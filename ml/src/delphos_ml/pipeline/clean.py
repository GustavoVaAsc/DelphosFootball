"""Pipeline stage `clean`: casts, filters, and sanitizes the 9 modeling tables from `ingest`.

Input: `<data dir>/ingest/_snapshot.json` and the 9 included text-only Parquet tables written by
`ingest` (`appearances`, `club_games`, `clubs`, `competitions`, `game_lineups`, `games`,
`player_valuations`, `players`, `transfers`).
Output: `<data dir>/clean/<table>.parquet` for those 9 tables with explicit Arrow types, plus
`<data dir>/clean/_clean.json`.
Responsibility: enforce the schema, sentinel, duplicate-key, temporal-leakage column pruning, and
row-level outlier rules from `docs/ML_ARCHITECTURE.md` sections 3.2 to 3.5 without performing
cross-row statistical imputation or multi-table feature joins (owned by `transform`).

Each run writes into a temporary directory next to `clean/` and swaps it in after every table and
`_clean.json` are written. A failed run leaves any previous `clean/` output intact.
"""

import json
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal, TypeGuard

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import typer

from delphos_ml.config import ConfigError, Settings, load_settings
from delphos_ml.pipeline._staging import (
    # Re-exported because the test fixture monkeypatches it on this module by name; _rename
    # reads its own copy in _staging, so the attribute must only exist here.
    _RENAME_RETRY_DELAY_SECONDS as _RENAME_RETRY_DELAY_SECONDS,
)
from delphos_ml.pipeline._staging import (
    _check_ownership,
    _prepare_data_dir,
    _remove_best_effort,
    _staging_prefix,
    _swap_in,
)
from delphos_ml.pipeline.ingest import SNAPSHOT_FILE_NAME
from delphos_ml.pipeline.ingest import STAGE_DIR_NAME as INGEST_DIR_NAME

STAGE_DIR_NAME = "clean"
MANIFEST_FILE_NAME = "_clean.json"
EXCLUDED_TABLES: tuple[str, ...] = ("countries", "game_events", "national_teams")

_INT_PATTERN = r"^-?[0-9]+$"
_FLOAT_PATTERN = r"^-?[0-9]+(\.[0-9]+)?$"
_ISO_DATE_OR_TS_PATTERN = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}([ T]([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]+)?)?$"
)
_VALID_PLAYER_POSITIONS: tuple[str, ...] = (
    "Defender",
    "Midfield",
    "Attack",
    "Goalkeeper",
    "Missing",
)

ColKind = Literal["string", "int64", "float64", "bool", "date32"]

_ARROW_TYPES: dict[ColKind, pa.DataType] = {
    "string": pa.string(),
    "int64": pa.int64(),
    "float64": pa.float64(),
    "bool": pa.bool_(),
    "date32": pa.date32(),
}


class CleanError(Exception):
    """An expected clean failure, reported to the user as a one-line message."""


@dataclass(frozen=True)
class ColSpec:
    name: str
    kind: ColKind
    nullable: bool = False
    sentinels: tuple[str, ...] = ()
    disallow_negative: bool = False
    null_below: int | None = None


