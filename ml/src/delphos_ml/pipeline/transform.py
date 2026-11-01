"""Pipeline stage `transform`: builds the deterministic modeling rows from the cleaned tables.

Input: `<data dir>/clean/_clean.json` and the typed Parquet tables written by `clean`.
Output: `<data dir>/transform/player_seasons.parquet`,
`<data dir>/transform/transfer_events.parquet` and `<data dir>/transform/_transform.json`.
Responsibility: assemble the Option A end-of-season player-season snapshots and the
paid-transfer event rows of docs/ML_ARCHITECTURE.md sections 3.2, 3.3 and 3.4 from the cleaned
tables, computing only deterministic raw counts, ratios and groupings. No statistic is learned
from the data here: the Empirical Bayes priors, imputers and scalers belong to the fitted
preprocessor that `train` fits on the training split, and the parameters both stages must
agree on (`window_days`, `minutes_floor`, `empirical_bayes_m`, `prior_grouping`,
`season_month_start`) are recorded in `_transform.json` so `train` reads them instead of
hard-coding them. Top-level `rows_per_split` and `rows_per_season` count the `player_seasons`
table; each entry under `tables` repeats them for its own table.

Each run writes into a temporary directory next to `transform/` and swaps it in after both
tables and `_transform.json` are written. A failed run leaves any previous `transform/` output
intact.
"""

import hashlib
import json
import tempfile
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import typer

from delphos_ml.config import ConfigError, Settings, load_settings
from delphos_ml.features.snapshots import build_player_seasons, build_transfer_events
from delphos_ml.features.snapshots.season import SEASON_MONTH_START
from delphos_ml.features.windows import TrailingWindowIndex
from delphos_ml.features.windows.trailing_window_index import WINDOW_DAYS
from delphos_ml.pipeline._staging import (
    _check_ownership,
    _prepare_data_dir,
    _remove_best_effort,
    _staging_prefix,
    _swap_in,
)
from delphos_ml.pipeline.clean import MANIFEST_FILE_NAME as CLEAN_MANIFEST_FILE_NAME
from delphos_ml.pipeline.clean import STAGE_DIR_NAME as CLEAN_DIR_NAME

STAGE_DIR_NAME = "transform"
MANIFEST_FILE_NAME = "_transform.json"
TABLE_PLAYER_SEASONS = "player_seasons"
TABLE_TRANSFER_EVENTS = "transfer_events"

MINUTES_FLOOR = 180
EMPIRICAL_BAYES_M = 5
PRIOR_GROUPING = "position"
COUNTRY_TOP_N = 10

# This stage's rename-retry policy, passed to the shared swap so a test can shorten it here.
_RENAME_ATTEMPTS = 3
_RENAME_RETRY_DELAY_SECONDS = 0.5

# Columns of the clean tables this stage reads. Everything else stays untouched on disk.
_INPUT_COLUMNS: dict[str, tuple[str, ...]] = {
    "appearances": (
        "game_id",
        "player_id",
        "player_club_id",
        "date",
        "competition_id",
        "minutes_played",
        "goals",
        "assists",
        "yellow_cards",
        "red_cards",
    ),
    "club_games": ("game_id", "club_id", "own_position", "own_goals", "opponent_goals", "is_win"),
    "clubs": ("club_id", "domestic_competition_id"),
    "competitions": ("competition_id", "type", "sub_type"),
    "game_lineups": ("player_id", "date", "type", "team_captain"),
    "games": ("game_id", "date"),
    "player_valuations": (
        "player_id",
        "date",
        "market_value_in_eur",
        "current_club_id",
        "player_club_domestic_competition_id",
    ),
    "players": (
        "player_id",
        "date_of_birth",
        "position",
        "sub_position",
        "foot",
        "height_in_cm",
        "country_of_citizenship",
    ),
    "transfers": (
        "player_id",
        "transfer_date",
        "from_club_id",
        "to_club_id",
        "transfer_fee",
        "market_value_in_eur",
    ),
}
_DATETIME_COLUMNS: dict[str, tuple[str, ...]] = {
    "player_valuations": ("date",),
    "players": ("date_of_birth",),
    "games": ("date",),
    "transfers": ("transfer_date",),
}
# The window index parses the first 10 characters of text dates itself (ADR-012).
_TEXT_DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "appearances": ("date",),
    "game_lineups": ("date",),
}
# The window index keeps the ingest text contract (ADR-012) and compares these binary flags
# as "1"/"0", but `clean` writes them as Arrow bool — normalize on load like the text dates
# above, or `win_flag` and `captain` would silently stay 0 for every row.
_TEXT_FLAG_COLUMNS: dict[str, tuple[str, ...]] = {
    "club_games": ("is_win",),
    "game_lineups": ("team_captain",),
}

