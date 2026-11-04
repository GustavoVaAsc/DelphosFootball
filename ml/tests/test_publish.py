"""Unit tests for the publish stage and publish/activation protocol."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import joblib
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner

from delphos_ml.artifacts._verification import (
    BUNDLE_JOBLIB_FILES,
    collect_runtime_versions,
)
from delphos_ml.artifacts.loader import load_model
from delphos_ml.config import Settings
from delphos_ml.pipeline._publish_artifacts import (
    promote_artifacts,
    sanitize_model_run_id,
)
from delphos_ml.pipeline._publish_db import verify_published_counts
from delphos_ml.pipeline.cli import app
from delphos_ml.pipeline.publish import PublishError, run_publish


def test_sanitize_model_run_id_valid() -> None:
    assert sanitize_model_run_id("custom_run_123", "abc123456789") == "custom_run_123"
    assert sanitize_model_run_id("v1-alpha_42", "abc123456789") == "v1-alpha_42"


def test_sanitize_model_run_id_auto_generation() -> None:
    slug = sanitize_model_run_id(None, "d41d8cd98f00b204e9800998ecf8427e")
    assert slug.startswith("run_")
    assert "d41d8cd98f00" in slug
    assert len(slug) <= 64


@pytest.mark.parametrize(
    "invalid_id",
    [
        "../path_traversal",
        "has spaces",
        "bad/slash",
        "semi;colon",
        "a" * 65,  # too long
        "",  # empty
    ],
)
def test_sanitize_model_run_id_rejects_invalid(invalid_id: str) -> None:
    with pytest.raises(ValueError, match="invalid model_run_id"):
        sanitize_model_run_id(invalid_id, "d41d8cd98f00")


def test_promote_artifacts_full_bundle_and_updates_manifest(tmp_path: Path) -> None:
    staged = tmp_path / "staged"
    staged.mkdir()

    # Create dummy joblib objects for all 9 required bundle files
    for fname in BUNDLE_JOBLIB_FILES:
        joblib.dump({"name": fname}, staged / fname)

    # Create manifest with staged model_run_id and runtime versions
    manifest_data = {
        "schema_version": 1,
        "model_run_id": "staged",
        "files": list(BUNDLE_JOBLIB_FILES),
        "versions": collect_runtime_versions(),
    }
    (staged / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

    artifacts_root = tmp_path / "artifacts"
    run_id = "run_20261104_abcdef123456"
    dest = artifacts_root / run_id

    hashes = promote_artifacts(staged, dest, run_id)

    # Verify all 10 files promoted and hashed
    assert len(hashes) == 10
    assert "manifest.json" in hashes
    for fname in BUNDLE_JOBLIB_FILES:
        assert fname in hashes
        assert (dest / fname).is_file()

    # Verify manifest was updated with model_run_id
    promoted_manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    assert promoted_manifest["model_run_id"] == run_id

    # Verify that the bundle can be loaded and verified cleanly by delphos_ml.artifacts.load_model
    loaded = load_model(run_id, expected_sha256=hashes, artifacts_dir=artifacts_root)
    assert loaded.model_run_id == run_id
    assert loaded.model is not None
    assert loaded.preprocessor is not None


def test_promote_artifacts_missing_file_raises(tmp_path: Path) -> None:
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "model.joblib").write_bytes(b"model")
    # missing other 8 joblibs and manifest.json

    dest = tmp_path / "artifacts" / "test_run"
    with pytest.raises(FileNotFoundError, match="staged artifact missing"):
        promote_artifacts(staged, dest, "test_run")


def test_verify_published_counts() -> None:
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # 1. Matching counts pass
    mock_cur.fetchone.return_value = (42,)
    verify_published_counts(mock_conn, "run_001", {"dim_players": 42})

    # 2. Mismatched counts raise ValueError
    mock_cur.fetchone.return_value = (40,)
    with pytest.raises(ValueError, match="count mismatch on analytics.dim_players"):
        verify_published_counts(mock_conn, "run_001", {"dim_players": 42})


def test_publish_corrupt_manifest_raises(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    evaluate_dir = data_dir / "evaluate"
    evaluate_dir.mkdir(parents=True)
    (evaluate_dir / "_evaluate.json").write_text("invalid json {", encoding="utf-8")

    settings = Settings(data_dir=data_dir, artifacts_dir=tmp_path / "artifacts")
    with pytest.raises(PublishError, match="corrupt manifest"):
        run_publish(settings)


def test_publish_transaction_executes_and_activates(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    evaluate_dir = data_dir / "evaluate"
    train_dir = data_dir / "train"
    transform_dir = data_dir / "transform"
    clean_dir = data_dir / "clean"
    for d in (evaluate_dir, train_dir, transform_dir, clean_dir):
        d.mkdir(parents=True)

    # Write realistic upstream manifests
    eval_m = {"version": 679, "source_snapshot_sha256": "snap123"}
    train_m = {"version": 679, "source_snapshot_sha256": "snap123"}
    trans_m = {"version": 679}
    clean_m = {"version": 679, "source_snapshot_sha256": "snap123"}

    (evaluate_dir / "_evaluate.json").write_text(json.dumps(eval_m), encoding="utf-8")
    (train_dir / "_train.json").write_text(json.dumps(train_m), encoding="utf-8")
    (transform_dir / "_transform.json").write_text(json.dumps(trans_m), encoding="utf-8")
    (clean_dir / "_clean.json").write_text(json.dumps(clean_m), encoding="utf-8")

    # Staged bundle with all required files
    staged = train_dir / "staged"
    staged.mkdir()
    for fname in BUNDLE_JOBLIB_FILES:
        (staged / fname).write_bytes(b"dummy_bytes")
    (staged / "manifest.json").write_text(json.dumps({"model_run_id": "staged"}), encoding="utf-8")

    # Write dummy parquets for all 10 required tables
    dummy_tables = {
        clean_dir / "players.parquet": pa.table({"player_id": [1], "name": ["Player 1"]}),
        clean_dir / "clubs.parquet": pa.table({"club_id": [10], "name": ["Club 10"]}),
        transform_dir / "player_seasons.parquet": pa.table({"player_id": [1], "season": [2025]}),
        train_dir / "player_predictions.parquet": pa.table({"player_id": [1], "season": [2025]}),
        train_dir / "clusters.parquet": pa.table({"player_id": [1], "season": [2025]}),
        train_dir / "transfer_predictions.parquet": pa.table(
            {"player_id": [1], "transfer_fee": [1e6]}
        ),
        evaluate_dir / "replacement_targets.parquet": pa.table({"player_id": [1]}),
        evaluate_dir / "replacements.parquet": pa.table({"target_player_id": [1], "rank": [1]}),
        evaluate_dir / "inefficiency_analysis.parquet": pa.table(
            {"scope": ["all"], "test_id": ["t1"]}
        ),
        evaluate_dir / "model_metrics.parquet": pa.table(
            {"scope": ["all"], "model": ["ols"], "metric": ["rmse"]}
        ),
    }
    for path, table in dummy_tables.items():
        pq.write_table(table, path)

    artifacts_root = tmp_path / "artifacts"
    settings = Settings(
        data_dir=data_dir,
        artifacts_dir=artifacts_root,
        model_run_id="test_run_001",
    )

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_copy = MagicMock()
    mock_cursor.copy.return_value.__enter__.return_value = mock_copy
    # Count verification returns 1 for each table
    mock_cursor.fetchone.return_value = (1,)

    with patch("psycopg.connect", return_value=mock_conn):
        manifest_path = run_publish(settings)

    assert manifest_path.is_file()
    assert manifest_path.name == "_publish.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["model_run_id"] == "test_run_001"
    assert manifest["status"] == "active"
    assert manifest["dataset_version"] == 679
    assert len(manifest["transform_manifest_sha256"]) == 64
    assert len(manifest["train_manifest_sha256"]) == 64
    assert len(manifest["evaluate_manifest_sha256"]) == 64
    assert len(manifest["artifact_files_sha256"]) == 10
    assert (artifacts_root / "test_run_001" / "model.joblib").is_file()


def test_publish_rolls_back_on_db_error_and_cleans_artifacts(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    evaluate_dir = data_dir / "evaluate"
    train_dir = data_dir / "train"
    transform_dir = data_dir / "transform"
    clean_dir = data_dir / "clean"
    for d in (evaluate_dir, train_dir, transform_dir, clean_dir):
        d.mkdir(parents=True)

    (evaluate_dir / "_evaluate.json").write_text("{}", encoding="utf-8")
    (train_dir / "_train.json").write_text("{}", encoding="utf-8")
    (transform_dir / "_transform.json").write_text("{}", encoding="utf-8")
    (clean_dir / "_clean.json").write_text("{}", encoding="utf-8")

    staged = train_dir / "staged"
    staged.mkdir()
    for fname in BUNDLE_JOBLIB_FILES:
        (staged / fname).write_bytes(b"bytes")
    (staged / "manifest.json").write_text("{}", encoding="utf-8")

    artifacts_root = tmp_path / "artifacts"
    settings = Settings(
        data_dir=data_dir,
        artifacts_dir=artifacts_root,
        model_run_id="failing_run_001",
    )

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.execute.side_effect = RuntimeError("Database connection severed!")

    with (
        patch("psycopg.connect", return_value=mock_conn),
        pytest.raises(PublishError, match="publication transaction failed"),
    ):
        run_publish(settings)

    # Verify that the target artifacts directory was cleaned up on failure
    assert not (artifacts_root / "failing_run_001").exists()


def test_cli_publish_runs_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    called = []
    monkeypatch.setattr(
        "delphos_ml.pipeline.publish.run_publish",
        lambda settings=None: called.append("publish"),
    )

    result = runner.invoke(app, ["publish"])
    assert result.exit_code == 0
    assert called == ["publish"]