@dataclass(frozen=True)
class TableSpec:
    name: str
    primary_key: tuple[str, ...]
    columns: tuple[ColSpec, ...]
    dropped_columns: tuple[str, ...] = ()


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        name="appearances",
        primary_key=("appearance_id",),
        dropped_columns=("player_current_club_id",),
        columns=(
            ColSpec("appearance_id", "string"),
            ColSpec("game_id", "int64"),
            ColSpec("player_id", "int64"),
            ColSpec("player_club_id", "int64"),
            ColSpec("date", "date32"),
            ColSpec("player_name", "string", nullable=True),
            ColSpec("competition_id", "string"),
            ColSpec("yellow_cards", "int64", disallow_negative=True),
            ColSpec("red_cards", "int64", disallow_negative=True),
            ColSpec("goals", "int64", disallow_negative=True),
            ColSpec("assists", "int64", disallow_negative=True),
            ColSpec("minutes_played", "int64"),
        ),
    ),
    TableSpec(
        name="club_games",
        primary_key=("game_id", "club_id"),
        columns=(
            ColSpec("game_id", "int64"),
            ColSpec("club_id", "int64"),
            ColSpec("own_goals", "int64", disallow_negative=True),
            ColSpec("own_position", "int64", nullable=True),
            ColSpec("own_manager_name", "string", nullable=True),
            ColSpec("opponent_id", "int64"),
            ColSpec("opponent_goals", "int64", disallow_negative=True),
            ColSpec("opponent_position", "int64", nullable=True),
            ColSpec("opponent_manager_name", "string", nullable=True),
            ColSpec("hosting", "string"),
            ColSpec("is_win", "bool"),
        ),
    ),
    TableSpec(
        name="clubs",
        primary_key=("club_id",),
        dropped_columns=(
            "total_market_value",
            "squad_size",
            "average_age",
            "foreigners_number",
            "foreigners_percentage",
            "national_team_players",
            "net_transfer_record",
            "coach_name",
            "last_season",
            "filename",
        ),
        columns=(
            ColSpec("club_id", "int64"),
            ColSpec("club_code", "string"),
            ColSpec("name", "string"),
            ColSpec("domestic_competition_id", "string"),
            ColSpec("stadium_name", "string", nullable=True),
            ColSpec("stadium_seats", "int64", nullable=True, disallow_negative=True),
            ColSpec("url", "string", nullable=True),
        ),
    ),
    TableSpec(
        name="competitions",
        primary_key=("competition_id",),
        columns=(
            ColSpec("competition_id", "string"),
            ColSpec("competition_code", "string"),
            ColSpec("name", "string"),
            ColSpec("sub_type", "string"),
            ColSpec("type", "string"),
            ColSpec("country_id", "int64", nullable=True, sentinels=("-1",)),
            ColSpec("country_name", "string", nullable=True),
            ColSpec("domestic_league_code", "string", nullable=True),
            ColSpec("confederation", "string"),
            ColSpec("total_clubs", "int64", nullable=True, disallow_negative=True),
            ColSpec("url", "string", nullable=True),
        ),
    ),
    TableSpec(
        name="game_lineups",
        primary_key=("game_lineups_id",),
        columns=(
            ColSpec("game_lineups_id", "string"),
            ColSpec("date", "date32"),
            ColSpec("game_id", "int64"),
            ColSpec("player_id", "int64"),
            ColSpec("club_id", "int64"),
            ColSpec("player_name", "string", nullable=True),
            ColSpec("type", "string"),
            ColSpec("position", "string", nullable=True),
            ColSpec("number", "int64", nullable=True, sentinels=("-",)),
            ColSpec("team_captain", "bool"),
        ),
    ),
    TableSpec(
        name="games",
        primary_key=("game_id",),
        columns=(
            ColSpec("game_id", "int64"),
            ColSpec("competition_id", "string"),
            ColSpec("season", "int64"),
            ColSpec("round", "string", nullable=True),
            ColSpec("date", "date32"),
            ColSpec("home_club_id", "int64"),
            ColSpec("away_club_id", "int64"),
            ColSpec("home_club_goals", "int64", disallow_negative=True),
            ColSpec("away_club_goals", "int64", disallow_negative=True),
            ColSpec("home_club_position", "int64", nullable=True),
            ColSpec("away_club_position", "int64", nullable=True),
            ColSpec("home_club_manager_name", "string", nullable=True),
            ColSpec("away_club_manager_name", "string", nullable=True),
            ColSpec("stadium", "string", nullable=True),
            ColSpec("attendance", "int64", nullable=True, disallow_negative=True),
            ColSpec("referee", "string", nullable=True),
            ColSpec("url", "string", nullable=True),
            ColSpec("home_club_formation", "string", nullable=True),
            ColSpec("away_club_formation", "string", nullable=True),
            ColSpec("home_club_name", "string", nullable=True),
            ColSpec("away_club_name", "string", nullable=True),
            ColSpec("aggregate", "string", nullable=True),
            ColSpec("competition_type", "string", nullable=True),
        ),
    ),
    TableSpec(
        name="player_valuations",
        primary_key=("player_id", "date"),
        columns=(
            ColSpec("player_id", "int64"),
            ColSpec("date", "date32"),
            ColSpec("market_value_in_eur", "float64"),
            ColSpec("current_club_name", "string", nullable=True),
            ColSpec("current_club_id", "int64"),
            ColSpec("player_club_domestic_competition_id", "string", nullable=True),
        ),
    ),
    TableSpec(
        name="players",
        primary_key=("player_id",),
        dropped_columns=(
            "last_season",
            "current_club_id",
            "contract_expiration_date",
            "agent_name",
            "international_caps",
            "international_goals",
            "current_national_team_id",
            "current_club_domestic_competition_id",
            "current_club_name",
            "market_value_in_eur",
            "highest_market_value_in_eur",
        ),
        columns=(
            ColSpec("player_id", "int64"),
            ColSpec("first_name", "string", nullable=True),
            ColSpec("last_name", "string", nullable=True),
            ColSpec("name", "string"),
            ColSpec("player_code", "string"),
            ColSpec("country_of_birth", "string", nullable=True),
            ColSpec("city_of_birth", "string", nullable=True, sentinels=("-",)),
            ColSpec("country_of_citizenship", "string", nullable=True),
            ColSpec("date_of_birth", "date32"),
            ColSpec("sub_position", "string", nullable=True),
            ColSpec("position", "string"),
            ColSpec("foot", "string", nullable=True),
            ColSpec("height_in_cm", "int64", nullable=True, null_below=140),
            ColSpec("image_url", "string", nullable=True),
            ColSpec("url", "string", nullable=True),
        ),
    ),
    TableSpec(
        name="transfers",
        primary_key=("player_id", "transfer_date", "from_club_id", "to_club_id"),
        columns=(
            ColSpec("player_id", "int64"),
            ColSpec("transfer_date", "date32"),
            ColSpec("transfer_season", "string"),
            ColSpec("from_club_id", "int64"),
            ColSpec("to_club_id", "int64"),
            ColSpec("from_club_name", "string", nullable=True),
            ColSpec("to_club_name", "string", nullable=True),
            ColSpec("transfer_fee", "float64", nullable=True, disallow_negative=True),
            ColSpec("market_value_in_eur", "float64", nullable=True, disallow_negative=True),
            ColSpec("player_name", "string", nullable=True),
        ),
    ),
)


