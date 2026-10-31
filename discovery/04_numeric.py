"""04 — Numeric summaries (min/max/mean/median/p25/p75/p99 + zeros/negatives)
for every numeric column of interest, per file.

Memory approach: reads ONLY the listed numeric columns via usecols and coerces
them with pd.to_numeric(errors="coerce"); for the big three files the read is
chunked (numbers are accumulated exactly via chunk concat of the selected
columns, which is small: a handful of int columns over a few M rows).
"""
import pandas as pd

from common import DATA_DIR, BIG_FILES, CHUNKSIZE, save

NUMERIC_COLS = {
    "appearances.csv": ["yellow_cards", "red_cards", "goals", "assists", "minutes_played"],
    "club_games.csv": ["own_goals", "own_position", "opponent_goals", "opponent_position", "is_win"],
    "clubs.csv": [
        "total_market_value", "squad_size", "average_age", "foreigners_number",
        "foreigners_percentage", "national_team_players", "stadium_seats",
    ],
    "competitions.csv": ["total_clubs"],
    "countries.csv": ["total_clubs", "total_players", "average_age"],
    "game_events.csv": ["minute"],
    "game_lineups.csv": ["number", "team_captain"],
    "games.csv": [
        "home_club_goals", "away_club_goals", "home_club_position",
        "away_club_position", "attendance",
    ],
    "national_teams.csv": [
        "squad_size", "average_age", "foreigners_number", "foreigners_percentage",
        "total_market_value", "fifa_ranking",
    ],
    "players.csv": [
        "height_in_cm", "international_caps", "international_goals",
        "market_value_in_eur", "highest_market_value_in_eur",
    ],
    "player_valuations.csv": ["market_value_in_eur"],
    "transfers.csv": ["transfer_fee", "market_value_in_eur"],
}

QUANTILES = [0.25, 0.50, 0.75, 0.99]


def summarize(s: pd.Series) -> dict:
    s = pd.to_numeric(s, errors="coerce")
    valid = s.dropna()
    if len(valid) == 0:
        return {"n_non_null": 0}
    q = valid.quantile(QUANTILES)
    return {
        "n_non_null": int(valid.shape[0]),
        "n_null": int(s.isna().sum()),
        "min": float(valid.min()),
        "max": float(valid.max()),
        "mean": float(valid.mean()),
        "median": float(q.loc[0.50]),
        "p25": float(q.loc[0.25]),
        "p75": float(q.loc[0.75]),
        "p99": float(q.loc[0.99]),
        "n_zero": int((valid == 0).sum()),
        "n_negative": int((valid < 0).sum()),
    }


def load_numeric(fname):
    cols = NUMERIC_COLS[fname]
    path = DATA_DIR / fname
    if fname in BIG_FILES:
        series = {c: [] for c in cols}
        for chunk in pd.read_csv(path, usecols=cols, chunksize=CHUNKSIZE):
            for c in cols:
                series[c].append(chunk[c])
        return {c: pd.concat(v, ignore_index=True) for c, v in series.items()}
    df = pd.read_csv(path, usecols=cols)
    return {c: df[c] for c in cols}


def parse_net_transfer_record(s: pd.Series) -> pd.Series:
    """clubs.net_transfer_record is a string like '+€5.90m' or '€-25.00m'."""
    x = s.astype("string").str.replace("€", "", regex=False).str.strip()
    x = x.str.replace("m$", "", regex=True)
    return pd.to_numeric(x, errors="coerce") * 1_000_000


def main():
    out = {}
    for fname, cols in NUMERIC_COLS.items():
        data = load_numeric(fname)
        out[fname] = {c: summarize(data[c]) for c in cols}
        print(fname, {c: out[fname][c].get("median") for c in cols})
    # string-formatted money column, parsed to numeric EUR
    clubs = pd.read_csv(DATA_DIR / "clubs.csv", usecols=["net_transfer_record"])
    out["clubs.csv"]["net_transfer_record (parsed from string like '+5.90m')"] = summarize(
        parse_net_transfer_record(clubs["net_transfer_record"])
    )
    save("04_numeric", out)


if __name__ == "__main__":
    main()
