"""Verified artifact loader enforcing the ARCHITECTURE.md section 4.3 contract.

Input: `run_id`, caller-supplied `expected_sha256` mapping, and optional `artifacts_dir`.
Output: a `LoadedArtifacts` instance, or `ArtifactError` / `ArtifactVersionError`.
Responsibility: validate `run_id` and path containment, fail closed on `expected_sha256`, verify
each file's SHA-256 once in memory before parsing JSON or unpickling from `io.BytesIO`, and refuse
any schema or seven-package serialization-stack version mismatch before unpickling.
"""

from __future__ import annotations

import io
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import joblib

from delphos_ml.artifacts._verification import (
    BUNDLE_JOBLIB_FILES,
    RUN_ID_PATTERN,
    SHA256_HEX_PATTERN,
    read_verified_bytes,
    verify_versions,
)
from delphos_ml.artifacts.errors import ArtifactError
from delphos_ml.artifacts.loaded_artifacts import LoadedArtifacts
from delphos_ml.config import find_project_root


def _resolve_artifacts_dir(artifacts_dir: Path | None) -> Path:
    if artifacts_dir is not None:
        try:
            return artifacts_dir.expanduser().resolve()
        except (RuntimeError, OSError) as exc:
            raise ArtifactError(f"could not resolve artifacts_dir {artifacts_dir}: {exc}") from exc
    project_root = find_project_root()
    if project_root is None:
        raise ArtifactError(
            "cannot resolve default artifacts directory without uv.lock; pass artifacts_dir"
        )
    try:
        return (project_root.parent / "artifacts").resolve()
    except OSError as exc:
        raise ArtifactError(f"could not resolve default artifacts directory: {exc}") from exc


def load_model(
    run_id: str,
    *,
    expected_sha256: Mapping[str, str] | None = None,
    artifacts_dir: Path | None = None,
) -> LoadedArtifacts:
    """Load and verify the artifact bundle for `run_id` without TOCTOU races."""
    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ArtifactError(f"invalid model_run_id {run_id!r}: must match ^[A-Za-z0-9_-]{{1,64}}$")
    required_files = {"manifest.json", *BUNDLE_JOBLIB_FILES}
    if not isinstance(expected_sha256, Mapping) or set(expected_sha256) != required_files:
        raise ArtifactError(
            "expected_sha256 must map manifest.json and every bundle .joblib file to hex digests"
        )
    for name, digest in expected_sha256.items():
        if not isinstance(digest, str) or SHA256_HEX_PATTERN.fullmatch(digest) is None:
            raise ArtifactError(f"expected_sha256[{name!r}] is not a lowercase 64-hex SHA-256")

    root = _resolve_artifacts_dir(artifacts_dir)
    bundle_dir = (root / run_id).resolve()
    if bundle_dir.parent != root or not bundle_dir.is_dir():
        raise ArtifactError(f"artifact directory for {run_id!r} not found inside {root}")

    manifest_buf = read_verified_bytes(
        bundle_dir, "manifest.json", expected_sha256["manifest.json"]
    )
    try:
        manifest = json.loads(manifest_buf.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"malformed manifest.json: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ArtifactError("manifest.json top-level value must be a JSON object")
    schema_ver = manifest.get("schema_version")
    if isinstance(schema_ver, bool) or schema_ver != 1:
        raise ArtifactError(f"unsupported manifest schema_version {schema_ver!r}; expected 1")
    if manifest.get("model_run_id") != run_id:
        raise ArtifactError(
            f"manifest model_run_id {manifest.get('model_run_id')!r} does not match {run_id!r}"
        )
    files = manifest.get("files")
    if not isinstance(files, list) or tuple(files) != BUNDLE_JOBLIB_FILES:
        raise ArtifactError("manifest files list does not match the expected artifact bundle")
    verify_versions(manifest.get("versions"))

    loaded: dict[str, Any] = {}
    for filename in BUNDLE_JOBLIB_FILES:
        payload_buf = read_verified_bytes(bundle_dir, filename, expected_sha256[filename])
        loaded[filename] = joblib.load(io.BytesIO(payload_buf))

    return LoadedArtifacts(
        model_run_id=run_id,
        manifest=manifest,
        preprocessor=loaded["preprocessor.joblib"],
        model=loaded["model.joblib"],
        polynomial_preprocessor=loaded["polynomial_preprocessor.joblib"],
        polynomial_model=loaded["polynomial_model.joblib"],
        cluster_preprocessor=loaded["cluster_preprocessor.joblib"],
        kmeans_model=loaded["kmeans_model.joblib"],
        classifier_preprocessor=loaded["classifier_preprocessor.joblib"],
        decision_tree_model=loaded["decision_tree_model.joblib"],
        random_forest_model=loaded["random_forest_model.joblib"],
    )
