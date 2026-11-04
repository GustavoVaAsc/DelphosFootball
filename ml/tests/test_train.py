"""End-to-end, idempotency, parity, and leak-guard tests for `train` over synthetic data."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from sklearn.preprocessing import RobustScaler
from typer.testing import CliRunner

from delphos_ml import load_model
from delphos_ml.models.scoring import to_dense
from delphos_ml.pipeline.cli import app
from delphos_ml.pipeline.transform import PLAYER_SEASONS_SCHEMA, TRANSFER_EVENTS_SCHEMA

runner = CliRunner()

SNAPSHOT_SHA256 = "94f42930f5d50d76f5226f64bd2b9e4c70552e110ad28743b5edce4041c8b1c1"


def _make_player_row(
    player_id: int,
    season: int,
    split: str,
    *,
    mv_scale: float = 1.0,
) -> dict[str, Any]:
    positions = ("Defender", "Midfield", "Attack")
    sub_positions = ("Centre-Back", "Central Midfield", "Centre-Forward")
    idx = player_id % 3
    age = 20.0 + float((player_id * 3 + season) % 12)
    minutes = 450.0 + float((player_id % 7) * 300)
    goals = float((idx * 4) + (player_id % 5))
    assists = float((idx * 2) + (player_id % 4))
    log10_mv = float(5.7 + 0.12 * idx + 0.03 * goals + (0.45 if player_id % 4 == 0 else -0.25))
    log10_mv += float(np.log10(mv_scale))
    return {
        "player_id": player_id,
        "season": season,
        "as_of_date": dt.date(season + 1, 5, 30),
        "split": split,
        "club_id": 100 + (player_id % 6),
        "league_id": "ES1" if player_id % 2 == 0 else "PO1",
        "minutes": minutes,
        "apps": max(5.0, minutes / 80.0),
        "starts": max(3.0, minutes / 95.0),
        "captain": 1.0 if player_id % 5 == 0 else 0.0,
        "squad_inclusions": max(6.0, minutes / 75.0),
        "goals": goals,
        "assists": assists,
        "yellow_cards": float(player_id % 4),
        "red_cards": 1.0 if player_id % 9 == 0 else 0.0,
        "win_flag": 6.0,
        "clean_sheet_flag": 4.0,
        "goals_conceded": 12.0,
        "uefa_minutes": 180.0 if player_id % 3 == 0 else 0.0,
        "starter_ratio": 0.75 if player_id % 2 == 0 else 0.45,
        "captain_ratio": 0.1 if player_id % 5 == 0 else 0.0,
        "win_rate": 0.55 if player_id % 2 == 0 else 0.38,
        "clean_sheet_rate": 0.35,
        "goals_conceded_per_match": 1.15,
        "uefa_share": 0.2 if player_id % 3 == 0 else 0.0,
        "cup_share": 0.1,
        "league_position": float(1 + (player_id % 14)),
        "league_position_missing": False,
        "age": age,
        "age_sq": age * age,
        "height_in_cm": None if player_id % 7 == 0 else 178.0 + float(player_id % 12),
        "foot": None if player_id % 8 == 0 else ("left" if player_id % 3 == 0 else "right"),
        "position": positions[idx],
        "sub_position": sub_positions[idx],
        "country_group": "Spain" if player_id % 2 == 0 else "other",
        "log10_market_value": log10_mv,
    }


def _write_synthetic_transform_fixture(
    data_dir: Path,
    *,
    val_test_mv_scale: float = 1.0,
    manifest_overrides: dict[str, Any] | None = None,
) -> None:
    clean_dir = data_dir / "clean"
    transform_dir = data_dir / "transform"
    clean_dir.mkdir(parents=True, exist_ok=True)
    transform_dir.mkdir(parents=True, exist_ok=True)

    clean_manifest = {
        "dataset": "davidcariboo/player-scores",
        "version": 679,
        "source_snapshot_sha256": SNAPSHOT_SHA256,
    }
    clean_bytes = (json.dumps(clean_manifest, indent=2) + "\n").encode("utf-8")
    (clean_dir / "_clean.json").write_bytes(clean_bytes)
    clean_sha256 = hashlib.sha256(clean_bytes).hexdigest()

    ps_rows: list[dict[str, Any]] = []
    for season in (2019, 2020, 2021, 2022, 2023):
        for pid in range(1, 13):
            ps_rows.append(_make_player_row(pid + season * 100, season, "train"))
    for season, split in ((2024, "validation"), (2025, "test")):
        for pid in range(1, 9):
            ps_rows.append(
                _make_player_row(pid + season * 100, season, split, mv_scale=val_test_mv_scale)
            )

    tr_indices = [0, 1, 2, 3, 4, 5, 60, 61, 68, 69]
    tr_rows: list[dict[str, Any]] = []
    clean_tr_rows: list[dict[str, Any]] = []
    for idx, row_i in enumerate(tr_indices):
        base = ps_rows[row_i]
        pre_mv = float(10.0 ** base["log10_market_value"])
        t_date = dt.date(int(base["season"]) + 1, 7, 15)
        fee = pre_mv * (1.3 if idx % 2 == 0 else 0.8)
        to_cid = 999 if idx == 5 else (200 + (idx % 3))
        tr_rows.append(
            {
                **base,
                "transfer_date": t_date,
                "transfer_fee": fee,
                "pre_transfer_market_value": pre_mv,
            }
        )
        clean_tr_rows.append(
            {
                "player_id": base["player_id"],
                "transfer_date": t_date,
                "from_club_id": base["club_id"],
                "to_club_id": to_cid,
                "transfer_fee": fee,
                "market_value_in_eur": pre_mv,
            }
        )

    ps_table = pa.Table.from_pylist(ps_rows, schema=PLAYER_SEASONS_SCHEMA)
    tr_table = pa.Table.from_pylist(tr_rows, schema=TRANSFER_EVENTS_SCHEMA)
    pq.write_table(ps_table, transform_dir / "player_seasons.parquet")
    pq.write_table(tr_table, transform_dir / "transfer_events.parquet")

    pq.write_table(pa.Table.from_pylist(clean_tr_rows), clean_dir / "transfers.parquet")
    clean_cl_rows = [
        {"club_id": cid, "domestic_competition_id": "ES1" if cid % 2 == 0 else "PO1"}
        for cid in range(100, 110)
    ]
    clean_cl_rows.extend(
        [
            {"club_id": 999, "domestic_competition_id": "SA1"},
            {"club_id": 200, "domestic_competition_id": "GB1"},
            {"club_id": 201, "domestic_competition_id": "ES1"},
            {"club_id": 202, "domestic_competition_id": "PO1"},
        ]
    )
    pq.write_table(pa.Table.from_pylist(clean_cl_rows), clean_dir / "clubs.parquet")

    manifest: dict[str, Any] = {
        "dataset": "davidcariboo/player-scores",
        "version": 679,
        "clean_manifest_sha256": clean_sha256,
        "transformed_at": "2026-11-03T18:00:00Z",
        "tool_versions": {"pandas": "3.1.0", "pyarrow": "26.0.0"},
        "window_days": 365,
        "minutes_floor": 180,
        "empirical_bayes_m": 5,
        "prior_grouping": "position",
        "season_month_start": 7,
        "country_top_n": 10,
        "country_groups": ["Spain"],
        "rows_per_split": {"train": 60, "validation": 8, "test": 8},
        "rows_per_season": {
            "2019": 12,
            "2020": 12,
            "2021": 12,
            "2022": 12,
            "2023": 12,
            "2024": 8,
            "2025": 8,
        },
        "tables": {
            "player_seasons": {"parquet_file": "player_seasons.parquet", "rows": len(ps_rows)},
            "transfer_events": {"parquet_file": "transfer_events.parquet", "rows": len(tr_rows)},
        },
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (transform_dir / "_transform.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def test_train_builds_outputs_is_idempotent_and_matches_reloaded_bundle_parity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    _write_synthetic_transform_fixture(data_dir)
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(data_dir))

    # First run + back-to-back idempotent re-run replacing `data/train/staged/` cleanly.
    assert runner.invoke(app, ["train"]).exit_code == 0
    result = runner.invoke(app, ["train"])
    assert result.exit_code == 0, result.output
    assert list(data_dir.glob(".train-*")) == []

    train_dir = data_dir / "train"
    train_manifest = json.loads((train_dir / "_train.json").read_text(encoding="utf-8"))
    assert train_manifest["source_snapshot_sha256"] == SNAPSHOT_SHA256
    assert train_manifest["bundle_dir"] == "staged"

    rates = [c["centroid_goals_plus_assists_per90"] for c in train_manifest["cluster_order"]]
    assert rates == sorted(rates, reverse=True)

    ps_in = pd.read_parquet(data_dir / "transform" / "player_seasons.parquet")
    preds = pd.read_parquet(train_dir / "player_predictions.parquet")
    clusters = pd.read_parquet(train_dir / "clusters.parquet")
    transfers = pd.read_parquet(train_dir / "transfer_predictions.parquet")
    assert (len(preds), len(clusters), len(transfers)) == (76, 76, 10)
    assert set(preds.loc[preds["season"] == 2019, "residual_source"]) == {"in_sample_anchor"}
    assert set(preds.loc[preds["season"].isin([2020, 2021, 2022, 2023]), "residual_source"]) == {
        "oof"
    }
    assert set(preds.loc[preds["season"] == 2024, "residual_source"]) == {"validation"}
    assert set(preds.loc[preds["season"] == 2025, "residual_source"]) == {"test"}
    assert "buyer_league_id" in transfers.columns
    assert (transfers["buyer_league_id"] == "SA1").any()
    assert set(preds["valuation_status"]).issubset({"undervalued", "fair", "overvalued"})
    assert set(clusters["cluster_id"]) == {0, 1, 2}

    loaded = load_model(
        "staged",
        expected_sha256=train_manifest["bundle_sha256"],
        artifacts_dir=train_dir,
    )
    assert loaded.manifest["model_run_id"] == "staged"
    assert getattr(loaded.random_forest_model, "n_jobs", None) == 1
    cluster_numeric = loaded.cluster_preprocessor.named_transformers_["numeric"]
    assert isinstance(cluster_numeric.named_steps["scale"], RobustScaler)

    # Batch-vs-reloaded parity across all 5 estimators.
    np.testing.assert_allclose(
        loaded.model.predict(to_dense(loaded.preprocessor.transform(ps_in))),
        preds["linear_log10_pred"].to_numpy(),
        atol=1e-12,
    )
    np.testing.assert_allclose(
        loaded.polynomial_model.predict(to_dense(loaded.polynomial_preprocessor.transform(ps_in))),
        preds["poly_log10_pred"].to_numpy(),
        atol=1e-12,
    )
    np.testing.assert_array_equal(
        loaded.kmeans_model.predict(to_dense(loaded.cluster_preprocessor.transform(ps_in))),
        clusters["cluster_id"].to_numpy(),
    )
    x_cls = to_dense(loaded.classifier_preprocessor.transform(ps_in))
    np.testing.assert_allclose(
        loaded.decision_tree_model.predict_proba(x_cls)[:, 1],
        preds["dt_undervalued_prob"].to_numpy(),
        atol=1e-12,
    )
    np.testing.assert_allclose(
        loaded.random_forest_model.predict_proba(x_cls)[:, 1],
        preds["rf_undervalued_prob"].to_numpy(),
        atol=1e-12,
    )


def test_train_retired_recovery_rejects_incomplete_staged_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    _write_synthetic_transform_fixture(data_dir)
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(data_dir))
    assert runner.invoke(app, ["train"]).exit_code == 0

    retired = data_dir / ".train-retired-corrupt"
    (data_dir / "train").rename(retired)
    (retired / "staged" / "model.joblib").unlink()

    result = runner.invoke(app, ["train"])
    assert result.exit_code == 0
    assert "discarding .train-retired-corrupt" in result.output
    assert (data_dir / "train" / "staged" / "model.joblib").is_file()


def test_train_leak_guard_changing_val_and_test_leaves_fitted_bundle_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dir_a = tmp_path / "run_a"
    dir_b = tmp_path / "run_b"
    _write_synthetic_transform_fixture(dir_a, val_test_mv_scale=1.0)
    _write_synthetic_transform_fixture(dir_b, val_test_mv_scale=50.0)

    monkeypatch.setenv("DELPHOS_DATA_DIR", str(dir_a))
    assert runner.invoke(app, ["train"]).exit_code == 0
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(dir_b))
    assert runner.invoke(app, ["train"]).exit_code == 0

    man_a = json.loads((dir_a / "train" / "_train.json").read_text(encoding="utf-8"))
    man_b = json.loads((dir_b / "train" / "_train.json").read_text(encoding="utf-8"))
    assert man_a["thresholds"] == man_b["thresholds"]
    for joblib_name, digest_a in man_a["bundle_sha256"].items():
        if joblib_name.endswith(".joblib"):
            assert digest_a == man_b["bundle_sha256"][joblib_name], joblib_name


@pytest.mark.parametrize(
    "bad_override",
    [
        {"window_days": True},
        {"minutes_floor": 0},
        {"empirical_bayes_m": float("inf")},
        {"empirical_bayes_m": -1.0},
        {"prior_grouping": "club_id"},
        {"season_month_start": 13},
        {"country_groups": ["A"] * 11},
        {"country_groups": ["Spain", "Spain"]},
        {"country_groups": ["other"]},
        {"clean_manifest_sha256": "0" * 64},
        {"clean_manifest_sha256": "Z" * 64},
        {"version": True},
        {"rows_per_split": {"train": 999, "validation": 8, "test": 8}},
        {"country_groups": ["France"]},
    ],
)
def test_train_refuses_forged_or_corrupt_transform_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_override: dict[str, Any]
) -> None:
    data_dir = tmp_path / "data"
    _write_synthetic_transform_fixture(data_dir, manifest_overrides=bad_override)
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(data_dir))

    result = runner.invoke(app, ["train"])

    assert result.exit_code == 1
    assert "train failed:" in result.output


def test_train_refuses_non_object_json_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    _write_synthetic_transform_fixture(data_dir)
    (data_dir / "transform" / "_transform.json").write_text("[1, 2, 3]\n", encoding="utf-8")
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(data_dir))

    result = runner.invoke(app, ["train"])

    assert result.exit_code == 1
    assert "train failed:" in result.output
