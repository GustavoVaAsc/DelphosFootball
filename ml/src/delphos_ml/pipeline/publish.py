"""Pipeline stage: publish.

Input: outputs of evaluate, train, transform, and clean stages.
Output: promoted artifacts in `artifacts/<model_run_id>/`, rows in PostgreSQL `analytics`,
and `ml/data/publish/_publish.json`.
Responsibility: publishes analytical results and model artifacts transactionally.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

from delphos_ml.config import Settings, load_settings
from delphos_ml.pipeline._publish_artifacts import (
    _hash_file,
    promote_artifacts,
    sanitize_model_run_id,
)
from delphos_ml.pipeline._publish_db import bulk_load_analytics, verify_published_counts

logger = logging.getLogger(__name__)


class PublishError(Exception):
    """Raised when publication to database or artifact promotion fails."""


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublishError(f"missing upstream manifest: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("manifest is not a JSON object")
        return data
    except Exception as exc:
        raise PublishError(f"corrupt manifest {path}: {exc}") from exc


def run_publish(settings: Settings | None = None) -> Path:
    """Publish model artifacts and analytical results to PostgreSQL in a single transaction."""
    settings = settings or load_settings()
    data_dir = settings.data_dir
    publish_dir = data_dir / "publish"
    publish_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load upstream manifests and calculate provenance hashes
    clean_manifest_path = data_dir / "clean" / "_clean.json"
    trans_manifest_path = data_dir / "transform" / "_transform.json"
    train_manifest_path = data_dir / "train" / "_train.json"
    eval_manifest_path = data_dir / "evaluate" / "_evaluate.json"

    eval_m = _load_manifest(eval_manifest_path)
    train_m = _load_manifest(train_manifest_path)
    _ = _load_manifest(trans_manifest_path)
    clean_m = _load_manifest(clean_manifest_path)

    eval_sha = _hash_file(eval_manifest_path)
    train_sha = _hash_file(train_manifest_path)
    trans_sha = _hash_file(trans_manifest_path)

    dataset_snapshot = (
        eval_m.get("source_snapshot_sha256")
        or train_m.get("source_snapshot_sha256")
        or clean_m.get("source_snapshot_sha256", "")
    )
    dataset_version = eval_m.get("version") or train_m.get("version") or clean_m.get("version", 679)

    manifest_metadata = {
        "dataset_version": dataset_version,
        "dataset_snapshot_sha256": dataset_snapshot,
        "transform_manifest_sha256": trans_sha,
        "train_manifest_sha256": train_sha,
        "evaluate_manifest_sha256": eval_sha,
    }

    # 2. Validate model_run_id
    try:
        model_run_id = sanitize_model_run_id(
            settings.model_run_id,
            manifest_metadata["evaluate_manifest_sha256"],
        )
    except ValueError as exc:
        raise PublishError(str(exc)) from exc

    # 3. Promote staged artifacts
    staged_dir = data_dir / "train" / "staged"
    artifacts_root = settings.get_artifacts_dir()
    target_artifacts_dir = artifacts_root / model_run_id
    try:
        artifact_hashes = promote_artifacts(staged_dir, target_artifacts_dir, model_run_id)
    except Exception as exc:
        raise PublishError(f"failed promoting artifacts to {target_artifacts_dir}: {exc}") from exc

    # 4. Database bulk load and activation inside single transaction
    db_url = settings.get_database_url()
    try:
        with psycopg.connect(db_url) as conn:
            with conn.transaction():
                row_counts = bulk_load_analytics(
                    conn=conn,
                    model_run_id=model_run_id,
                    data_dir=data_dir,
                    manifests=manifest_metadata,
                    artifact_hashes=artifact_hashes,
                )
                verify_published_counts(conn, model_run_id, row_counts)
    except Exception as exc:
        shutil.rmtree(target_artifacts_dir, ignore_errors=True)
        raise PublishError(f"publication transaction failed: {exc}") from exc

    # 5. Write _publish.json atomically
    manifest = {
        "published_at": datetime.now(UTC).isoformat(),
        "model_run_id": model_run_id,
        "status": "active",
        **manifest_metadata,
        "artifact_files_sha256": artifact_hashes,
        "row_counts": row_counts,
    }
    manifest_bytes = json.dumps(manifest, indent=2, allow_nan=False).encode("utf-8")
    manifest_path = publish_dir / "_publish.json"
    tmp_path = publish_dir / "_publish.json.tmp"
    tmp_path.write_bytes(manifest_bytes)
    tmp_path.replace(manifest_path)

    logger.info("Published model_run_id=%s successfully", model_run_id)
    return manifest_path


def publish() -> None:
    """Publish model artifacts and analytical results to PostgreSQL in a single transaction."""
    import typer

    from delphos_ml.config import ConfigError

    try:
        run_publish()
    except (ConfigError, PublishError) as exc:
        logger.error("Publish stage failed: %s", exc)
        raise typer.Exit(code=1) from exc
