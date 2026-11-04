"""Pipeline stage `evaluate`: statistical inefficiency tests, replacements, and scheme metrics.

Input: `<data dir>/train/` (`_train.json`, Parquet outputs, `staged/`), `<data dir>/transform/`,
and `<data dir>/clean/_clean.json`.
Output: `<data dir>/evaluate/inefficiency_analysis.parquet`, `replacement_targets.parquet`,
`replacements.parquet`, `model_metrics.parquet`, and `_evaluate.json`.
Responsibility: verify the full provenance chain and staged bundle via `delphos_ml.load_model()`,
execute §3.12 hypothesis tests with Holm-Bonferroni correction, §3.13 unpadded top-3 replacement
rankings, and §3.15 model comparison metrics without temporal leakage, and atomically swap
`data/evaluate/`. Like `clean.py`, `transform.py`, and `train.py`, this stage module holds the
schemas, provenance checks, and staging swap while delegating math to `delphos_ml.evaluation`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import tempfile
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import typer

from delphos_ml.artifacts import (
    SHA256_HEX_PATTERN,
    ArtifactError,
    LoadedArtifacts,
    collect_runtime_versions,
    load_model,
)
from delphos_ml.config import ConfigError, Settings, load_settings
from delphos_ml.evaluation import (
    build_replacements,
    compute_scheme_metrics,
    run_inefficiency_tests,
)
from delphos_ml.models import ValidatedTransformConfig, validate_transform_manifest
from delphos_ml.pipeline._staging import (
    _check_ownership,
    _prepare_data_dir,
    _remove_best_effort,
    _staging_prefix,
    _swap_in,
)
from delphos_ml.pipeline.clean import MANIFEST_FILE_NAME as CLEAN_MANIFEST_FILE_NAME
from delphos_ml.pipeline.clean import STAGE_DIR_NAME as CLEAN_DIR_NAME
from delphos_ml.pipeline.train import MANIFEST_FILE_NAME as TRAIN_MANIFEST_FILE_NAME
from delphos_ml.pipeline.train import STAGE_DIR_NAME as TRAIN_DIR_NAME
from delphos_ml.pipeline.train import (
    TABLE_CLUSTERS,
    TABLE_PLAYER_PREDICTIONS,
    TABLE_TRANSFER_PREDICTIONS,
)
from delphos_ml.pipeline.transform import MANIFEST_FILE_NAME as TRANSFORM_MANIFEST_FILE_NAME
from delphos_ml.pipeline.transform import STAGE_DIR_NAME as TRANSFORM_DIR_NAME
from delphos_ml.pipeline.transform import TABLE_PLAYER_SEASONS, TABLE_TRANSFER_EVENTS

STAGE_DIR_NAME = "evaluate"
MANIFEST_FILE_NAME = "_evaluate.json"

TABLE_INEFFICIENCY_ANALYSIS = "inefficiency_analysis"
TABLE_REPLACEMENT_TARGETS = "replacement_targets"
TABLE_REPLACEMENTS = "replacements"
TABLE_MODEL_METRICS = "model_metrics"

_RENAME_ATTEMPTS = 3
_RENAME_RETRY_DELAY_SECONDS = 0.5

INEFFICIENCY_ANALYSIS_SCHEMA = pa.schema(
    [
        pa.field("scope", pa.string()),
        pa.field("test_id", pa.string()),
        pa.field("hypothesis", pa.string()),
        pa.field("statistic_name", pa.string()),
        pa.field("statistic", pa.float64()),
        pa.field("p_value", pa.float64()),
        pa.field("p_value_holm", pa.float64()),
        pa.field("alpha", pa.float64()),
        pa.field("reject_null", pa.bool_()),
        pa.field("n_primary", pa.int64()),
        pa.field("n_secondary", pa.int64(), nullable=True),
        pa.field("effect_size_name", pa.string()),
        pa.field("effect_size", pa.float64()),
        pa.field("primary_median_log10", pa.float64()),
        pa.field("secondary_median_log10", pa.float64(), nullable=True),
        pa.field("median_eur_ratio", pa.float64()),
    ]
)

REPLACEMENT_TARGETS_SCHEMA = pa.schema(
    [
        pa.field("player_id", pa.int64()),
        pa.field("season", pa.int64()),
        pa.field("position", pa.string()),
        pa.field("cluster_id", pa.int64()),
        pa.field("market_value_eur", pa.float64()),
        pa.field("elite_mv_threshold_eur", pa.float64()),
        pa.field("is_elite_asset", pa.bool_()),
        pa.field("distance_ceiling", pa.float64()),
        pa.field("qualifying_count", pa.int64()),
        pa.field("shortfall_reason", pa.string(), nullable=True),
    ]
)

REPLACEMENTS_SCHEMA = pa.schema(
    [
        pa.field("target_player_id", pa.int64()),
        pa.field("season", pa.int64()),
        pa.field("rank", pa.int64()),
        pa.field("candidate_player_id", pa.int64()),
        pa.field("cluster_id", pa.int64()),
        pa.field("position", pa.string()),
        pa.field("euclidean_distance", pa.float64()),
        pa.field("similarity_score", pa.float64()),
        pa.field("target_market_value_eur", pa.float64()),
        pa.field("candidate_market_value_eur", pa.float64()),
        pa.field("cost_savings_eur", pa.float64()),
        pa.field("cost_ratio", pa.float64()),
        pa.field("candidate_fair_value_eur", pa.float64()),
        pa.field("candidate_residual_log10", pa.float64()),
        pa.field("candidate_valuation_status", pa.string()),
        pa.field("target_is_elite_asset", pa.bool_()),
    ]
)

MODEL_METRICS_SCHEMA = pa.schema(
    [
        pa.field("scope", pa.string()),
        pa.field("model", pa.string()),
        pa.field("metric", pa.string()),
        pa.field("value", pa.float64()),
        pa.field("se", pa.float64(), nullable=True),
        pa.field("n_rows", pa.int64()),
    ]
)


class EvaluateError(Exception):
    """An expected evaluate failure, reported to the user as a one-line message."""


def evaluate() -> None:
    """Run market-inefficiency tests, replacement rankings, and scheme metrics from data/train/
    into data/evaluate/.

    Reads _train.json, staged/, and Parquet outputs from <DELPHOS_DATA_DIR>/train/ plus
    <DELPHOS_DATA_DIR>/transform/ and <DELPHOS_DATA_DIR>/clean/_clean.json, and writes
    inefficiency_analysis.parquet, replacement_targets.parquet, replacements.parquet,
    model_metrics.parquet, and _evaluate.json to <DELPHOS_DATA_DIR>/evaluate/.
    """
    try:
        settings = load_settings()
        manifest = _run(settings)
    except (ConfigError, EvaluateError) as exc:
        typer.echo(f"evaluate failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Evaluated {manifest['tables'][TABLE_INEFFICIENCY_ANALYSIS]['rows']} inefficiency tests, "
        f"{manifest['tables'][TABLE_REPLACEMENTS]['rows']} replacements across "
        f"{manifest['tables'][TABLE_REPLACEMENT_TARGETS]['rows']} active-season players, and "
        f"{manifest['tables'][TABLE_MODEL_METRICS]['rows']} metric rows into "
        f"{settings.data_dir / STAGE_DIR_NAME}"
    )


def _check_hex_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_HEX_PATTERN.fullmatch(value) is None:
        raise EvaluateError(f"missing valid 64-hex {label}")
    return value


def _check_finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise EvaluateError(f"invalid finite number for {label}")
    return float(value)


def _load_provenance_and_bundle(
    data_dir: Path, settings: Settings
) -> tuple[
    dict[str, Any], dict[str, Any], ValidatedTransformConfig, LoadedArtifacts, dict[str, str]
]:
    clean_path = data_dir / CLEAN_DIR_NAME / CLEAN_MANIFEST_FILE_NAME
    transform_path = data_dir / TRANSFORM_DIR_NAME / TRANSFORM_MANIFEST_FILE_NAME
    train_path = data_dir / TRAIN_DIR_NAME / TRAIN_MANIFEST_FILE_NAME
    for path, hint in (
        (clean_path, "clean"),
        (transform_path, "transform"),
        (train_path, "train"),
    ):
        if not path.is_file():
            raise EvaluateError(f"missing {path}; run {hint} first")
    try:
        clean_bytes = clean_path.read_bytes()
        transform_bytes = transform_path.read_bytes()
        train_bytes = train_path.read_bytes()
        clean_man = json.loads(clean_bytes.decode("utf-8"))
        transform_man = json.loads(transform_bytes.decode("utf-8"))
        train_man = json.loads(train_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluateError(f"could not read upstream manifests: {exc}") from exc

    if (
        not isinstance(clean_man, dict)
        or not isinstance(transform_man, dict)
        or not isinstance(train_man, dict)
    ):
        raise EvaluateError("upstream manifests must be JSON objects")
    raw_ver = train_man.get("version")
    if (
        train_man.get("dataset") != settings.kaggle_dataset
        or isinstance(raw_ver, bool)
        or raw_ver != settings.kaggle_dataset_version
    ):
        raise EvaluateError("train manifest dataset/version does not match DELPHOS_KAGGLE_*")

    snapshot_sha = _check_hex_digest(clean_man.get("source_snapshot_sha256"), "clean snapshot sha")
    rec_snap = _check_hex_digest(train_man.get("source_snapshot_sha256"), "train snapshot sha")
    clean_sha = hashlib.sha256(clean_bytes).hexdigest()
    rec_clean = _check_hex_digest(train_man.get("clean_manifest_sha256"), "train clean sha")
    transform_sha = hashlib.sha256(transform_bytes).hexdigest()
    rec_transform = _check_hex_digest(
        train_man.get("transform_manifest_sha256"), "train transform sha"
    )
    if (
        not hmac.compare_digest(snapshot_sha, rec_snap)
        or not hmac.compare_digest(clean_sha, rec_clean)
        or not hmac.compare_digest(transform_sha, rec_transform)
    ):
        raise EvaluateError("provenance hash chain mismatch across clean, transform, and train")

    try:
        cfg = validate_transform_manifest(transform_man)
    except ValueError as exc:
        raise EvaluateError(str(exc)) from exc
    bundle_dir = train_man.get("bundle_dir")
    bundle_digests = train_man.get("bundle_sha256")
    if not isinstance(bundle_dir, str) or not isinstance(bundle_digests, dict):
        raise EvaluateError("_train.json is missing bundle_dir or bundle_sha256")
    try:
        bundle = load_model(
            bundle_dir, expected_sha256=bundle_digests, artifacts_dir=data_dir / TRAIN_DIR_NAME
        )
    except ArtifactError as exc:
        raise EvaluateError(f"staged artifact verification failed: {exc}") from exc

    hashes = {
        "source_snapshot_sha256": snapshot_sha,
        "clean_manifest_sha256": clean_sha,
        "transform_manifest_sha256": transform_sha,
        "train_manifest_sha256": hashlib.sha256(train_bytes).hexdigest(),
    }
    return transform_man, train_man, cfg, bundle, hashes


def _write_parquet(frame: pd.DataFrame, schema: pa.Schema, path: Path) -> dict[str, Any]:
    if frame.empty:
        arrays = [pa.array([], type=field.type) for field in schema]
        table = pa.Table.from_arrays(arrays, schema=schema)
    else:
        table = pa.Table.from_pandas(frame, schema=schema, preserve_index=False)
    pq.write_table(table, path)
    return {
        "parquet_file": path.name,
        "rows": int(table.num_rows),
        "columns": list(table.schema.names),
        "dtypes": {field.name: str(field.type) for field in table.schema},
    }


def _expected_rows(tables: Any, table_name: str, manifest_label: str) -> int:
    if not isinstance(tables, dict) or not isinstance(tables.get(table_name), dict):
        raise EvaluateError(f"{manifest_label} is missing tables.{table_name}")
    raw = tables[table_name].get("rows")
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise EvaluateError(f"{manifest_label} tables.{table_name}.rows must be a non-negative int")
    return raw


def _run(settings: Settings) -> dict[str, Any]:
    started = time.perf_counter()
    evaluated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    data_dir = settings.data_dir
    target = data_dir / STAGE_DIR_NAME
    expected_tables = {
        TABLE_INEFFICIENCY_ANALYSIS,
        TABLE_REPLACEMENT_TARGETS,
        TABLE_REPLACEMENTS,
        TABLE_MODEL_METRICS,
    }
    typer.echo(f"Data directory: {data_dir}")
    _prepare_data_dir(
        data_dir,
        stage=STAGE_DIR_NAME,
        manifest_file_name=MANIFEST_FILE_NAME,
        expected_table_names=expected_tables,
        error=EvaluateError,
        rename_attempts=_RENAME_ATTEMPTS,
        rename_delay_seconds=_RENAME_RETRY_DELAY_SECONDS,
    )
    _check_ownership(
        target, stage=STAGE_DIR_NAME, manifest_file_name=MANIFEST_FILE_NAME, error=EvaluateError
    )
    transform_man, train_man, cfg, bundle, hashes = _load_provenance_and_bundle(data_dir, settings)

    ps_path = data_dir / TRANSFORM_DIR_NAME / f"{TABLE_PLAYER_SEASONS}.parquet"
    tr_ev_path = data_dir / TRANSFORM_DIR_NAME / f"{TABLE_TRANSFER_EVENTS}.parquet"
    preds_path = data_dir / TRAIN_DIR_NAME / f"{TABLE_PLAYER_PREDICTIONS}.parquet"
    cl_path = data_dir / TRAIN_DIR_NAME / f"{TABLE_CLUSTERS}.parquet"
    tr_pred_path = data_dir / TRAIN_DIR_NAME / f"{TABLE_TRANSFER_PREDICTIONS}.parquet"
    for req in (ps_path, tr_ev_path, preds_path, cl_path, tr_pred_path):
        if not req.is_file():
            raise EvaluateError(f"missing upstream Parquet file {req}")
    try:
        player_seasons = pd.read_parquet(ps_path)
        tr_ev_rows = pq.read_metadata(tr_ev_path).num_rows
        player_predictions = pd.read_parquet(preds_path)
        clusters = pd.read_parquet(cl_path)
        transfer_predictions = pd.read_parquet(tr_pred_path)
    except (OSError, pa.ArrowException) as exc:
        raise EvaluateError(f"could not read upstream Parquet files: {exc}") from exc

    tf_tables = transform_man.get("tables")
    tr_tables = train_man.get("tables")
    if (
        len(player_seasons) != _expected_rows(tf_tables, TABLE_PLAYER_SEASONS, "_transform.json")
        or tr_ev_rows != _expected_rows(tf_tables, TABLE_TRANSFER_EVENTS, "_transform.json")
        or len(player_predictions)
        != _expected_rows(tr_tables, TABLE_PLAYER_PREDICTIONS, "_train.json")
        or len(clusters) != _expected_rows(tr_tables, TABLE_CLUSTERS, "_train.json")
        or len(transfer_predictions)
        != _expected_rows(tr_tables, TABLE_TRANSFER_PREDICTIONS, "_train.json")
        or len(player_seasons) != len(player_predictions)
    ):
        raise EvaluateError("upstream Parquet row counts do not match _transform.json/_train.json")

    if "country_group" not in player_seasons or player_seasons["country_group"].isna().any():
        raise EvaluateError("player_seasons is missing non-null country_group values")
    allowed_cg = {*cfg.country_groups, "other"}
    if not set(player_seasons["country_group"].unique()).issubset(allowed_cg):
        raise EvaluateError("player_seasons contains country_group values outside _transform.json")

    thresholds = train_man.get("thresholds")
    if not isinstance(thresholds, dict):
        raise EvaluateError("_train.json thresholds must be a JSON object")
    q25 = _check_finite_number(thresholds.get("q25_overvalued_log10"), "q25_overvalued_log10")
    q75 = _check_finite_number(thresholds.get("q75_undervalued_log10"), "q75_undervalued_log10")
    if q25 > q75:
        raise EvaluateError("_train.json q25_overvalued_log10 exceeds q75_undervalued_log10")

    try:
        ineff_df = run_inefficiency_tests(transfer_predictions, q25=q25, q75=q75)
        targets_df, repl_df, elite_by_pos, radii, active_season = build_replacements(
            player_seasons,
            player_predictions,
            clusters,
            cluster_preprocessor=bundle.cluster_preprocessor,
        )
        metrics_df = compute_scheme_metrics(
            player_seasons,
            player_predictions,
            clusters,
            bundle,
            empirical_bayes_m=cfg.empirical_bayes_m,
            prior_grouping=cfg.prior_grouping,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise EvaluateError(f"evaluation failed: {exc}") from exc

    elite_sub = targets_df[targets_df["is_elite_asset"]]
    coverage = {
        "active_players": int(len(targets_df)),
        "active_with_3_replacements": int((targets_df["qualifying_count"] == 3).sum()),
        "elite_players": int(len(elite_sub)),
        "elite_with_3_replacements": int((elite_sub["qualifying_count"] == 3).sum()),
        "shortfall_counts": {
            str(k): int(v)
            for k, v in targets_df["shortfall_reason"].dropna().value_counts().sort_index().items()
        },
    }

    try:
        staging = Path(tempfile.mkdtemp(prefix=_staging_prefix(STAGE_DIR_NAME), dir=data_dir))
    except OSError as exc:
        raise EvaluateError(f"could not create staging directory in {data_dir}: {exc}") from exc
    try:
        ineff_path = staging / f"{TABLE_INEFFICIENCY_ANALYSIS}.parquet"
        targets_path = staging / f"{TABLE_REPLACEMENT_TARGETS}.parquet"
        repl_path = staging / f"{TABLE_REPLACEMENTS}.parquet"
        metrics_path = staging / f"{TABLE_MODEL_METRICS}.parquet"
        tables_meta = {
            TABLE_INEFFICIENCY_ANALYSIS: _write_parquet(
                ineff_df, INEFFICIENCY_ANALYSIS_SCHEMA, ineff_path
            ),
            TABLE_REPLACEMENT_TARGETS: _write_parquet(
                targets_df, REPLACEMENT_TARGETS_SCHEMA, targets_path
            ),
            TABLE_REPLACEMENTS: _write_parquet(repl_df, REPLACEMENTS_SCHEMA, repl_path),
            TABLE_MODEL_METRICS: _write_parquet(metrics_df, MODEL_METRICS_SCHEMA, metrics_path),
        }
        manifest: dict[str, Any] = {
            "dataset": settings.kaggle_dataset,
            "version": settings.kaggle_dataset_version,
            **hashes,
            "evaluated_at": evaluated_at,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "tool_versions": {
                **collect_runtime_versions(),
                "pandas": version("pandas"),
                "pyarrow": version("pyarrow"),
            },
            "active_replacement_season": active_season,
            "elite_thresholds_eur": elite_by_pos,
            "athletic_distance_ceilings": radii,
            "replacement_coverage": coverage,
            "tables": tables_meta,
        }
        (staging / MANIFEST_FILE_NAME).write_text(
            json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        _swap_in(
            staging,
            target,
            stage=STAGE_DIR_NAME,
            error=EvaluateError,
            rename_attempts=_RENAME_ATTEMPTS,
            rename_delay_seconds=_RENAME_RETRY_DELAY_SECONDS,
        )
    except BaseException:
        if staging.exists():
            _remove_best_effort(staging, "an incomplete staging directory", stage=STAGE_DIR_NAME)
        raise
    return manifest
