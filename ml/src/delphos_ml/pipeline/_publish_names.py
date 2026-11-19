"""The candidate names the scouting report can carry (LLM_PLAN §7.3).

Input: the clean stage's players Parquet and the evaluate stage's replacements
Parquet. Output: nothing, or a ValueError naming the offending row.
Responsibility: refuse to publish a candidate name the scouting report cannot
represent, so the report request never carries a name that reads like an
instruction.

The names come from the source dataset and are published in `analytics.dim_players`;
the report request renders every one of them as a JSON string, which keeps a name
from starting a token, and joins them with " | ", which keeps a comma from acting
as a separator. A name that carries an instruction is still an instruction the model
may follow, so the row is refused here: that is a DATA problem, and it must surface
before the row reaches the database rather than inside a report a director reads.

The rule mirrors the backend's `report_names.unrepresentable_reason`: the two
components are separate uv projects, so the check is stated twice and kept in step
by hand. Both refuse a control character (Cc), a format character (Cf — a bidi
override), a line or paragraph separator (Zl, Zp) and a surrogate (Cs), and both
refuse a comma. The check FAILS CLOSED: a missing or renamed input is an error,
not a silent "nothing to validate" — a gate that validates nothing because it
could not read its input is worse than no gate.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pyarrow.parquet as pq

PLAYERS_PARQUET = "clean/players.parquet"
REPLACEMENTS_PARQUET = "evaluate/replacements.parquet"

_REFUSED_CATEGORIES = ("Cc", "Cf", "Zl", "Zp", "Cs")
"""The Unicode categories a name may not contain: controls, formats, separators."""


def validate_candidate_names(data_dir: Path) -> None:
    """Raise ValueError naming the row whose candidate name cannot be represented.

    Fails closed: a missing input, or one without the expected columns, is an
    error. A gate that cannot read its input must not report success.
    """
    names = _player_names(data_dir / PLAYERS_PARQUET)
    for row in _replacement_rows(data_dir / REPLACEMENTS_PARQUET):
        name = names.get(row["candidate_player_id"])
        if name is None:
            continue
        reason = unrepresentable_reason(name)
        if reason is not None:
            raise ValueError(
                "the candidate name of the replacement row "
                f"(target_player_id={row['target_player_id']}, rank={row['rank']}, "
                f"candidate_player_id={row['candidate_player_id']}) cannot be carried by "
                f"the scouting report: {reason}. Name: {name!r}"
            )


def unrepresentable_reason(name: str) -> str | None:
    """Why the name cannot be represented, or None when it can."""
    for character in name:
        category = unicodedata.category(character)
        if category in _REFUSED_CATEGORIES:
            return f"it contains a {category} character ({character!r})"
    if "," in name:
        return "it contains a comma, which makes the name ambiguous in a listing"
    return None


def _player_names(path: Path) -> dict[int, str]:
    """The published players' names, keyed by player id."""
    if not path.is_file():
        raise ValueError(f"the players Parquet {path} is missing; the name check cannot run")
    table = pq.read_table(path, columns=["player_id", "name"])
    return {int(row["player_id"]): str(row["name"]) for row in table.to_pylist()}


def _replacement_rows(path: Path) -> list[dict[str, object]]:
    """The replacement rows that name a candidate. Fails closed on a missing input.

    A file that exists but carries no candidate id column holds no candidate
    names, so there is nothing to refuse; a file that is MISSING is an error,
    because a gate that cannot read its input must not report success.
    """
    if not path.is_file():
        raise ValueError(f"the replacements Parquet {path} is missing; the name check cannot run")
    columns = pq.ParquetFile(path).schema.names
    wanted = ["target_player_id", "rank", "candidate_player_id"]
    if "candidate_player_id" not in columns:
        return []
    return pq.read_table(path, columns=wanted).to_pylist()
