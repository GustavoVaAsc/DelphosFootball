"""Shared config for the throwaway Transfermarkt dataset profiling scripts.

All scripts in discovery/ are read-only with respect to data/Dataset/ and only
write JSON results into discovery/results/ (plus the final markdown rendered
into docs/DATA_DISCOVERY.md by render_report.py).

Environment: discovery/.venv (python3 -m venv + pip install pandas).
Run everything with:  bash discovery/run_all.sh
"""
from pathlib import Path
import json

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "Dataset"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "DATA_DISCOVERY.md"

FILES = [
    "appearances.csv",
    "club_games.csv",
    "clubs.csv",
    "competitions.csv",
    "countries.csv",
    "game_events.csv",
    "game_lineups.csv",
    "games.csv",
    "national_teams.csv",
    "players.csv",
    "player_valuations.csv",
    "transfers.csv",
]

# Big files are always read in chunks (or with usecols) to bound memory.
BIG_FILES = {"appearances.csv", "game_events.csv", "game_lineups.csv"}
CHUNKSIZE = 250_000

# Primary-key candidates to verify per file (tuple => composite key).
PK_CANDIDATES = {
    "appearances.csv": ("appearance_id",),
    "club_games.csv": ("game_id", "club_id"),
    "clubs.csv": ("club_id",),
    "competitions.csv": ("competition_id",),
    "countries.csv": ("country_id",),
    "game_events.csv": ("game_event_id",),
    "game_lineups.csv": ("game_lineups_id",),
    "games.csv": ("game_id",),
    "national_teams.csv": ("national_team_id",),
    "players.csv": ("player_id",),
    "player_valuations.csv": ("player_id", "date"),
    "transfers.csv": (),  # no obvious PK; verified dups reported instead
}


def save(name: str, obj) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{name}.json"
    path.write_text(json.dumps(_jsonable(obj), indent=1, ensure_ascii=False))
    print(f"[{name}] wrote {path}")


def load(name: str):
    return json.loads((RESULTS_DIR / f"{name}.json").read_text())


def _jsonable(obj):
    """Convert numpy/pandas scalars to plain python for json.dumps."""
    import numpy as np
    import pandas as pd

    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        f = float(obj)
        return None if f != f else f  # NaN -> null
    if isinstance(obj, np.bool_):
        return bool(obj)
    if obj is pd.NA or (isinstance(obj, float) and obj != obj):
        return None
    return obj


def fmt_bytes(n: int) -> str:
    return f"{n / 1_048_576:.1f} MB"