_WINDOW_METRIC_FIELDS: tuple[pa.Field, ...] = tuple(
    pa.field(name, pa.float64())
    for name in (
        "minutes",
        "apps",
        "starts",
        "captain",
        "squad_inclusions",
        "goals",
        "assists",
        "yellow_cards",
        "red_cards",
        "win_flag",
        "clean_sheet_flag",
        "goals_conceded",
        "uefa_minutes",
    )
)
_ROW_SCHEMA_FIELDS: tuple[pa.Field, ...] = (
    pa.field("player_id", pa.int64()),
    pa.field("season", pa.int64()),
    pa.field("as_of_date", pa.date32()),
    pa.field("split", pa.string()),
    pa.field("club_id", pa.int64()),
    pa.field("league_id", pa.string()),
    *_WINDOW_METRIC_FIELDS,
    pa.field("starter_ratio", pa.float64()),
    pa.field("captain_ratio", pa.float64()),
    pa.field("win_rate", pa.float64()),
    pa.field("clean_sheet_rate", pa.float64()),
    pa.field("goals_conceded_per_match", pa.float64()),
    pa.field("uefa_share", pa.float64()),
    pa.field("cup_share", pa.float64()),
    pa.field("league_position", pa.float64(), nullable=True),
    pa.field("league_position_missing", pa.bool_()),
    pa.field("age", pa.float64()),
    pa.field("age_sq", pa.float64()),
    pa.field("height_in_cm", pa.float64(), nullable=True),
    pa.field("foot", pa.string(), nullable=True),
    pa.field("position", pa.string()),
    pa.field("sub_position", pa.string(), nullable=True),
    pa.field("country_group", pa.string()),
    pa.field("log10_market_value", pa.float64()),
)
PLAYER_SEASONS_SCHEMA = pa.schema(_ROW_SCHEMA_FIELDS)
TRANSFER_EVENTS_SCHEMA = pa.schema(
    [
        *_ROW_SCHEMA_FIELDS,
        pa.field("transfer_date", pa.date32()),
        pa.field("transfer_fee", pa.float64()),
        pa.field("pre_transfer_market_value", pa.float64()),
    ]
)


class TransformError(Exception):
    """An expected transform failure, reported to the user as a one-line message."""


