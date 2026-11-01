"""July-to-June season assignment and chronological split labels for the snapshot rows.

Input: pandas Series of dates (valuation or transfer dates) and season start years.
Output: the season start year per date (`season_of`) and the split label per season
(`assign_split`).
Responsibility: own the two deterministic calendar rules the snapshot population and every
downstream split depend on.

`season_of` and `assign_split` are small related functions kept together on purpose: the team
convention (root AGENTS.md section 4) is about file length, not one symbol per file, and two
tiny calendar rules do not justify a file each.
"""

from __future__ import annotations

import pandas as pd

SEASON_MONTH_START = 7

_SPLIT_BY_SEASON: dict[int, str] = {
    **{season: "train" for season in range(2017, 2024)},
    2024: "validation",
    2025: "test",
}

_SEASON_RANGE_HINT = "expected 2017 to 2025"


def season_of(dates: pd.Series) -> pd.Series:
    """Return the July-to-June season start year for each date.

    A date in July or later belongs to the season starting in its own calendar year; a date
    before July belongs to the season that started in the previous year, so 2024-06-30 is
    season 2023 and 2024-07-01 is season 2024.
    """
    parsed = pd.Series(dates)
    return (parsed.dt.year - (parsed.dt.month < SEASON_MONTH_START).astype("int64")).astype("int64")


def assign_split(season: int | pd.Series) -> str | pd.Series:
    """Map each season start year to its chronological split label.

    Seasons 2017 to 2023 map to `train`, 2024 to `validation`, and 2025 to `test`. Any other
    season raises `ValueError` instead of silently landing in a split.
    """
    if isinstance(season, pd.Series):
        unknown = [value for value in season.unique() if value not in _SPLIT_BY_SEASON]
        if unknown:
            raise ValueError(f"unknown season {unknown[0]}; {_SEASON_RANGE_HINT}")
        return season.map(_SPLIT_BY_SEASON).astype("string")
    try:
        return _SPLIT_BY_SEASON[season]
    except KeyError:
        raise ValueError(f"unknown season {season}; {_SEASON_RANGE_HINT}") from None
