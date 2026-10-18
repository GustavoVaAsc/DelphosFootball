"""Pipeline stage `ingest`: copies the pinned Kaggle dataset into Parquet files, as text.

Input: the Kaggle dataset `DELPHOS_KAGGLE_DATASET` at version `DELPHOS_KAGGLE_DATASET_VERSION`,
downloaded with kagglehub (which keeps its own local cache).
Output: `<data dir>/ingest/<table>.parquet` for every CSV in the dataset, plus
`<data dir>/ingest/_snapshot.json`.
Responsibility: copy the CSVs faithfully. Every column is a Parquet string column holding the
exact text of each field, so "007", "True", "700000.000", "NA", and "-" come through unchanged.
Typing, cleaning, renaming, and filtering belong to the `clean` stage.

Nulls: an unquoted empty field becomes null. A quoted empty field (`""`) stays an empty string,
because the source writes nulls and empty strings differently. Blank lines are skipped, except
in a single-column CSV, where an empty line is an unquoted empty field and becomes a null row.
Quoted values may span lines.

Headers: a CSV with duplicate or empty column names fails the run, because the copy could not
keep those columns apart.

Rejected alternative: letting pandas infer column types. Inference rewrites the text (`007`
becomes 7, `700000.000` becomes 700000.0, `True` becomes a boolean) and moves typing decisions
into ingest.

`snapshot_sha256` is the SHA-256 of the UTF-8 text made of one line
`"<file sha256>  <file name>\\n"` per source CSV, sorted by file name. This is the format
`sha256sum` prints.

Each run writes into a temporary directory next to `ingest/` and swaps it in after every table
is written. A failed run leaves the previous output in place. If a crash leaves `ingest/`
missing, the next run restores the newest complete leftover copy (one whose `_snapshot.json`
lists only files that exist). Leftovers it cannot delete are reported and left for a later run.
Two ingest runs on the same data directory at the same time are not supported.
"""

import csv
import hashlib
import json
import shutil
import tempfile
import time
import uuid
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import kagglehub
import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq
import typer

from delphos_ml.config import (
    DEFAULT_KAGGLE_DATASET,
    DEFAULT_KAGGLE_DATASET_VERSION,
    ConfigError,
    Settings,
    load_settings,
)

STAGE_DIR_NAME = "ingest"
SNAPSHOT_FILE_NAME = "_snapshot.json"
_STAGING_PREFIX = ".ingest-staging-"
_RETIRED_PREFIX = ".ingest-retired-"
# Each CSV is streamed in blocks of this size, so memory depends on it, not on the file size.
_CSV_BLOCK_BYTES = 16 * 1024 * 1024
# Antivirus scanners and open terminals can hold a directory for a moment on Windows.
_RENAME_ATTEMPTS = 3
_RENAME_RETRY_DELAY_SECONDS = 0.5
# Errors that mean "this CSV could not be converted" rather than a bug in this module.
_CONVERSION_ERRORS = (OSError, ValueError, csv.Error, pa.ArrowException, MemoryError)


class IngestError(Exception):
    """An expected ingest failure, reported to the user as a one-line message."""


