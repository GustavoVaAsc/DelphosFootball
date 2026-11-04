"""Artifact promotion and model_run_id validation for the publish stage.

Input: staged artifacts in `ml/data/train/staged/` and target run directory.
Output: promoted artifacts in `artifacts/<model_run_id>/` and SHA-256 digests.
Responsibility: verifies and copies all bundle artifacts and manifest to the publish root.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from delphos_ml.artifacts._verification import BUNDLE_JOBLIB_FILES

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
REQUIRED_ARTIFACT_FILES: tuple[str, ...] = (*BUNDLE_JOBLIB_FILES, "manifest.json")


def sanitize_model_run_id(run_id: str | None, evaluate_hash: str) -> str:
    """Validate or generate a safe model_run_id slug matching `^[A-Za-z0-9_-]{1,64}$`."""
    if run_id is not None:
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError(
                f"invalid model_run_id '{run_id}': must match pattern ^[A-Za-z0-9_-]{{1,64}}$"
            )
        return run_id

    # Auto-generate a deterministic timestamped slug
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    digest_prefix = evaluate_hash[:12] if evaluate_hash else "000000000000"
    slug = f"run_{ts}_{digest_prefix}"
    return slug[:64]


def _hash_file(path: Path) -> str:
    """Compute lowercase hex SHA-256 of file bytes."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def promote_artifacts(staged_dir: Path, target_dir: Path, model_run_id: str) -> dict[str, str]:
    """Copy staged model artifacts to target directory, update manifest, and return digests.

    Raises FileNotFoundError if any required artifact is missing from staged_dir.
    """
    for fname in REQUIRED_ARTIFACT_FILES:
        src = staged_dir / fname
        if not src.is_file():
            raise FileNotFoundError(f"staged artifact missing: {src}")

    target_dir.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}

    # 1. Copy all joblib model and preprocessor artifacts
    for fname in BUNDLE_JOBLIB_FILES:
        src = staged_dir / fname
        dest = target_dir / fname
        shutil.copy2(src, dest)
        digests[fname] = _hash_file(dest)

    # 2. Update manifest.json with the active model_run_id and save to target_dir
    manifest_raw = json.loads((staged_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_raw["model_run_id"] = model_run_id
    manifest_dest = target_dir / "manifest.json"
    manifest_dest.write_text(json.dumps(manifest_raw, indent=2), encoding="utf-8")
    digests["manifest.json"] = _hash_file(manifest_dest)

    return digests
