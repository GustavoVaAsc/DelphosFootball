"""Unit tests for the `delphos_ml.load_model()` artifact contract (ARCHITECTURE.md section 4.3)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import pytest
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.preprocessing import StandardScaler

from delphos_ml import load_model
from delphos_ml.artifacts import (
    BUNDLE_JOBLIB_FILES,
    ArtifactError,
    ArtifactVersionError,
    collect_runtime_versions,
)


def _raise_if_called(msg: str) -> None:
    raise AssertionError(msg)


class _UnpickleBomb:
    """Triggers `_raise_if_called` at unpickle time, not at dump time."""

    def __reduce__(self) -> tuple[Any, tuple[str]]:
        return (_raise_if_called, ("joblib.load executed on an unverified/mismatched bundle!",))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_valid_bundle(
    root: Path,
    run_id: str = "run_2026_11_03",
    *,
    versions_override: dict[str, str] | None = None,
    payload_override: Any | None = None,
    manifest_override: Any | None = None,
) -> dict[str, str]:
    bundle = root / run_id
    bundle.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}

    objects: dict[str, Any] = {
        "preprocessor.joblib": StandardScaler(),
        "model.joblib": DummyRegressor(),
        "polynomial_preprocessor.joblib": StandardScaler(),
        "polynomial_model.joblib": DummyRegressor(),
        "cluster_preprocessor.joblib": StandardScaler(),
        "kmeans_model.joblib": DummyClassifier(),
        "classifier_preprocessor.joblib": StandardScaler(),
        "decision_tree_model.joblib": DummyClassifier(),
        "random_forest_model.joblib": DummyClassifier(),
    }
    if payload_override is not None:
        objects["model.joblib"] = payload_override

    for filename in BUNDLE_JOBLIB_FILES:
        target = bundle / filename
        joblib.dump(objects[filename], target)
        digests[filename] = _sha256_bytes(target.read_bytes())

    versions = collect_runtime_versions()
    if versions_override:
        versions.update(versions_override)

    manifest: Any = {
        "schema_version": 1,
        "model_run_id": run_id,
        "created_at": "2026-11-03T18:30:00Z",
        "dataset": {
            "handle": "davidcariboo/player-scores",
            "version": 679,
            "snapshot_sha256": "94f42930f5d50d76f5226f64bd2b9e4c70552e110ad28743b5edce4041c8b1c1",
        },
        "versions": versions,
        "files": list(BUNDLE_JOBLIB_FILES),
        "champion_regressor": "linear_regression",
        "champion_classifier": "random_forest",
        "feature_names": ["f1", "f2"],
        "feature_sets": {},
        "thresholds": {
            "q25_overvalued_log10": -0.345,
            "q75_undervalued_log10": 0.2735,
            "oof_seasons": [2018, 2019, 2020, 2021, 2022, 2023],
            "oof_rows": 31714,
        },
        "cluster_order": [],
        "training_config": {"empirical_bayes_m": 5},
    }
    if manifest_override is not None:
        if isinstance(manifest_override, dict):
            manifest.update(manifest_override)
        else:
            manifest = manifest_override
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    (bundle / "manifest.json").write_bytes(manifest_bytes)
    digests["manifest.json"] = _sha256_bytes(manifest_bytes)
    return digests


def test_load_model_round_trips_a_verified_bundle(tmp_path: Path) -> None:
    digests = _write_valid_bundle(tmp_path, "run_001")

    loaded = load_model("run_001", expected_sha256=digests, artifacts_dir=tmp_path)

    assert loaded.model_run_id == "run_001"
    assert loaded.manifest["dataset"]["version"] == 679
    assert isinstance(loaded.preprocessor, StandardScaler)
    assert isinstance(loaded.model, DummyRegressor)
    assert isinstance(loaded.random_forest_model, DummyClassifier)


@pytest.mark.parametrize(
    "bad_run_id",
    [
        "",
        "../escape",
        "run/sub",
        "run\\sub",
        "run_001\n",
        "run with spaces",
        "a" * 65,
        ".hidden",
    ],
)
def test_load_model_rejects_invalid_run_id_patterns(tmp_path: Path, bad_run_id: str) -> None:
    digests = _write_valid_bundle(tmp_path, "run_001")

    with pytest.raises(ArtifactError, match="invalid model_run_id"):
        load_model(bad_run_id, expected_sha256=digests, artifacts_dir=tmp_path)


def test_load_model_fails_closed_when_expected_sha256_is_absent_incomplete_or_non_hex(
    tmp_path: Path,
) -> None:
    digests = _write_valid_bundle(tmp_path, "run_001")

    with pytest.raises(ArtifactError, match="expected_sha256"):
        load_model("run_001", expected_sha256=None, artifacts_dir=tmp_path)
    with pytest.raises(ArtifactError, match="expected_sha256"):
        load_model("run_001", expected_sha256={}, artifacts_dir=tmp_path)

    partial = dict(digests)
    partial.pop("random_forest_model.joblib")
    with pytest.raises(ArtifactError, match="expected_sha256"):
        load_model("run_001", expected_sha256=partial, artifacts_dir=tmp_path)

    for bad_hex in ("ABCDEF" + "0" * 58, "z" * 64, "short"):
        with pytest.raises(ArtifactError, match="lowercase 64-hex"):
            load_model(
                "run_001",
                expected_sha256={**digests, "model.joblib": bad_hex},
                artifacts_dir=tmp_path,
            )


def test_load_model_rejects_tampered_manifest_or_model_bytes_without_unpickling(
    tmp_path: Path,
) -> None:
    digests = _write_valid_bundle(tmp_path, "run_001", payload_override=_UnpickleBomb())
    bad_digests = {**digests, "model.joblib": "0" * 64}
    with pytest.raises(ArtifactError, match="SHA-256 mismatch for model.joblib"):
        load_model("run_001", expected_sha256=bad_digests, artifacts_dir=tmp_path)

    (tmp_path / "run_001" / "manifest.json").write_text('{"tampered": true}\n', encoding="utf-8")
    with pytest.raises(ArtifactError, match="SHA-256 mismatch for manifest.json"):
        load_model("run_001", expected_sha256=digests, artifacts_dir=tmp_path)


@pytest.mark.parametrize(
    ("override", "match"),
    [
        (["not", "an", "object"], "top-level value must be a JSON object"),
        ({"schema_version": 2}, "unsupported manifest schema_version"),
        ({"schema_version": True}, "unsupported manifest schema_version"),
        ({"files": None}, "manifest files list"),
        ({"files": {name: 1 for name in BUNDLE_JOBLIB_FILES}}, "manifest files list"),
        ({"versions": ["bad"]}, "versions field must be a JSON object"),
    ],
)
def test_load_model_rejects_malformed_manifest_structure_before_unpickling(
    tmp_path: Path, override: Any, match: str
) -> None:
    digests = _write_valid_bundle(
        tmp_path, "run_bad", payload_override=_UnpickleBomb(), manifest_override=override
    )
    with pytest.raises(ArtifactError, match=match):
        load_model("run_bad", expected_sha256=digests, artifacts_dir=tmp_path)


@pytest.mark.parametrize(
    "pkg_key",
    [
        "scikit-learn",
        "joblib",
        "cloudpickle",
        "numpy",
        "scipy",
        "threadpoolctl",
        "delphos_ml",
    ],
)
def test_load_model_refuses_version_mismatch_before_unpickling_payload(
    tmp_path: Path, pkg_key: str
) -> None:
    digests = _write_valid_bundle(
        tmp_path,
        f"run_{pkg_key.replace('-', '_')}",
        versions_override={pkg_key: "0.0.0-mismatch"},
        payload_override=_UnpickleBomb(),
    )

    with pytest.raises(ArtifactVersionError, match=pkg_key):
        load_model(
            f"run_{pkg_key.replace('-', '_')}",
            expected_sha256=digests,
            artifacts_dir=tmp_path,
        )


def test_load_model_rejects_manifest_run_id_mismatch_and_missing_uv_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    digests = _write_valid_bundle(tmp_path, "run_001")
    (tmp_path / "run_001").rename(tmp_path / "run_002")

    with pytest.raises(ArtifactError, match="model_run_id"):
        load_model("run_002", expected_sha256=digests, artifacts_dir=tmp_path)

    isolated = tmp_path / "isolated_cwd"
    isolated.mkdir()
    monkeypatch.chdir(isolated)
    with pytest.raises(ArtifactError, match="uv.lock"):
        load_model("run_002", expected_sha256=digests)
