"""Exceptions raised by artifact validation and loading.

Input: failure reason strings from `delphos_ml.artifacts.loader`.
Output: `ArtifactError` and its version-mismatch subclass `ArtifactVersionError`.
Responsibility: give callers (notably the FastAPI backend's RFC 9457 problem mapper in
docs/ARCHITECTURE.md section 9) distinct exception types for missing/tampered artifacts versus
stale runtime versions. Both classes are tiny domain markers and stay in one module.
"""

from __future__ import annotations


class ArtifactError(Exception):
    """An artifact bundle is missing, malformed, or failed SHA-256 verification."""


class ArtifactVersionError(ArtifactError):
    """An artifact's recorded serialization-stack versions differ from the installed ones."""
