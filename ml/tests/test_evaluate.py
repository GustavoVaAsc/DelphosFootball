"""End-to-end, Holm-Bonferroni, replacement-contract, and leak-guard tests for `evaluate`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from tests.test_train import SNAPSHOT_SHA256, _write_synthetic_transform_fixture
from typer.testing import CliRunner

from delphos_ml.evaluation import (
    build_replacements,
    compute_scheme_metrics,
    holm_bonferroni,
    run_inefficiency_tests,
)
from delphos_ml.evaluation._calibration import classify_shortfall
from delphos_ml.evaluation._hypothesis_tests import (
    kruskal_rows,
    one_sample_rows,
    two_sample_rows,
)
from delphos_ml.evaluation.specs import (
    INEFFICIENCY_COLUMNS,
    MODEL_METRICS_COLUMNS,
    REPLACEMENT_COLUMNS,
    TARGET_COLUMNS,
)
from delphos_ml.pipeline._staging import _restore_candidate
from delphos_ml.pipeline.cli import app
from delphos_ml.pipeline.train import TRANSFER_PREDICTIONS_SCHEMA

runner = CliRunner()


def _prepare_trained_fixture(
    data_dir: Path,
    *,
    val_test_mv_scale: float = 1.0,
    manifest_overrides: dict[str, Any] | None = None,
) -> None:
    _write_synthetic_transform_fixture(
        data_dir, val_test_mv_scale=val_test_mv_scale, manifest_overrides=manifest_overrides
    )
    res = runner.invoke(app, ["train"], env={"DELPHOS_DATA_DIR": str(data_dir)})
    assert res.exit_code == 0, res.output


def test_holm_bonferroni_enforces_step_down_monotonicity_and_preserves_order() -> None:
    # Sorted raw: 0.015 (x3=0.045), 0.020 (x2=0.040 -> monotone 0.045), 0.040 (x1=0.040 -> 0.045).
    raw = np.array([0.040, 0.015, 0.020], dtype="float64")
    adj = holm_bonferroni(raw)
    np.testing.assert_allclose(adj, np.array([0.045, 0.045, 0.045]))

    distinct = np.array([0.020, 0.001, 0.200, 0.012], dtype="float64")
    # Sorted: 0.001*4=0.004, 0.012*3=0.036, 0.020*2=0.040, 0.200*1=0.200
    np.testing.assert_allclose(holm_bonferroni(distinct), np.array([0.040, 0.004, 0.200, 0.036]))
    assert holm_bonferroni(np.array([], dtype="float64")).size == 0


def test_classify_shortfall_covers_all_bottleneck_codes() -> None:
    assert classify_shortfall(5, 4, 3, 3) is None
    assert classify_shortfall(0, 0, 0, 0) == "no_same_cluster_and_position_peer"
    assert classify_shortfall(4, 0, 0, 0) == "no_peer_within_athletic_distance"
    assert classify_shortfall(4, 2, 0, 0) == "no_peer_below_cost_ceiling"
    assert classify_shortfall(4, 2, 2, 0) == "no_non_overvalued_peer"
    assert classify_shortfall(4, 3, 3, 2) == "fewer_than_three_qualifying_peers"


def test_build_replacements_tie_breaks_by_distance_then_residual_then_player_id() -> None:
    class _IdentityPreprocessor:
        def transform(self, df: pd.DataFrame) -> np.ndarray:
            return df[["feat_x", "feat_y"]].to_numpy(dtype="float64")

    # Train split establishes generous distance ceiling (pairs at distance 5.0 -> P25 = 5.0).
    rows_ps = [
        {
            "player_id": 1,
            "season": 2020,
            "split": "train",
            "position": "Attack",
            "feat_x": 0.0,
            "feat_y": 0.0,
        },
        {
            "player_id": 2,
            "season": 2020,
            "split": "train",
            "position": "Attack",
            "feat_x": 5.0,
            "feat_y": 0.0,
        },
        {
            "player_id": 100,
            "season": 2025,
            "split": "test",
            "position": "Attack",
            "feat_x": 0.0,
            "feat_y": 0.0,
        },
        {
            "player_id": 30,
            "season": 2025,
            "split": "test",
            "position": "Attack",
            "feat_x": 1.0,
            "feat_y": 0.0,
        },
        {
            "player_id": 20,
            "season": 2025,
            "split": "test",
            "position": "Attack",
            "feat_x": 1.0,
            "feat_y": 0.0,
        },
        {
            "player_id": 10,
            "season": 2025,
            "split": "test",
            "position": "Attack",
            "feat_x": 1.0,
            "feat_y": 0.0,
        },
    ]
    rows_pr = [
        {
            "player_id": 1,
            "season": 2020,
            "split": "train",
            "market_value_eur": 10e6,
            "fair_value_eur": 10e6,
            "residual_log10": 0.0,
            "valuation_status": "fair",
        },
        {
            "player_id": 2,
            "season": 2020,
            "split": "train",
            "market_value_eur": 2e6,
            "fair_value_eur": 2e6,
            "residual_log10": 0.0,
            "valuation_status": "fair",
        },
        {
            "player_id": 100,
            "season": 2025,
            "split": "test",
            "market_value_eur": 10e6,
            "fair_value_eur": 10e6,
            "residual_log10": 0.0,
            "valuation_status": "fair",
        },
        # Candidates 10, 20, 30 sit at distance 1.0 and cost <= 8.0M:
        # 30 has residual 0.50 (rank 1); 10 and 20 tie at 0.20 -> 10 before 20.
        {
            "player_id": 30,
            "season": 2025,
            "split": "test",
            "market_value_eur": 5e6,
            "fair_value_eur": 15e6,
            "residual_log10": 0.50,
            "valuation_status": "undervalued",
        },
        {
            "player_id": 20,
            "season": 2025,
            "split": "test",
            "market_value_eur": 5e6,
            "fair_value_eur": 8e6,
            "residual_log10": 0.20,
            "valuation_status": "fair",
        },
        {
            "player_id": 10,
            "season": 2025,
            "split": "test",
            "market_value_eur": 5e6,
            "fair_value_eur": 8e6,
            "residual_log10": 0.20,
            "valuation_status": "fair",
        },
    ]
    rows_cl = [
        {"player_id": r["player_id"], "season": r["season"], "split": r["split"], "cluster_id": 0}
        for r in rows_ps
    ]
    _, repl_df, _, _, _ = build_replacements(
        pd.DataFrame(rows_ps),
        pd.DataFrame(rows_pr).sample(frac=1.0, random_state=7),
        pd.DataFrame(rows_cl).sample(frac=1.0, random_state=11),
        cluster_preprocessor=_IdentityPreprocessor(),
    )
    sub = repl_df[repl_df["target_player_id"] == 100].sort_values("rank")
    assert sub["candidate_player_id"].tolist() == [30, 10, 20]


def test_evaluate_produces_inefficiency_replacements_metrics_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    _prepare_trained_fixture(data_dir)
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(data_dir))

    assert runner.invoke(app, ["evaluate"]).exit_code == 0
    result = runner.invoke(app, ["evaluate"])
    assert result.exit_code == 0, result.output
    assert list(data_dir.glob(".evaluate-*")) == []

    eval_dir = data_dir / "evaluate"
    manifest = json.loads((eval_dir / "_evaluate.json").read_text(encoding="utf-8"))
    assert manifest["source_snapshot_sha256"] == SNAPSHOT_SHA256
    assert manifest["active_replacement_season"] == 2025

    ineff = pd.read_parquet(eval_dir / "inefficiency_analysis.parquet")
    targets = pd.read_parquet(eval_dir / "replacement_targets.parquet")
    repl = pd.read_parquet(eval_dir / "replacements.parquet")
    metrics = pd.read_parquet(eval_dir / "model_metrics.parquet")

    assert set(ineff["scope"]) == {"train_validation", "test", "all"}
    b5_test = ineff[
        (ineff["scope"] == "all") & (ineff["test_id"] == "kruskal_big5_vs_non_big5")
    ].iloc[0]
    assert b5_test["n_primary"] + b5_test["n_secondary"] == 10
    cv_rows = [r for r in metrics.to_dict(orient="records") if r["scope"].startswith("cv_")]
    assert len(cv_rows) > 0
    assert any(r["se"] is not None and r["se"] > 0 for r in cv_rows)
    for _scope, grp in ineff.groupby("scope"):
        assert len(grp) == 6
        valid_p = (grp["p_value_holm"] >= grp["p_value"] - 1e-15) & (grp["p_value_holm"] <= 1.0)
        assert valid_p.all()
        assert (grp["reject_null"] == (grp["p_value_holm"] < grp["alpha"])).all()

    assert len(targets) == 8
    for row in targets.itertuples(index=False):
        cands = repl[repl["target_player_id"] == row.player_id].sort_values("rank")
        assert len(cands) == row.qualifying_count
        assert 0 <= len(cands) <= 3
        if len(cands) == 3:
            assert row.shortfall_reason is None or pd.isna(row.shortfall_reason)
        else:
            assert isinstance(row.shortfall_reason, str) and len(row.shortfall_reason) > 0
        if not cands.empty:
            assert list(cands["rank"]) == list(range(1, len(cands) + 1))
            assert (cands["candidate_player_id"] != row.player_id).all()
            assert (cands["cluster_id"] == row.cluster_id).all()
            assert (cands["position"] == row.position).all()
            assert (cands["euclidean_distance"] <= row.distance_ceiling + 1e-12).all()
            assert (cands["candidate_market_value_eur"] <= 0.80 * row.market_value_eur + 1e-9).all()
            assert (cands["candidate_valuation_status"] != "overvalued").all()
            sims = cands["similarity_score"].tolist()
            assert sims == sorted(sims, reverse=True)

    assert set(metrics["model"]) == {
        "linear_regression",
        "polynomial_regression",
        "decision_tree",
        "random_forest",
        "kmeans",
    }
    assert {"validation", "test"}.issubset(set(metrics["scope"]))


def test_evaluate_leak_guard_test_split_never_moves_elite_or_distance_thresholds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dir_a = tmp_path / "eval_a"
    dir_b = tmp_path / "eval_b"
    _prepare_trained_fixture(dir_a, val_test_mv_scale=1.0)
    _prepare_trained_fixture(dir_b, val_test_mv_scale=25.0)

    monkeypatch.setenv("DELPHOS_DATA_DIR", str(dir_a))
    assert runner.invoke(app, ["evaluate"]).exit_code == 0
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(dir_b))
    assert runner.invoke(app, ["evaluate"]).exit_code == 0

    man_a = json.loads((dir_a / "evaluate" / "_evaluate.json").read_text(encoding="utf-8"))
    man_b = json.loads((dir_b / "evaluate" / "_evaluate.json").read_text(encoding="utf-8"))
    assert man_a["elite_thresholds_eur"] == man_b["elite_thresholds_eur"]
    assert man_a["athletic_distance_ceilings"] == man_b["athletic_distance_ceilings"]


def test_evaluate_refuses_missing_or_tampered_train_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    _prepare_trained_fixture(data_dir)
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(data_dir))

    train_man_path = data_dir / "train" / "_train.json"
    orig_text = train_man_path.read_text(encoding="utf-8")
    train_man = json.loads(orig_text)
    train_man["transform_manifest_sha256"] = "0" * 64
    train_man_path.write_text(json.dumps(train_man, indent=2) + "\n", encoding="utf-8")

    result = runner.invoke(app, ["evaluate"])
    assert result.exit_code == 1
    assert "evaluate failed:" in result.output

    # Restore provenance, then corrupt q25 > q75 threshold.
    bad_thresh = json.loads(orig_text)
    bad_thresh["thresholds"]["q25_overvalued_log10"] = 0.90
    bad_thresh["thresholds"]["q75_undervalued_log10"] = -0.10
    train_man_path.write_text(json.dumps(bad_thresh, indent=2) + "\n", encoding="utf-8")
    res_thresh = runner.invoke(app, ["evaluate"])
    assert res_thresh.exit_code == 1
    assert "q25_overvalued_log10 exceeds q75_undervalued_log10" in res_thresh.output


def test_matched_rank_biserial_and_signed_rank_biserial_closed_form() -> None:
    # 1-sample: all positive differences -> ranks 1, 2, 3 -> matched_rb = +1.0
    pos_rows = one_sample_rows("scope", np.array([1.0, 2.0, 3.0]))
    assert pos_rows[1]["effect_size"] == 1.0
    # all negative -> matched_rb = -1.0
    neg_rows = one_sample_rows("scope", np.array([-3.0, -2.0, -1.0]))
    assert neg_rows[1]["effect_size"] == -1.0

    # 2-sample: under < over -> signed rank_biserial must be negative (-1.0)
    u_small = np.array([1.0, 2.0])
    o_large = np.array([10.0, 20.0])
    res_neg = two_sample_rows("scope", u_small, o_large)
    assert res_neg[0]["effect_size"] == -1.0
    assert res_neg[1]["statistic"] < 0  # Welch t is negative

    # under > over -> signed rank_biserial must be positive (+1.0)
    res_pos = two_sample_rows("scope", o_large, u_small)
    assert res_pos[0]["effect_size"] == 1.0
    assert res_pos[1]["statistic"] > 0


def test_kruskal_rows_guards_constant_and_all_tied_inputs() -> None:
    gap = np.array([5.0, 5.0, 5.0, 5.0])
    b5 = np.array([5.0, 5.0])
    nb5 = np.array([5.0, 5.0])
    cl_groups = [np.array([5.0, 5.0]), np.array([5.0, 5.0])]
    rows = kruskal_rows("scope", gap, b5, nb5, cl_groups)
    assert len(rows) == 2
    for r in rows:
        assert r["statistic"] == 0.0
        assert r["p_value"] == 1.0
        assert r["effect_size"] == 0.0


def test_empty_dataframes_preserve_all_schema_columns() -> None:
    empty_tr = pd.DataFrame(columns=TRANSFER_PREDICTIONS_SCHEMA.names)
    ineff_empty = run_inefficiency_tests(empty_tr, q25=-0.3, q75=0.3)
    assert list(ineff_empty.columns) == list(INEFFICIENCY_COLUMNS)

    empty_ps = pd.DataFrame(
        columns=["player_id", "season", "split", "position", "log10_market_value"]
    )
    empty_pr = pd.DataFrame(
        columns=[
            "player_id",
            "season",
            "split",
            "market_value_eur",
            "fair_value_eur",
            "residual_log10",
            "valuation_status",
        ]
    )
    empty_cl = pd.DataFrame(columns=["player_id", "season", "split", "cluster_id"])

    class _DummyPrep:
        def transform(self, df: pd.DataFrame) -> np.ndarray:
            return np.empty((len(df), 2))

    t_df, r_df, _, _, _ = build_replacements(
        empty_ps, empty_pr, empty_cl, cluster_preprocessor=_DummyPrep()
    )
    assert list(t_df.columns) == list(TARGET_COLUMNS)
    assert list(r_df.columns) == list(REPLACEMENT_COLUMNS)

    class _DummyBundle:
        cluster_preprocessor = _DummyPrep()

    metrics_empty = compute_scheme_metrics(
        empty_ps,
        empty_pr,
        empty_cl,
        _DummyBundle(),
        empirical_bayes_m=5.0,
        prior_grouping="position",
    )
    assert list(metrics_empty.columns) == list(MODEL_METRICS_COLUMNS)


def test_evaluate_corrupt_parquet_and_evaluated_at_staging_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    _prepare_trained_fixture(data_dir)
    monkeypatch.setenv("DELPHOS_DATA_DIR", str(data_dir))

    # Corrupt player_predictions.parquet
    preds_path = data_dir / "train" / "player_predictions.parquet"
    preds_path.write_bytes(b"NOT_A_PARQUET_FILE")
    res = runner.invoke(app, ["evaluate"])
    assert res.exit_code == 1
    assert "evaluate failed:" in res.output

    # Test _restore_candidate recognizes evaluated_at in leftover retired directory
    retired_dir = data_dir / ".evaluate-retired-candidate"
    retired_dir.mkdir(parents=True, exist_ok=True)
    for tbl in ("inefficiency_analysis", "replacement_targets", "replacements", "model_metrics"):
        (retired_dir / f"{tbl}.parquet").write_bytes(b"placeholder")
    test_manifest = {
        "evaluated_at": "2026-11-03T19:00:00Z",
        "tables": {
            "inefficiency_analysis": {"parquet_file": "inefficiency_analysis.parquet"},
            "replacement_targets": {"parquet_file": "replacement_targets.parquet"},
            "replacements": {"parquet_file": "replacements.parquet"},
            "model_metrics": {"parquet_file": "model_metrics.parquet"},
        },
    }
    (retired_dir / "_evaluate.json").write_text(json.dumps(test_manifest), encoding="utf-8")
    cand = _restore_candidate(
        [retired_dir],
        manifest_file_name="_evaluate.json",
        expected_table_names={
            "inefficiency_analysis",
            "replacement_targets",
            "replacements",
            "model_metrics",
        },
    )
    assert cand == retired_dir
