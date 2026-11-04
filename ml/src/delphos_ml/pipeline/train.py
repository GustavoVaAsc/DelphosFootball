"""Pipeline stage `train`: fits the five KDD models and writes staged artifacts and predictions.

Input: `<data dir>/transform/_transform.json`, `player_seasons.parquet`, `transfer_events.parquet`,
and `<data dir>/clean/_clean.json` for snapshot provenance.
Output: `<data dir>/train/player_predictions.parquet`, `clusters.parquet`,
`transfer_predictions.parquet`, `staged/` (`.joblib` estimators + `manifest.json`), and
`_train.json`.
Responsibility: validate `_transform.json` and `_clean.json` provenance and row-count/vocabulary
agreement, fit K-Means, OLS linear and degree-2 polynomial regressors, and Decision Tree and Random
Forest classifiers strictly on `train` without leakage, write and self-verify the staged artifact
bundle via `delphos_ml.artifacts.write_verified_bundle()`, and atomically swap `data/train/`. Like
`clean.py` and `transform.py`, this stage module carries the stage schemas, provenance checks, and
staging swap while delegating math and serialization to `models` and `artifacts`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
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
    collect_runtime_versions,
    write_verified_bundle,
)
from delphos_ml.config import ConfigError, Settings, load_settings
from delphos_ml.models import (
    ValidatedTransformConfig,
    fit_and_score_all,
    validate_transform_manifest,
)
from delphos_ml.pipeline._staging import (
    _check_ownership,
    _prepare_data_dir,
    _remove_best_effort,
    _staging_prefix,
    _swap_in,
)
from delphos_ml.pipeline.clean import MANIFEST_FILE_NAME as CLEAN_MANIFEST_FILE_NAME
from delphos_ml.pipeline.clean import STAGE_DIR_NAME as CLEAN_DIR_NAME
from delphos_ml.pipeline.transform import MANIFEST_FILE_NAME as TRANSFORM_MANIFEST_FILE_NAME
from delphos_ml.pipeline.transform import STAGE_DIR_NAME as TRANSFORM_DIR_NAME
from delphos_ml.pipeline.transform import TABLE_PLAYER_SEASONS, TABLE_TRANSFER_EVENTS

STAGE_DIR_NAME = "train"
MANIFEST_FILE_NAME = "_train.json"
BUNDLE_DIR_NAME = "staged"

TABLE_PLAYER_PREDICTIONS = "player_predictions"
TABLE_CLUSTERS = "clusters"
TABLE_TRANSFER_PREDICTIONS = "transfer_predictions"

_RENAME_ATTEMPTS = 3
_RENAME_RETRY_DELAY_SECONDS = 0.5

PLAYER_PREDICTIONS_SCHEMA = pa.schema(
    [
        pa.field("player_id", pa.int64()),
        pa.field("season", pa.int64()),
        pa.field("as_of_date", pa.date32()),
        pa.field("split", pa.string()),
        pa.field("residual_source", pa.string()),
        pa.field("log10_market_value", pa.float64()),
        pa.field("market_value_eur", pa.float64()),
        pa.field("linear_log10_pred", pa.float64()),
        pa.field("poly_log10_pred", pa.float64()),
        pa.field("predicted_log10_value", pa.float64()),
        pa.field("fair_value_eur", pa.float64()),
        pa.field("residual_log10", pa.float64()),
        pa.field("valuation_status", pa.string()),
        pa.field("is_undervalued", pa.bool_()),
        pa.field("dt_undervalued_prob", pa.float64()),
        pa.field("dt_undervalued_pred", pa.bool_()),
        pa.field("rf_undervalued_prob", pa.float64()),
        pa.field("rf_undervalued_pred", pa.bool_()),
    ]
)

CLUSTERS_SCHEMA = pa.schema(
    [
        pa.field("player_id", pa.int64()),
        pa.field("season", pa.int64()),
        pa.field("split", pa.string()),
        pa.field("cluster_id", pa.int64()),
        pa.field("centroid_distance", pa.float64()),
    ]
)

TRANSFER_PREDICTIONS_SCHEMA = pa.schema(
    [
        pa.field("player_id", pa.int64()),
        pa.field("season", pa.int64()),
        pa.field("split", pa.string()),
        pa.field("transfer_date", pa.date32()),
        pa.field("club_id", pa.int64()),
        pa.field("league_id", pa.string()),
        pa.field("buyer_league_id", pa.string(), nullable=True),
        pa.field("transfer_fee", pa.float64()),
        pa.field("pre_transfer_market_value", pa.float64()),
        pa.field("log10_transfer_fee", pa.float64()),
        pa.field("linear_log10_pred", pa.float64()),
        pa.field("poly_log10_pred", pa.float64()),
        pa.field("fair_value_eur", pa.float64()),
        pa.field("fee_minus_fair_log10", pa.float64()),
        pa.field("fee_minus_mv_log10", pa.float64()),
        pa.field("cluster_id", pa.int64()),
        pa.field("rf_undervalued_prob", pa.float64()),
    ]
)


class TrainError(Exception):
    """An expected train failure, reported to the user as a one-line message."""


def train() -> None:
    """Fit the five KDD models on data/transform/ and write predictions and staged artifacts to
    data/train/.

    Reads _transform.json, player_seasons.parquet and transfer_events.parquet from
    <DELPHOS_DATA_DIR>/transform/ (verifying provenance against data/clean/_clean.json) and writes
    player_predictions.parquet, clusters.parquet, transfer_predictions.parquet, the verified joblib
    artifact bundle under data/train/staged/, and _train.json to <DELPHOS_DATA_DIR>/train/.
    """
    try:
        settings = load_settings()
        manifest = _run(settings)
    except (ConfigError, TrainError) as exc:
        typer.echo(f"train failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Trained 5 models on {manifest['tables'][TABLE_PLAYER_PREDICTIONS]['rows']} "
        f"player-seasons and {manifest['tables'][TABLE_TRANSFER_PREDICTIONS]['rows']} transfers "
        f"into {settings.data_dir / STAGE_DIR_NAME}"
    )


def _load_provenance(
    data_dir: Path, settings: Settings
) -> tuple[dict[str, Any], ValidatedTransformConfig, str, str]:
    transform_manifest_path = data_dir / TRANSFORM_DIR_NAME / TRANSFORM_MANIFEST_FILE_NAME
    clean_manifest_path = data_dir / CLEAN_DIR_NAME / CLEAN_MANIFEST_FILE_NAME
    if not transform_manifest_path.is_file():
        raise TrainError(f"missing {transform_manifest_path}; run transform first")
    if not clean_manifest_path.is_file():
        raise TrainError(f"missing {clean_manifest_path}; run clean first")
    try:
        transform_bytes = transform_manifest_path.read_bytes()
        clean_bytes = clean_manifest_path.read_bytes()
        transform_manifest = json.loads(transform_bytes.decode("utf-8"))
        clean_manifest = json.loads(clean_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrainError(f"could not read upstream manifests: {exc}") from exc

    if not isinstance(transform_manifest, dict) or not isinstance(clean_manifest, dict):
        raise TrainError("upstream _transform.json and _clean.json must be JSON objects")
    raw_ver = transform_manifest.get("version")
    if (
        transform_manifest.get("dataset") != settings.kaggle_dataset
        or isinstance(raw_ver, bool)
        or raw_ver != settings.kaggle_dataset_version
    ):
        raise TrainError("transform manifest dataset/version does not match DELPHOS_KAGGLE_*")
    recorded_clean_sha = transform_manifest.get("clean_manifest_sha256")
    if (
        not isinstance(recorded_clean_sha, str)
        or SHA256_HEX_PATTERN.fullmatch(recorded_clean_sha) is None
    ):
        raise TrainError("_transform.json is missing a valid 64-hex clean_manifest_sha256")
    actual_clean_sha = hashlib.sha256(clean_bytes).hexdigest()
    if not hmac.compare_digest(actual_clean_sha, recorded_clean_sha):
        raise TrainError("clean_manifest_sha256 in _transform.json does not match _clean.json")
    snapshot_sha256 = clean_manifest.get("source_snapshot_sha256")
    if (
        not isinstance(snapshot_sha256, str)
        or SHA256_HEX_PATTERN.fullmatch(snapshot_sha256) is None
    ):
        raise TrainError("_clean.json is missing a valid 64-hex source_snapshot_sha256")
    try:
        cfg = validate_transform_manifest(transform_manifest)
    except ValueError as exc:
        raise TrainError(str(exc)) from exc
    return transform_manifest, cfg, hashlib.sha256(transform_bytes).hexdigest(), snapshot_sha256


def _validate_inputs(
    player_seasons: pd.DataFrame,
    transfer_events: pd.DataFrame,
    transform_manifest: dict[str, Any],
    cfg: ValidatedTransformConfig,
) -> dict[str, int]:
    tables = transform_manifest.get("tables")
    if not isinstance(tables, dict):
        raise TrainError("_transform.json is missing tables metadata")
    ps_info = tables.get(TABLE_PLAYER_SEASONS)
    tr_info = tables.get(TABLE_TRANSFER_EVENTS)
    if not isinstance(ps_info, dict) or not isinstance(tr_info, dict):
        raise TrainError("_transform.json tables metadata is incomplete")
    if len(player_seasons) != ps_info.get("rows") or len(transfer_events) != tr_info.get("rows"):
        raise TrainError("transform Parquet row counts do not match _transform.json")

    rows_per_split = {
        str(k): int(v) for k, v in player_seasons["split"].value_counts().sort_index().items()
    }
    recorded_splits = transform_manifest.get("rows_per_split")
    if isinstance(recorded_splits, dict) and rows_per_split != recorded_splits:
        raise TrainError("player_seasons split counts do not match _transform.json rows_per_split")

    allowed_countries = {*cfg.country_groups, "other"}
    for name, frame in (
        (TABLE_PLAYER_SEASONS, player_seasons),
        (TABLE_TRANSFER_EVENTS, transfer_events),
    ):
        if "country_group" not in frame or frame["country_group"].isna().any():
            raise TrainError(f"{name} is missing non-null country_group values")
        if not set(frame["country_group"].unique()).issubset(allowed_countries):
            raise TrainError(
                f"{name} contains country_group values outside _transform.json country_groups"
            )
    return rows_per_split


def _write_parquet(frame: pd.DataFrame, schema: pa.Schema, path: Path) -> dict[str, Any]:
    table = pa.Table.from_pandas(frame, schema=schema, preserve_index=False)
    pq.write_table(table, path)
    return {
        "parquet_file": path.name,
        "rows": int(table.num_rows),
        "columns": list(table.schema.names),
        "dtypes": {field.name: str(field.type) for field in table.schema},
    }


def _attach_buyer_league_id(transfer_events: pd.DataFrame, data_dir: Path) -> pd.DataFrame:
    clean_tr_path = data_dir / CLEAN_DIR_NAME / "transfers.parquet"
    clean_cl_path = data_dir / CLEAN_DIR_NAME / "clubs.parquet"
    if not clean_tr_path.is_file() or not clean_cl_path.is_file():
        raise TrainError(f"missing clean transfers or clubs under {data_dir / CLEAN_DIR_NAME}")
    try:
        clean_tr = pd.read_parquet(
            clean_tr_path,
            columns=[
                "player_id",
                "transfer_date",
                "to_club_id",
                "transfer_fee",
                "market_value_in_eur",
            ],
        )
        clean_cl = pd.read_parquet(clean_cl_path, columns=["club_id", "domestic_competition_id"])
    except (OSError, pa.ArrowException) as exc:
        raise TrainError(f"could not read clean transfers or clubs: {exc}") from exc

    paid_tr = clean_tr[
        clean_tr["transfer_fee"].notna()
        & (clean_tr["transfer_fee"] > 0.0)
        & clean_tr["market_value_in_eur"].notna()
        & (clean_tr["market_value_in_eur"] > 0.0)
    ].copy()
    leagues = clean_cl[["club_id", "domestic_competition_id"]]
    paid_tr = paid_tr.merge(
        leagues.rename(
            columns={"club_id": "to_club_id", "domestic_competition_id": "buyer_league_id"}
        ),
        on="to_club_id",
        how="left",
    )
    paid_tr = paid_tr.rename(columns={"market_value_in_eur": "pre_transfer_market_value"})
    keys = ["player_id", "transfer_date", "transfer_fee", "pre_transfer_market_value"]
    try:
        merged = transfer_events.merge(
            paid_tr[keys + ["buyer_league_id"]],
            on=keys,
            how="left",
            validate="one_to_one",
        )
    except (ValueError, pd.errors.MergeError) as exc:
        raise TrainError(f"could not attach buyer_league_id to transfer_events: {exc}") from exc
    return merged


def _run(settings: Settings) -> dict[str, Any]:
    started = time.perf_counter()
    trained_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    data_dir = settings.data_dir
    target = data_dir / STAGE_DIR_NAME
    expected_tables = {TABLE_PLAYER_PREDICTIONS, TABLE_CLUSTERS, TABLE_TRANSFER_PREDICTIONS}
    typer.echo(f"Data directory: {data_dir}")
    _prepare_data_dir(
        data_dir,
        stage=STAGE_DIR_NAME,
        manifest_file_name=MANIFEST_FILE_NAME,
        expected_table_names=expected_tables,
        error=TrainError,
        rename_attempts=_RENAME_ATTEMPTS,
        rename_delay_seconds=_RENAME_RETRY_DELAY_SECONDS,
    )
    _check_ownership(
        target, stage=STAGE_DIR_NAME, manifest_file_name=MANIFEST_FILE_NAME, error=TrainError
    )
    transform_manifest, cfg, transform_sha256, snapshot_sha256 = _load_provenance(
        data_dir, settings
    )
    # Hard-code input Parquet file names (docs/TRANSFORM_PLAN.md section 4).
    ps_path = data_dir / TRANSFORM_DIR_NAME / f"{TABLE_PLAYER_SEASONS}.parquet"
    tr_path = data_dir / TRANSFORM_DIR_NAME / f"{TABLE_TRANSFER_EVENTS}.parquet"
    if not ps_path.is_file() or not tr_path.is_file():
        raise TrainError(f"missing transform Parquet inputs under {data_dir / TRANSFORM_DIR_NAME}")

    try:
        player_seasons = pd.read_parquet(ps_path)
        transfer_events = pd.read_parquet(tr_path)
    except (OSError, pa.ArrowException) as exc:
        raise TrainError(f"could not read transform Parquet inputs: {exc}") from exc
    rows_per_split = _validate_inputs(player_seasons, transfer_events, transform_manifest, cfg)
    transfer_events = _attach_buyer_league_id(transfer_events, data_dir)
    try:
        suite = fit_and_score_all(
            player_seasons,
            transfer_events,
            empirical_bayes_m=cfg.empirical_bayes_m,
            prior_grouping=cfg.prior_grouping,
        )
    except (ValueError, KeyError) as exc:
        raise TrainError(f"model training failed: {exc}") from exc

    try:
        staging = Path(tempfile.mkdtemp(prefix=_staging_prefix(STAGE_DIR_NAME), dir=data_dir))
    except OSError as exc:
        raise TrainError(f"could not create staging directory in {data_dir}: {exc}") from exc
    try:
        tables_meta = {
            TABLE_PLAYER_PREDICTIONS: _write_parquet(
                suite.player_predictions,
                PLAYER_PREDICTIONS_SCHEMA,
                staging / f"{TABLE_PLAYER_PREDICTIONS}.parquet",
            ),
            TABLE_CLUSTERS: _write_parquet(
                suite.clusters, CLUSTERS_SCHEMA, staging / f"{TABLE_CLUSTERS}.parquet"
            ),
            TABLE_TRANSFER_PREDICTIONS: _write_parquet(
                suite.transfer_predictions,
                TRANSFER_PREDICTIONS_SCHEMA,
                staging / f"{TABLE_TRANSFER_PREDICTIONS}.parquet",
            ),
        }
        try:
            bundle_digests = write_verified_bundle(
                staging,
                BUNDLE_DIR_NAME,
                suite,
                trained_at=trained_at,
                dataset_handle=settings.kaggle_dataset,
                dataset_version=settings.kaggle_dataset_version,
                snapshot_sha256=snapshot_sha256,
                clean_sha256=str(transform_manifest["clean_manifest_sha256"]),
                transform_sha256=transform_sha256,
                cfg=cfg,
                rows_per_split=rows_per_split,
            )
        except ArtifactError as exc:
            raise TrainError(f"staged artifact self-verification failed: {exc}") from exc
        manifest: dict[str, Any] = {
            "dataset": settings.kaggle_dataset,
            "version": settings.kaggle_dataset_version,
            "source_snapshot_sha256": snapshot_sha256,
            "clean_manifest_sha256": str(transform_manifest["clean_manifest_sha256"]),
            "transform_manifest_sha256": transform_sha256,
            "trained_at": trained_at,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "tool_versions": {
                **collect_runtime_versions(),
                "pandas": version("pandas"),
                "pyarrow": version("pyarrow"),
            },
            "thresholds": {
                "q25_overvalued_log10": suite.q25_overvalued_log10,
                "q75_undervalued_log10": suite.q75_undervalued_log10,
                "oof_seasons": list(suite.oof_seasons),
                "oof_rows": suite.oof_rows,
            },
            "cluster_order": list(suite.cluster_order),
            "bundle_dir": BUNDLE_DIR_NAME,
            "bundle_sha256": bundle_digests,
            "tables": tables_meta,
        }
        (staging / MANIFEST_FILE_NAME).write_text(
            json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        _swap_in(
            staging,
            target,
            stage=STAGE_DIR_NAME,
            error=TrainError,
            rename_attempts=_RENAME_ATTEMPTS,
            rename_delay_seconds=_RENAME_RETRY_DELAY_SECONDS,
        )
    except BaseException:
        if staging.exists():
            _remove_best_effort(staging, "an incomplete staging directory", stage=STAGE_DIR_NAME)
        raise
    return manifest