def _is_strict_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def clean() -> None:
    """Cast, filter, and sanitize the 9 modeling tables from data/ingest/ into data/clean/.

    Reads _snapshot.json and the 9 included text-only Parquet tables from
    <DELPHOS_DATA_DIR>/ingest/, where DELPHOS_DATA_DIR defaults to data. Drops the 3 excluded
    tables (countries, game_events, national_teams) and banned static snapshot columns, casts
    every column to its explicit Arrow type, maps sentinels to null, enforces unique primary
    keys, applies row-level outlier filters, and writes typed Parquet tables plus _clean.json to
    <DELPHOS_DATA_DIR>/clean/. The previous clean/ directory is replaced only after every table
    is written.
    """
    try:
        settings = load_settings()
        manifest = _run(settings)
    except (ConfigError, CleanError) as exc:
        typer.echo(f"clean failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    total_in = sum(info["input_rows"] for info in manifest["tables"].values())
    total_out = sum(info["output_rows"] for info in manifest["tables"].values())
    typer.echo(
        f"Cleaned {len(manifest['tables'])} tables ({total_in} -> {total_out} rows) into "
        f"{settings.data_dir / STAGE_DIR_NAME}"
    )


def _run(settings: Settings) -> dict[str, Any]:
    cleaned_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    data_dir = settings.data_dir
    ingest_dir = data_dir / INGEST_DIR_NAME
    target = data_dir / STAGE_DIR_NAME
    typer.echo(f"Data directory: {data_dir}")
    _prepare_data_dir(
        data_dir,
        stage=STAGE_DIR_NAME,
        manifest_file_name=MANIFEST_FILE_NAME,
        expected_table_names={spec.name for spec in TABLE_SPECS},
        error=CleanError,
    )
    _check_ownership(
        target, stage=STAGE_DIR_NAME, manifest_file_name=MANIFEST_FILE_NAME, error=CleanError
    )
    snapshot = _load_ingest_snapshot(ingest_dir, settings)

    try:
        staging = Path(tempfile.mkdtemp(prefix=_staging_prefix(STAGE_DIR_NAME), dir=data_dir))
    except OSError as exc:
        raise CleanError(f"could not create a temporary directory in {data_dir}: {exc}") from exc
    try:
        tables_summary: dict[str, dict[str, Any]] = {}
        for spec in TABLE_SPECS:
            table_meta = snapshot["tables"].get(spec.name)
            rows_val = table_meta.get("rows") if isinstance(table_meta, dict) else None
            if not _is_strict_int(rows_val) or rows_val < 0:
                raise CleanError(
                    f"ingest {SNAPSHOT_FILE_NAME} has no valid entry for required table "
                    f"{spec.name!r}"
                )
            source_parquet = ingest_dir / f"{spec.name}.parquet"
            if not source_parquet.is_file():
                raise CleanError(f"missing required ingest file {source_parquet}")
            tables_summary[spec.name] = _clean_table(
                source_parquet=source_parquet,
                expected_rows=rows_val,
                spec=spec,
                target_parquet=staging / f"{spec.name}.parquet",
            )
        excluded_present = [name for name in EXCLUDED_TABLES if name in snapshot["tables"]]
        manifest: dict[str, Any] = {
            "dataset": snapshot["dataset"],
            "version": snapshot["version"],
            "source_snapshot_sha256": snapshot["snapshot_sha256"],
            "cleaned_at": cleaned_at,
            "tool_versions": {
                "pandas": version("pandas"),
                "pyarrow": version("pyarrow"),
            },
            "excluded_tables": excluded_present,
            "tables": tables_summary,
        }
        try:
            (staging / MANIFEST_FILE_NAME).write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            raise CleanError(f"could not write {MANIFEST_FILE_NAME}: {exc}") from exc
        _swap_in(staging, target, stage=STAGE_DIR_NAME, error=CleanError)
    finally:
        if staging.exists():
            _remove_best_effort(staging, "the temporary directory", stage=STAGE_DIR_NAME)
    return manifest


def _load_ingest_snapshot(ingest_dir: Path, settings: Settings) -> dict[str, Any]:
    snapshot_path = ingest_dir / SNAPSHOT_FILE_NAME
    if not snapshot_path.is_file():
        raise CleanError(
            f"missing ingest snapshot at {snapshot_path}; run `delphos-pipeline ingest` first"
        )
    try:
        raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CleanError(f"could not read {snapshot_path}: {exc}") from exc
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("dataset"), str)
        or not _is_strict_int(raw.get("version"))
        or raw["version"] < 1
        or not isinstance(raw.get("snapshot_sha256"), str)
        or not isinstance(raw.get("tables"), dict)
    ):
        raise CleanError(f"{snapshot_path} is missing required snapshot fields")
    if (
        raw["dataset"] != settings.kaggle_dataset
        or raw["version"] != settings.kaggle_dataset_version
    ):
        raise CleanError(
            f"ingest snapshot ({raw['dataset']} v{raw['version']}) does not match configured "
            f"dataset ({settings.kaggle_dataset} v{settings.kaggle_dataset_version}); rerun ingest"
        )
    known_tables = {spec.name for spec in TABLE_SPECS} | set(EXCLUDED_TABLES)
    unknown_tables = sorted(set(raw["tables"]) - known_tables)
    if unknown_tables:
        raise CleanError(f"ingest {SNAPSHOT_FILE_NAME} lists unexpected tables {unknown_tables}")
    return raw


