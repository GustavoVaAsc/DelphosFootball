"""Atomic staging-directory swap shared by the pipeline stages.

Input: the caller stage's name, its manifest file name, the table names its manifest must list,
the exception class it reports expected failures with, and the pipeline data directory.
Output: `<data dir>/<stage>/` atomically replaced by the fully written staging directory next to
it, with leftovers from interrupted runs restored or removed.
Responsibility: implement the one swap protocol every stage uses — prepare the data directory,
check target ownership, retire the previous output, swap the new one in with retries and
rollback, restore a complete retired copy when the target is missing, and remove leftovers
best-effort. The helpers implement a single protocol and only make sense read together, so they
stay in one module instead of one file per helper. Each stage passes its own name and gets
`.<stage>-staging-` and `.<stage>-retired-` directory names.
"""

import json
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

import typer

_RENAME_ATTEMPTS = 3
_RENAME_RETRY_DELAY_SECONDS = 0.5


def _staging_prefix(stage: str) -> str:
    return f".{stage}-staging-"


def _retired_prefix(stage: str) -> str:
    return f".{stage}-retired-"


def _prepare_data_dir(
    data_dir: Path,
    *,
    stage: str,
    manifest_file_name: str,
    expected_table_names: set[str],
    error: type[Exception],
) -> None:
    target = data_dir / stage
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        retired = sorted(data_dir.glob(f"{_retired_prefix(stage)}*"))
        staging = sorted(data_dir.glob(f"{_staging_prefix(stage)}*"))
    except OSError as exc:
        raise error(f"could not prepare {data_dir}: {exc}") from exc
    if not target.exists() and retired:
        candidate = _restore_candidate(
            retired,
            manifest_file_name=manifest_file_name,
            expected_table_names=expected_table_names,
        )
        if candidate is None:
            typer.echo(
                f"warning: {target} is missing and no leftover copy of it is complete; "
                f"discarding {', '.join(path.name for path in retired)}",
                err=True,
            )
        else:
            try:
                _rename(candidate, target)
            except OSError as exc:
                raise error(
                    f"could not restore {target} from {candidate}: {exc}; close programs or "
                    f"terminals using {candidate} and retry"
                ) from exc
            typer.echo(f"restored {target} from {candidate.name}, left by an interrupted run")
            retired.remove(candidate)
    for leftover in [*staging, *retired]:
        typer.echo(f"removing {leftover.name}, left by an interrupted run")
        _remove_best_effort(leftover, "a leftover directory", stage=stage)


def _restore_candidate(
    retired: list[Path], *, manifest_file_name: str, expected_table_names: set[str]
) -> Path | None:
    complete: list[tuple[float, Path]] = []
    for directory in retired:
        try:
            manifest = json.loads((directory / manifest_file_name).read_text(encoding="utf-8"))
            tables = manifest["tables"]
            if set(tables) != expected_table_names:
                continue
            files = [info["parquet_file"] for info in tables.values()]
            if not all((directory / name).is_file() for name in files):
                continue
            cleaned_at = manifest.get("cleaned_at")
            age = (
                datetime.fromisoformat(cleaned_at).timestamp()
                if isinstance(cleaned_at, str)
                else directory.stat().st_mtime
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        complete.append((age, directory))
    return max(complete)[1] if complete else None


def _check_ownership(
    target: Path, *, stage: str, manifest_file_name: str, error: type[Exception]
) -> None:
    if target.exists() and not (target / manifest_file_name).is_file():
        raise error(
            f"{target} exists but was not written by {stage}; refusing to replace it "
            f"(it has no {manifest_file_name})"
        )


def _rename(source: Path, target: Path) -> None:
    for attempt in range(1, _RENAME_ATTEMPTS + 1):
        try:
            source.rename(target)
            return
        except OSError:
            if attempt == _RENAME_ATTEMPTS:
                raise
            time.sleep(_RENAME_RETRY_DELAY_SECONDS)


def _swap_in(staging: Path, target: Path, *, stage: str, error: type[Exception]) -> None:
    retired = None
    if target.exists():
        retired = target.with_name(f"{_retired_prefix(stage)}{uuid.uuid4().hex}")
        try:
            _rename(target, retired)
        except OSError as exc:
            raise error(
                f"could not move the previous output aside: {exc}; close programs or terminals "
                f"using {target} and retry"
            ) from exc
    try:
        _rename(staging, target)
    except OSError as exc:
        if retired is None:
            raise error(
                f"could not move the new output into {target}: {exc}; close programs or "
                f"terminals using {target.parent} and retry"
            ) from exc
        try:
            _rename(retired, target)
        except OSError as rollback_exc:
            raise error(
                f"could not move the new output into {target} ({exc}), and putting the previous "
                f"output back also failed ({rollback_exc}). The previous output is in {retired}; "
                f"rename it to {target.name} to recover, or rerun {stage}, which restores it"
            ) from exc
        raise error(
            f"could not move the new output into {target}: {exc}. The previous output was put "
            f"back; close programs or terminals using {target} and retry"
        ) from exc
    if retired is not None:
        _remove_best_effort(retired, "the previous output", stage=stage)


def _remove_best_effort(path: Path, description: str, *, stage: str) -> None:
    try:
        shutil.rmtree(path)
    except OSError as exc:
        typer.echo(
            f"warning: could not delete {description} at {path}: {exc}. The next {stage} run "
            "removes it, or delete it by hand",
            err=True,
        )
