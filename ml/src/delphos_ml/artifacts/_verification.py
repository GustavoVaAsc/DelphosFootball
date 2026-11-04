"""Integrity and runtime-version checks for `delphos_ml.artifacts.loader`.

Input: artifact directory paths, caller-supplied SHA-256 hex digests, and `manifest.json` metadata.
Output: verified in-memory byte buffers and exact runtime package version dictionaries.
Responsibility: centralize constant-time SHA-256 verification and the seven-package version match
required before any `joblib.load()` unpickle. Kept in one module because byte-level hashing and
version gating together form the pre-unpickle trust boundary.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path
from typing import Any

from delphos_ml.artifacts.errors import ArtifactError, ArtifactVersionError

RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
SHA256_HEX_PATTERN = re.compile(r"[0-9a-f]{64}")

MANIFEST_VERSION_KEY_MAP: dict[str, str] = {
    "scikit-learn": "scikit-learn",
    "joblib": "joblib",
    "cloudpickle": "cloudpickle",
    "numpy": "numpy",
    "scipy": "scipy",
    "threadpoolctl": "threadpoolctl",
    "delphos_ml": "delphos-ml",
}

BUNDLE_JOBLIB_FILES: tuple[str, ...] = (
    "preprocessor.joblib",
    "model.joblib",
    "polynomial_preprocessor.joblib",
    "polynomial_model.joblib",
    "cluster_preprocessor.joblib",
    "kmeans_model.joblib",
    "classifier_preprocessor.joblib",
    "decision_tree_model.joblib",
    "random_forest_model.joblib",
)


def collect_runtime_versions() -> dict[str, str]:
    """Return the exact installed versions of the seven artifact-contract packages."""
    return {key: version(dist) for key, dist in MANIFEST_VERSION_KEY_MAP.items()}


def read_verified_bytes(bundle_dir: Path, filename: str, expected_digest: str) -> bytes:
    """Read `bundle_dir / filename` once into memory and verify its SHA-256 digest."""
    target = (bundle_dir / filename).resolve()
    if target.parent != bundle_dir or not target.is_file():
        raise ArtifactError(f"missing or escaped artifact file: {filename}")
    try:
        buffer = target.read_bytes()
    except OSError as exc:
        raise ArtifactError(f"could not read {filename}: {exc}") from exc
    actual = hashlib.sha256(buffer).hexdigest()
    if not hmac.compare_digest(actual, expected_digest):
        raise ArtifactError(
            f"SHA-256 mismatch for {filename}: expected {expected_digest}, got {actual}"
        )
    return buffer


def verify_versions(recorded: Any) -> None:
    """Refuse loading if any recorded serialization-stack version differs from runtime."""
    if not isinstance(recorded, Mapping):
        raise ArtifactError("manifest.json versions field must be a JSON object")
    installed = collect_runtime_versions()
    mismatches = [
        f"{key} (artifact={recorded.get(key)!r}, installed={installed_ver!r})"
        for key, installed_ver in installed.items()
        if recorded.get(key) != installed_ver
    ]
    if mismatches:
        raise ArtifactVersionError(f"artifact version mismatch: {', '.join(mismatches)}")