def _clean_table(
    source_parquet: Path,
    expected_rows: int,
    spec: TableSpec,
    target_parquet: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    retained_names = [col.name for col in spec.columns]
    try:
        with pq.ParquetFile(source_parquet) as pf:
            num_rows = pf.metadata.num_rows
            source_schema = pf.schema_arrow
            if num_rows != expected_rows:
                raise CleanError(
                    f"{spec.name}.parquet row count ({num_rows}) disagrees with "
                    f"{SNAPSHOT_FILE_NAME} ({expected_rows})"
                )
            non_string_fields = [
                f"{field.name} ({field.type})"
                for field in source_schema
                if not (pa.types.is_string(field.type) or pa.types.is_large_string(field.type))
            ]
            if non_string_fields:
                raise CleanError(
                    f"{spec.name}.parquet must hold only Arrow string columns from ingest; got "
                    f"{', '.join(non_string_fields)}"
                )
            expected_cols = set(retained_names) | set(spec.dropped_columns)
            actual_cols = set(source_schema.names)
            missing_cols = sorted(expected_cols - actual_cols)
            unexpected_cols = sorted(actual_cols - expected_cols)
            if missing_cols or unexpected_cols:
                details: list[str] = []
                if missing_cols:
                    details.append(f"missing columns {missing_cols}")
                if unexpected_cols:
                    details.append(f"unexpected columns {unexpected_cols}")
                raise CleanError(f"{spec.name}.parquet schema mismatch: {'; '.join(details)}")
            raw_table = pf.read(columns=retained_names)
    except CleanError:
        raise
    except (OSError, pa.ArrowException) as exc:
        raise CleanError(f"could not read {source_parquet}: {exc}") from exc

    was_not_null: dict[str, pd.Series] = {}
    stripped_changed: dict[str, pd.Series] = {}
    parsed_cols: dict[str, pd.Series] = {}

    for col in spec.columns:
        raw_s = pd.Series(pd.arrays.ArrowExtensionArray(raw_table[col.name].combine_chunks()))
        was_not_null[col.name] = raw_s.notna()
        stripped = raw_s.str.strip()
        norm = stripped.mask(stripped == "", pd.NA)
        if col.sentinels:
            norm = norm.mask(norm.isin(col.sentinels), pd.NA)
        if col.kind == "string":
            stripped_changed[col.name] = (norm.notna() & (norm != raw_s)).fillna(False)
        parsed_cols[col.name] = _cast_column(spec.name, col, norm)

    del raw_table
    df = pd.DataFrame(parsed_cols)
    del parsed_cols
    input_rows = len(df)

    for pk_col in spec.primary_key:
        if df[pk_col].isna().any():
            raise CleanError(f"null primary key in {spec.name}.{pk_col}")
    dup_count = int(df.duplicated(subset=list(spec.primary_key)).sum())
    if dup_count > 0:
        raise CleanError(
            f"duplicate primary key in {spec.name} on {list(spec.primary_key)} "
            f"({dup_count} duplicate rows)"
        )

    df, capped_rows = _apply_row_rules(spec, df)

    for col in spec.columns:
        if col.null_below is not None:
            below_mask = (df[col.name].notna() & (df[col.name] < col.null_below)).fillna(False)
            if below_mask.any():
                df.loc[below_mask, col.name] = pd.NA

    for col in spec.columns:
        null_count = int(df[col.name].isna().sum())
        if not col.nullable and null_count > 0:
            raise CleanError(
                f"null value in required column {spec.name}.{col.name} ({null_count} rows)"
            )

    surviving_idx = df.index
    nulled_cells = sum(
        int((was_not_null[col.name].loc[surviving_idx] & df[col.name].isna()).sum())
        for col in spec.columns
    )
    stripped_cells = sum(
        int((stripped_changed[col.name].loc[surviving_idx] & df[col.name].notna()).sum())
        for col in spec.columns
        if col.kind == "string"
    )

    target_schema = pa.schema(
        [pa.field(col.name, _ARROW_TYPES[col.kind], nullable=col.nullable) for col in spec.columns]
    )
    arrays = [
        pa.array(df[col.name], type=_ARROW_TYPES[col.kind], from_pandas=True)
        for col in spec.columns
    ]
    arrow_out = pa.Table.from_arrays(arrays, schema=target_schema)
    try:
        pq.write_table(arrow_out, target_parquet)
    except (OSError, pa.ArrowException) as exc:
        raise CleanError(f"could not write {target_parquet}: {exc}") from exc

    output_rows = len(df)
    elapsed = time.perf_counter() - started
    typer.echo(
        f"  {spec.name}: {input_rows} -> {output_rows} rows x {len(spec.columns)} columns "
        f"in {elapsed:.1f}s"
    )
    return {
        "parquet_file": target_parquet.name,
        "input_rows": input_rows,
        "output_rows": output_rows,
        "dropped_rows": input_rows - output_rows,
        "capped_rows": capped_rows,
        "nulled_cells": nulled_cells,
        "stripped_cells": stripped_cells,
        "dropped_columns": list(spec.dropped_columns),
        "columns": len(spec.columns),
        "dtypes": {field.name: str(field.type) for field in target_schema},
    }


def _cast_column(table_name: str, col: ColSpec, norm: pd.Series) -> pd.Series:
    qualified = f"{table_name}.{col.name}"
    if col.kind == "string":
        return norm

    non_null = norm.dropna()
    if col.kind == "int64":
        if len(non_null):
            bad = non_null[~non_null.str.fullmatch(_INT_PATTERN)]
            if len(bad):
                raise CleanError(f"invalid int64 value in {qualified}: {bad.iloc[0]!r}")
        try:
            pa_int = pc.cast(pa.array(norm, type=pa.string()), pa.int64())
            parsed = pd.Series(pa_int, index=norm.index, dtype="Int64")
        except (ValueError, OverflowError, TypeError, pa.ArrowException) as exc:
            raise CleanError(f"invalid int64 value in {qualified}: {exc}") from exc
        if col.disallow_negative:
            neg = parsed[parsed < 0]
            if len(neg):
                raise CleanError(f"negative value in {qualified}: {int(neg.iloc[0])}")
        return parsed

    if col.kind == "float64":
        if len(non_null):
            bad = non_null[~non_null.str.fullmatch(_FLOAT_PATTERN)]
            if len(bad):
                raise CleanError(f"invalid float64 value in {qualified}: {bad.iloc[0]!r}")
        try:
            pa_flt = pc.cast(pa.array(norm, type=pa.string()), pa.float64())
            parsed_f = pd.Series(pa_flt, index=norm.index, dtype="Float64")
        except (ValueError, OverflowError, TypeError, pa.ArrowException) as exc:
            raise CleanError(f"invalid float64 value in {qualified}: {exc}") from exc
        if parsed_f.isin((float("inf"), float("-inf"))).any():
            raise CleanError(f"non-finite float64 value in {qualified}")
        if col.disallow_negative:
            neg_f = parsed_f[parsed_f < 0.0]
            if len(neg_f):
                raise CleanError(f"negative value in {qualified}: {float(neg_f.iloc[0])}")
        return parsed_f

    if col.kind == "bool":
        if len(non_null):
            bad = non_null[~non_null.isin(("0", "1"))]
            if len(bad):
                raise CleanError(f"invalid bool value in {qualified}: {bad.iloc[0]!r}")
        return (norm == "1").astype("boolean")

    if len(non_null):
        bad_fmt = non_null[~non_null.str.fullmatch(_ISO_DATE_OR_TS_PATTERN)]
        if len(bad_fmt):
            raise CleanError(f"invalid date32 value in {qualified}: {bad_fmt.iloc[0]!r}")
    sliced = norm.str.slice(0, 10)
    dt_series = pd.to_datetime(sliced, format="%Y-%m-%d", errors="coerce")
    bad_cal = norm[norm.notna() & dt_series.isna()]
    if len(bad_cal):
        raise CleanError(f"invalid calendar date in {qualified}: {bad_cal.iloc[0]!r}")
    arrow_dates = pa.Array.from_pandas(dt_series).cast(pa.date32())
    return pd.Series(arrow_dates, index=norm.index, dtype=pd.ArrowDtype(pa.date32()))


def _apply_row_rules(spec: TableSpec, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    capped_rows = 0
    if spec.name == "appearances":
        if df["minutes_played"].isna().any():
            null_count = int(df["minutes_played"].isna().sum())
            raise CleanError(
                f"null value in required column appearances.minutes_played ({null_count} rows)"
            )
        df = df.loc[(df["minutes_played"] > 0).fillna(False)].copy()
        over_cap = (df["minutes_played"] > 120).fillna(False)
        capped_rows = int(over_cap.sum())
        if capped_rows:
            df.loc[over_cap, "minutes_played"] = 120
        return df, capped_rows

    if spec.name == "player_valuations":
        keep = (df["market_value_in_eur"].notna() & (df["market_value_in_eur"] > 0.0)).fillna(False)
        return df.loc[keep].copy(), 0

    if spec.name == "players":
        if df["position"].isna().any():
            null_count = int(df["position"].isna().sum())
            raise CleanError(f"null value in required column players.position ({null_count} rows)")
        bad_pos = df["position"][~df["position"].isin(_VALID_PLAYER_POSITIONS)]
        if len(bad_pos):
            raise CleanError(f"unexpected value in players.position: {bad_pos.iloc[0]!r}")
        keep = (
            df["date_of_birth"].notna() & ~df["position"].isin(("Goalkeeper", "Missing"))
        ).fillna(False)
        return df.loc[keep].copy(), 0

    return df, 0
