"""Unit tests for the shared staging-swap helpers: stage-name validation and recovery.

`clean` and `transform` both drive `_prepare_data_dir` / `_swap_in` with their own stage
name and error class, and those helpers splice the name into directory names, path joins
and cleanup globs. These tests pin the guard that refuses a name which is not a plain
lowercase identifier before it can escape `data/<stage>/`, and the interrupted-run
recovery that must pick the newest complete retired copy instead of crashing when two
copies report the same timestamp.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from delphos_ml.pipeline._staging import _prepare_data_dir, _restore_candidate, _swap_in

EXPECTED_TABLES = {"player_seasons", "transfer_events"}


class _StageError(Exception):
    """Stand-in for a stage's own error class (TransformError, CleanError, ...)."""


def _prepare(data_dir: Path, stage: str) -> None:
    _prepare_data_dir(
        data_dir,
        stage=stage,
        manifest_file_name="_transform.json",
        expected_table_names=EXPECTED_TABLES,
        error=_StageError,
    )


@pytest.mark.parametrize(
    "stage",
    ["..", "../outside", "a/b", "a*b", "a[b", "Transform", "", "with space", "transform\n"],
    ids=[
        "dotdot",
        "dotdot-prefix",
        "slash",
        "star",
        "bracket",
        "upper",
        "empty",
        "space",
        "trailing-nl",
    ],
)
def test_invalid_stage_names_are_refused_before_any_path_is_touched(
    tmp_path: Path, stage: str
) -> None:
    with pytest.raises(_StageError, match="invalid stage name"):
        _prepare(tmp_path, stage)

    # Validation runs first: no data directory was created and nothing was globbed away.
    assert list(tmp_path.iterdir()) == []


def test_swap_in_refuses_an_invalid_stage_name_and_moves_nothing(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    target = tmp_path / "target"
    staging.mkdir()
    target.mkdir()
    (staging / "_transform.json").write_text("{}", encoding="utf-8")
    (target / "_transform.json").write_text("{}", encoding="utf-8")

    with pytest.raises(_StageError, match="invalid stage name"):
        _swap_in(
            staging,
            target,
            stage="../evil",
            error=_StageError,
            rename_attempts=1,
            rename_delay_seconds=0.0,
        )

    assert (staging / "_transform.json").is_file()
    assert (target / "_transform.json").is_file()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["staging", "target"]


def _write_retired(directory: Path, cleaned_at: str) -> None:
    """Create one complete retired copy: manifest plus both parquet files."""
    directory.mkdir(parents=True)
    manifest = {
        "cleaned_at": cleaned_at,
        "tables": {
            "player_seasons": {"parquet_file": "player_seasons.parquet"},
            "transfer_events": {"parquet_file": "transfer_events.parquet"},
        },
    }
    (directory / "_transform.json").write_text(json.dumps(manifest), encoding="utf-8")
    for table in ("player_seasons", "transfer_events"):
        (directory / f"{table}.parquet").write_bytes(b"")


def test_restore_candidate_returns_a_copy_on_tied_timestamps(tmp_path: Path) -> None:
    """Equal `cleaned_at` values must pick a copy, not raise TypeError comparing Paths."""
    first = tmp_path / ".transform-retired-aaa"
    second = tmp_path / ".transform-retired-bbb"
    _write_retired(first, "2026-11-01T00:00:00Z")
    _write_retired(second, "2026-11-01T00:00:00Z")

    candidate = _restore_candidate(
        [first, second],
        manifest_file_name="_transform.json",
        expected_table_names=EXPECTED_TABLES,
    )

    assert candidate in (first, second)


def test_restore_candidate_prefers_the_newest_copy(tmp_path: Path) -> None:
    older = tmp_path / ".transform-retired-aaa"
    newer = tmp_path / ".transform-retired-bbb"
    _write_retired(older, "2026-11-01T00:00:00Z")
    _write_retired(newer, "2026-11-01T01:00:00Z")

    candidate = _restore_candidate(
        [older, newer],
        manifest_file_name="_transform.json",
        expected_table_names=EXPECTED_TABLES,
    )

    assert candidate == newer