def ingest() -> None:
    """Copy the pinned Kaggle dataset into data/ingest/ as Parquet files.

    Downloads davidcariboo/player-scores version 679 with kagglehub. Set
    DELPHOS_KAGGLE_DATASET or DELPHOS_KAGGLE_DATASET_VERSION to change either. Writes one
    <table>.parquet per CSV to <DELPHOS_DATA_DIR>/ingest/, where DELPHOS_DATA_DIR defaults to
    data. Every column is stored as text exactly as it appears in the CSV, and unquoted empty
    fields become null. _snapshot.json records the version, file hashes, column names, and row
    counts. The previous ingest/ is replaced only after every table is written.
    """
    try:
        settings = load_settings()
        snapshot = _run(settings)
    except (ConfigError, IngestError) as exc:
        typer.echo(f"ingest failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    total_rows = sum(table["rows"] for table in snapshot["tables"].values())
    typer.echo(
        f"Wrote {len(snapshot['tables'])} tables ({total_rows} rows) to "
        f"{settings.data_dir / STAGE_DIR_NAME}"
    )
    typer.echo(f"snapshot_sha256 {snapshot['snapshot_sha256']}")


def _run(settings: Settings) -> dict[str, Any]:
    """Download, convert, and publish `data/ingest/`; return the snapshot metadata."""
    ingested_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    data_dir = settings.data_dir
    target = data_dir / STAGE_DIR_NAME
    typer.echo(f"Data directory: {data_dir}")
    _announce_overrides(settings)
    _prepare_data_dir(data_dir)
    _check_ownership(target)

    handle = f"{settings.kaggle_dataset}/versions/{settings.kaggle_dataset_version}"
    source = _download(handle)
    csv_files = _find_csv_files(source)

    try:
        staging = Path(tempfile.mkdtemp(prefix=_STAGING_PREFIX, dir=data_dir))
    except OSError as exc:
        raise IngestError(f"could not create a temporary directory in {data_dir}: {exc}") from exc
    try:
        tables: dict[str, dict[str, Any]] = {}
        for name, path in csv_files.items():
            table = Path(name).stem
            tables[table] = _copy_table(path, name, staging / f"{table}.parquet")
        snapshot = {
            "dataset": settings.kaggle_dataset,
            "version": settings.kaggle_dataset_version,
            "handle": handle,
            "ingested_at": ingested_at,
            "snapshot_sha256": _combined_snapshot_hash(
                {info["source_file"]: info["sha256"] for info in tables.values()}
            ),
            "tool_versions": {"kagglehub": version("kagglehub"), "pyarrow": version("pyarrow")},
            "tables": tables,
        }
        try:
            (staging / SNAPSHOT_FILE_NAME).write_text(
                json.dumps(snapshot, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            raise IngestError(f"could not write {SNAPSHOT_FILE_NAME}: {exc}") from exc
        _swap_in(staging, target)
    finally:
        if staging.exists():
            _remove_best_effort(staging, "the temporary directory")
    return snapshot


def _announce_overrides(settings: Settings) -> None:
    if settings.kaggle_dataset != DEFAULT_KAGGLE_DATASET:
        typer.echo(
            f"using overridden dataset {settings.kaggle_dataset} (default {DEFAULT_KAGGLE_DATASET})"
        )
    if settings.kaggle_dataset_version != DEFAULT_KAGGLE_DATASET_VERSION:
        typer.echo(
            f"using overridden version {settings.kaggle_dataset_version} "
            f"(default {DEFAULT_KAGGLE_DATASET_VERSION})"
        )


def _prepare_data_dir(data_dir: Path) -> None:
    """Create `data_dir`, then recover or remove what an interrupted earlier run left behind.

    If `ingest/` is missing, a run died between moving the old output aside and putting the new
    one in place. The newest complete retired copy is restored; the other leftovers are deleted,
    and each deletion is reported.
    """
    target = data_dir / STAGE_DIR_NAME
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        retired = sorted(data_dir.glob(f"{_RETIRED_PREFIX}*"))
        staging = sorted(data_dir.glob(f"{_STAGING_PREFIX}*"))
    except OSError as exc:
        raise IngestError(f"could not prepare {data_dir}: {exc}") from exc
    if not target.exists() and retired:
        candidate = _restore_candidate(retired)
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
                raise IngestError(
                    f"could not restore {target} from {candidate}: {exc}; close programs or "
                    f"terminals using {candidate} and retry"
                ) from exc
            typer.echo(f"restored {target} from {candidate.name}, left by an interrupted run")
            retired.remove(candidate)
    for leftover in [*staging, *retired]:
        typer.echo(f"removing {leftover.name}, left by an interrupted run")
        _remove_best_effort(leftover, "a leftover directory")


def _restore_candidate(retired: list[Path]) -> Path | None:
    """Return the newest retired copy whose snapshot lists only files that exist, or None."""
    complete: list[tuple[float, Path]] = []
    for directory in retired:
        try:
            snapshot = json.loads((directory / SNAPSHOT_FILE_NAME).read_text(encoding="utf-8"))
            files = [info["parquet_file"] for info in snapshot["tables"].values()]
            if not files or not all((directory / name).is_file() for name in files):
                continue
            ingested_at = snapshot.get("ingested_at")
            age = (
                datetime.fromisoformat(ingested_at).timestamp()
                if isinstance(ingested_at, str)
                else directory.stat().st_mtime
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue  # unreadable or malformed snapshot: not a complete copy
        complete.append((age, directory))
    return max(complete)[1] if complete else None


def _check_ownership(target: Path) -> None:
    if target.exists() and not (target / SNAPSHOT_FILE_NAME).is_file():
        raise IngestError(
            f"{target} exists but was not written by ingest; refusing to replace it "
            f"(it has no {SNAPSHOT_FILE_NAME})"
        )


def _combined_snapshot_hash(file_hashes: dict[str, str]) -> str:
    """SHA-256 over `"<sha256>  <file name>\\n"` lines sorted by file name (sha256sum format)."""
    listing = "".join(f"{file_hashes[name]}  {name}\n" for name in sorted(file_hashes))
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()


def _download(handle: str) -> Path:
    typer.echo(f"Downloading {handle} with kagglehub (cached after the first download)")
    try:
        path = Path(kagglehub.dataset_download(handle))
    except Exception as exc:  # kagglehub raises many types; all mean "no dataset".
        raise IngestError(f"could not download {handle}: {exc}") from exc
    if not path.is_dir():
        raise IngestError(f"kagglehub returned {path} for {handle}, which is not a directory")
    typer.echo(f"Source files: {path}")
    return path


def _find_csv_files(source: Path) -> dict[str, Path]:
    """Map each CSV's path relative to `source` (POSIX style) to its absolute path."""
    found = {
        path.relative_to(source).as_posix(): path
        for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() == ".csv"
    }
    if not found:
        raise IngestError(f"the download at {source} contains no CSV files")
    # Compared case-insensitively because Windows (NTFS) treats A.parquet and a.parquet as one.
    seen: dict[str, str] = {}
    for name in sorted(found):
        key = Path(name).stem.casefold()
        if key in seen:
            raise IngestError(
                f"{seen[key]} and {name} would both be written as {Path(name).stem}.parquet "
                "(table names are compared case-insensitively)"
            )
        seen[key] = name
    return {name: found[name] for name in sorted(found)}


def _copy_table(source: Path, source_name: str, target: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        typer.echo(f"reading {target.stem} ({source.stat().st_size / 2**20:.1f} MiB)")
        column_names = _read_header(source, source_name)
        rows = _stream_csv_to_parquet(source, column_names, target)
        with source.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
    except _CONVERSION_ERRORS as exc:
        raise IngestError(f"could not convert {source_name}: {exc}") from exc
    elapsed = time.perf_counter() - started
    typer.echo(f"  {target.stem}: {rows} rows x {len(column_names)} columns in {elapsed:.1f}s")
    return {
        "source_file": source_name,
        "parquet_file": target.name,
        "sha256": digest,
        "rows": rows,
        "columns": len(column_names),
        "column_names": column_names,
    }


def _read_header(source: Path, source_name: str) -> list[str]:
    """Return the header row, rejecting names a faithful copy could not keep apart."""
    with source.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle), None)
    if not header:
        raise IngestError(f"{source_name} has no header row")
    duplicates = sorted({name for name in header if header.count(name) > 1})
    empty = [str(position) for position, name in enumerate(header, start=1) if not name.strip()]
    problems = []
    if duplicates:
        problems.append("duplicate column names " + ", ".join(repr(n) for n in duplicates))
    if empty:
        problems.append("empty column names at positions " + ", ".join(empty))
    if problems:
        raise IngestError(f"{source_name} has {' and '.join(problems)}")
    return header


def _stream_csv_to_parquet(source: Path, column_names: list[str], target: Path) -> int:
    """Copy `source` into `target` block by block, every column as a string; return the rows."""
    read_options = pa_csv.ReadOptions(block_size=_CSV_BLOCK_BYTES)
    # With one column, an empty line is an unquoted empty field (a null row), not a blank line.
    parse_options = pa_csv.ParseOptions(
        newlines_in_values=True, ignore_empty_lines=len(column_names) != 1
    )
    convert_options = pa_csv.ConvertOptions(
        column_types={name: pa.string() for name in column_names},
        null_values=[""],
        strings_can_be_null=True,
        quoted_strings_can_be_null=False,
    )
    rows = 0
    with pa_csv.open_csv(
        source,
        read_options=read_options,
        parse_options=parse_options,
        convert_options=convert_options,
    ) as reader:
        if reader.schema.names != column_names:
            raise ValueError(
                f"pyarrow read the header as {reader.schema.names}, expected {column_names}"
            )
        with pq.ParquetWriter(target, reader.schema) as writer:
            for batch in reader:
                writer.write_batch(batch)
                rows += batch.num_rows
    return rows


def _rename(source: Path, target: Path) -> None:
    """Rename with a few short retries; raise the last OSError if every attempt fails."""
    for attempt in range(1, _RENAME_ATTEMPTS + 1):
        try:
            source.rename(target)
            return
        except OSError:
            if attempt == _RENAME_ATTEMPTS:
                raise
            time.sleep(_RENAME_RETRY_DELAY_SECONDS)


def _swap_in(staging: Path, target: Path) -> None:
    """Replace `target` with `staging`, putting the old `target` back if the swap fails."""
    retired = None
    if target.exists():
        retired = target.with_name(f"{_RETIRED_PREFIX}{uuid.uuid4().hex}")
        try:
            _rename(target, retired)
        except OSError as exc:
            raise IngestError(
                f"could not move the previous output aside: {exc}; close programs or terminals "
                f"using {target} and retry"
            ) from exc
    try:
        _rename(staging, target)
    except OSError as exc:
        if retired is None:
            raise IngestError(
                f"could not move the new output into {target}: {exc}; close programs or "
                f"terminals using {target.parent} and retry"
            ) from exc
        try:
            _rename(retired, target)
        except OSError as rollback_exc:
            raise IngestError(
                f"could not move the new output into {target} ({exc}), and putting the previous "
                f"output back also failed ({rollback_exc}). The previous output is in {retired}; "
                f"rename it to {target.name} to recover, or rerun ingest, which restores it"
            ) from exc
        raise IngestError(
            f"could not move the new output into {target}: {exc}. The previous output was put "
            f"back; close programs or terminals using {target} and retry"
        ) from exc
    if retired is not None:
        _remove_best_effort(retired, "the previous output")


def _remove_best_effort(path: Path, description: str) -> None:
    """Delete `path`; on failure warn instead of failing, since the next run removes it."""
    try:
        shutil.rmtree(path)
    except OSError as exc:
        typer.echo(
            f"warning: could not delete {description} at {path}: {exc}. The next ingest run "
            "removes it, or delete it by hand",
            err=True,
        )
