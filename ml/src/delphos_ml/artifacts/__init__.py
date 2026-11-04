"""Public facade for the artifact contract (`delphos_ml.artifacts`).

Input: none (re-export facade).
Output: `ArtifactError`, `ArtifactVersionError`, `BUNDLE_JOBLIB_FILES`, `LoadedArtifacts`,
`SHA256_HEX_PATTERN`, `collect_runtime_versions`, `load_model`, and `write_verified_bundle`.
Responsibility: expose the artifact loader, serializer, and error/result types from one path.
"""

from __future__ import annotations

from delphos_ml.artifacts._verification import (
    BUNDLE_JOBLIB_FILES,
    SHA256_HEX_PATTERN,
    collect_runtime_versions,
)
from delphos_ml.artifacts.errors import ArtifactError, ArtifactVersionError
from delphos_ml.artifacts.loaded_artifacts import LoadedArtifacts
from delphos_ml.artifacts.loader import load_model
from delphos_ml.artifacts.writer import write_verified_bundle

__all__ = [
    "ArtifactError",
    "ArtifactVersionError",
    "BUNDLE_JOBLIB_FILES",
    "LoadedArtifacts",
    "SHA256_HEX_PATTERN",
    "collect_runtime_versions",
    "load_model",
    "write_verified_bundle",
]