def transform() -> None:
    """Build the modeling rows in data/transform/ from the cleaned tables in data/clean/.

    Reads _clean.json and the typed Parquet tables from <DELPHOS_DATA_DIR>/clean/ and writes
    player_seasons.parquet (Option A end-of-season snapshots: seasons 2017 to 2025, the 14
    covered European leagues, outfield players, at least 180 trailing-window minutes),
    transfer_events.parquet (paid outfield transfers with pre-transfer window counts), and
    _transform.json to <DELPHOS_DATA_DIR>/transform/. Only deterministic raw counts, ratios
    and groupings are computed; learned statistics belong to the fitted preprocessor. The
    previous transform/ directory is replaced only after every file is written.
    """
    try:
        settings = load_settings()
        manifest = _run(settings)
    except (ConfigError, TransformError) as exc:
        typer.echo(f"transform failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    total_rows = sum(info["rows"] for info in manifest["tables"].values())
    typer.echo(
        f"Transformed {manifest['tables'][TABLE_PLAYER_SEASONS]['rows']} player-seasons and "
        f"{manifest['tables'][TABLE_TRANSFER_EVENTS]['rows']} transfers ({total_rows} rows) "
        f"into {settings.data_dir / STAGE_DIR_NAME}"
    )


def _run(settings: Settings) -> dict[str, Any]:
    started = time.perf_counter()
    transformed_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    data_dir = settings.data_dir
    clean_dir = data_dir / CLEAN_DIR_NAME
    target = data_dir / STAGE_DIR_NAME
    typer.echo(f"Data directory: {data_dir}")
    _prepare_data_dir(
        data_dir,
        stage=STAGE_DIR_NAME,
        manifest_file_name=MANIFEST_FILE_NAME,
        expected_table_names={TABLE_PLAYER_SEASONS, TABLE_TRANSFER_EVENTS},
        error=TransformError,
    )
    _check_ownership(
        target, stage=STAGE_DIR_NAME, manifest_file_name=MANIFEST_FILE_NAME, error=TransformError
    )
    clean_manifest, clean_manifest_sha256 = _load_clean_manifest(clean_dir, settings)
    tables = _load_tables(clean_dir)
    window, cup_window = _build_indexes(tables)

    player_seasons = build_player_seasons(
        tables["player_valuations"],
        tables["players"],
        tables["club_games"],
        tables["games"],
        window,
        cup_window,
        minutes_floor=MINUTES_FLOOR,
    )
    country_map = _country_group_map(player_seasons["country_of_citizenship"])
    transfer_events = build_transfer_events(
        tables["transfers"],
        tables["players"],
        tables["clubs"],
        tables["club_games"],
        tables["games"],
        window,
        cup_window,
        minutes_floor=MINUTES_FLOOR,
    )
    player_seasons_out = _to_arrow(
        _with_deterministic_columns(player_seasons, country_map), PLAYER_SEASONS_SCHEMA
    )
    transfer_events_out = _to_arrow(
        _with_deterministic_columns(transfer_events, country_map), TRANSFER_EVENTS_SCHEMA
    )
    typer.echo(
        f"  player_seasons: {player_seasons_out.num_rows} rows x "
        f"{len(player_seasons_out.schema.names)} columns; transfer_events: "
        f"{transfer_events_out.num_rows} rows x {len(transfer_events_out.schema.names)} columns "
        f"in {time.perf_counter() - started:.1f}s"
    )

    try:
        staging = Path(tempfile.mkdtemp(prefix=_staging_prefix(STAGE_DIR_NAME), dir=data_dir))
    except OSError as exc:
        raise TransformError(
            f"could not create a temporary directory in {data_dir}: {exc}"
        ) from exc
    try:
        _write_table(
            player_seasons_out, staging / f"{TABLE_PLAYER_SEASONS}.parquet", TABLE_PLAYER_SEASONS
        )
        _write_table(
            transfer_events_out,
            staging / f"{TABLE_TRANSFER_EVENTS}.parquet",
            TABLE_TRANSFER_EVENTS,
        )
        manifest: dict[str, Any] = {
            "dataset": clean_manifest["dataset"],
            "version": clean_manifest["version"],
            "clean_manifest_sha256": clean_manifest_sha256,
            "transformed_at": transformed_at,
            "tool_versions": {"pandas": version("pandas"), "pyarrow": version("pyarrow")},
            "window_days": WINDOW_DAYS,
            "minutes_floor": MINUTES_FLOOR,
            "empirical_bayes_m": EMPIRICAL_BAYES_M,
            "prior_grouping": PRIOR_GROUPING,
            "season_month_start": SEASON_MONTH_START,
            "country_top_n": COUNTRY_TOP_N,
            "rows_per_split": _counts_by(player_seasons, "split"),
            "rows_per_season": _counts_by(player_seasons, "season"),
            "tables": {
                TABLE_PLAYER_SEASONS: _table_summary(
                    player_seasons, player_seasons_out, f"{TABLE_PLAYER_SEASONS}.parquet"
                ),
                TABLE_TRANSFER_EVENTS: _table_summary(
                    transfer_events, transfer_events_out, f"{TABLE_TRANSFER_EVENTS}.parquet"
                ),
            },
        }
        try:
            (staging / MANIFEST_FILE_NAME).write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            raise TransformError(f"could not write {MANIFEST_FILE_NAME}: {exc}") from exc
        _swap_in(
            staging,
            target,
            stage=STAGE_DIR_NAME,
            error=TransformError,
            rename_attempts=_RENAME_ATTEMPTS,
            rename_delay_seconds=_RENAME_RETRY_DELAY_SECONDS,
        )
    finally:
        if staging.exists():
            _remove_best_effort(staging, "the temporary directory", stage=STAGE_DIR_NAME)
    return manifest


def _load_clean_manifest(clean_dir: Path, settings: Settings) -> tuple[dict[str, Any], str]:
    """Read and validate `_clean.json`; return it with the SHA-256 of its bytes."""
    manifest_path = clean_dir / CLEAN_MANIFEST_FILE_NAME
    if not manifest_path.is_file():
        raise TransformError(
            f"missing clean manifest at {manifest_path}; run `delphos-pipeline clean` first"
        )
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    except (OSError, ValueError) as exc:
        raise TransformError(f"could not read {manifest_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise TransformError(f"{manifest_path} is not a JSON object")
    if (
        raw.get("dataset") != settings.kaggle_dataset
        or raw.get("version") != settings.kaggle_dataset_version
    ):
        raise TransformError(
            f"clean manifest ({raw.get('dataset')} v{raw.get('version')}) does not match "
            f"configured dataset ({settings.kaggle_dataset} v"
            f"{settings.kaggle_dataset_version}); rerun clean"
        )
    manifest_tables = raw.get("tables")
    known = set(_INPUT_COLUMNS)
    missing = sorted(known - set(manifest_tables)) if isinstance(manifest_tables, dict) else known
    if missing:
        raise TransformError(
            f"{CLEAN_MANIFEST_FILE_NAME} has no entry for required tables {missing}"
        )
    return raw, digest


def _load_tables(clean_dir: Path) -> dict[str, pd.DataFrame]:
    """Read the needed columns of the 9 clean tables and normalize their date columns."""
    tables: dict[str, pd.DataFrame] = {}
    for name, columns in _INPUT_COLUMNS.items():
        path = clean_dir / f"{name}.parquet"
        if not path.is_file():
            raise TransformError(
                f"missing required clean file {path}; run `delphos-pipeline clean` first"
            )
        try:
            frame = pq.read_table(path, columns=list(columns)).to_pandas()
        except (OSError, pa.ArrowException) as exc:
            raise TransformError(f"could not read {path}: {exc}") from exc
        for column in _DATETIME_COLUMNS.get(name, ()):
            frame[column] = pd.to_datetime(frame[column])
        for column in _TEXT_DATE_COLUMNS.get(name, ()):
            frame[column] = frame[column].astype(str)
        for column in _TEXT_FLAG_COLUMNS.get(name, ()):
            frame[column] = frame[column].map({True: "1", False: "0"})
        tables[name] = frame
    return tables


def _build_indexes(
    tables: dict[str, pd.DataFrame],
) -> tuple[TrailingWindowIndex, TrailingWindowIndex]:
    """Build the full-metrics window index and the domestic-cup-minutes index.

    The cup index is a second `TrailingWindowIndex` over only the domestic-cup appearances, so
    the 13 public metrics of the shared index stay byte-identical for `analysis/eda.py`; only
    its `minutes_played` output is read, so its lineup frame is empty on purpose.
    """
    competitions = tables["competitions"]
    window = TrailingWindowIndex(
        tables["appearances"], tables["club_games"], tables["game_lineups"], competitions
    )
    cup_ids = set(competitions.loc[competitions["type"] == "domestic_cup", "competition_id"])
    cup_apps = tables["appearances"].loc[tables["appearances"]["competition_id"].isin(cup_ids)]
    empty_lineups = pd.DataFrame(
        {
            column: pd.Series(dtype="object")
            for column in ("player_id", "date", "type", "team_captain")
        }
    )
    cup_window = TrailingWindowIndex(cup_apps, tables["club_games"], empty_lineups, competitions)
    return window, cup_window


def _country_group_map(citizenship: pd.Series) -> dict[str, str]:
    """Map the top-N citizenships of the player-season population to themselves.

    Ranked by row count, ties broken alphabetically for determinism; every other country
    (including a missing citizenship) becomes `"other"` downstream. The same mapping is
    applied to the transfer rows.
    """
    counts = citizenship.dropna().value_counts()
    ranked = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
    return {str(country): str(country) for country, _ in ranked[:COUNTRY_TOP_N]}


def _ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Element-wise numerator/denominator, 0.0 where the denominator is not positive."""
    num = numerator.astype("float64")
    den = denominator.astype("float64")
    return (num / den.where(den > 0.0)).fillna(0.0)


def _with_deterministic_columns(frame: pd.DataFrame, country_map: dict[str, str]) -> pd.DataFrame:
    """Add the deterministic ratios and groupings; drop the internal helper columns."""
    derived = pd.DataFrame(
        {
            "starter_ratio": _ratio(frame["starts"], frame["apps"]),
            "captain_ratio": _ratio(frame["captain"], frame["squad_inclusions"]),
            "win_rate": _ratio(frame["win_flag"], frame["apps"]),
            "clean_sheet_rate": _ratio(frame["clean_sheet_flag"], frame["apps"]),
            "goals_conceded_per_match": _ratio(frame["goals_conceded"], frame["apps"]),
            "uefa_share": _ratio(frame["uefa_minutes"], frame["minutes"]),
            "cup_share": _ratio(frame["cup_minutes"], frame["minutes"]),
            "age_sq": frame["age"].astype("float64") ** 2,
            "country_group": (
                frame["country_of_citizenship"].map(country_map).fillna("other").astype("string")
            ),
        }
    )
    base = frame.drop(columns=["cup_minutes", "country_of_citizenship"])
    return pd.concat([base, derived], axis=1)


def _to_arrow(frame: pd.DataFrame, schema: pa.Schema) -> pa.Table:
    """Order and cast the derived frame to the stage's authoritative Arrow schema."""
    missing = [name for name in schema.names if name not in frame.columns]
    unexpected = [name for name in frame.columns if name not in schema.names]
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing columns {missing}")
        if unexpected:
            details.append(f"unexpected columns {unexpected}")
        raise TransformError(f"derived row frame does not match the schema: {'; '.join(details)}")
    try:
        arrays = [
            pa.array(frame[field.name], type=field.type, from_pandas=True) for field in schema
        ]
        return pa.Table.from_arrays(arrays, schema=schema)
    except (ValueError, TypeError, pa.ArrowException) as exc:
        raise TransformError(
            f"could not cast the derived rows to the output schema: {exc}"
        ) from exc


def _write_table(table: pa.Table, path: Path, name: str) -> None:
    try:
        pq.write_table(table, path)
    except (OSError, pa.ArrowException) as exc:
        raise TransformError(f"could not write {path}: {exc}") from exc
    typer.echo(f"  wrote {name}.parquet ({table.num_rows} rows)")


def _counts_by(frame: pd.DataFrame, column: str) -> dict[str, int]:
    counts = frame[column].value_counts().sort_index()
    return {str(key): int(value) for key, value in counts.items()}


def _table_summary(frame: pd.DataFrame, table: pa.Table, parquet_file: str) -> dict[str, Any]:
    return {
        "parquet_file": parquet_file,
        "rows": table.num_rows,
        "rows_per_split": _counts_by(frame, "split"),
        "rows_per_season": _counts_by(frame, "season"),
        "columns": table.schema.names,
        "dtypes": {field.name: str(field.type) for field in table.schema},
    }
