"""08 — Referential integrity: orphan counts/rates for cross-file key
references (player_id -> players, game_id -> games, club_id -> clubs,
competition_id -> competitions).

Memory approach: dimension keys loaded once as sets; big fact tables are
streamed in chunks and orphan counts accumulated. Rates are computed over
non-null values (nulls reported separately).
"""
import pandas as pd

from common import DATA_DIR, BIG_FILES, CHUNKSIZE, save


def dim_set(fname, col):
    return set(pd.read_csv(DATA_DIR / fname, usecols=[col])[col].dropna().unique())


PLAYERS = dim_set("players.csv", "player_id")
GAMES = dim_set("games.csv", "game_id")
CLUBS = dim_set("clubs.csv", "club_id")
COMPETITIONS = dim_set("competitions.csv", "competition_id")

NATIONAL_TEAMS = dim_set("national_teams.csv", "national_team_id")

DIMS = {"players": PLAYERS, "games": GAMES, "clubs": CLUBS, "competitions": COMPETITIONS,
        "national_teams": NATIONAL_TEAMS}

# fact file -> list of (column, dimension, [extra: treat 0 or -1 as null?])
CHECKS = {
    "appearances.csv": [
        ("player_id", "players"), ("game_id", "games"),
        ("player_club_id", "clubs"), ("player_current_club_id", "clubs"),
        ("competition_id", "competitions"),
    ],
    "club_games.csv": [
        ("game_id", "games"), ("club_id", "clubs"), ("opponent_id", "clubs"),
    ],
    "games.csv": [
        ("home_club_id", "clubs"), ("away_club_id", "clubs"),
        ("competition_id", "competitions"),
    ],
    "player_valuations.csv": [("player_id", "players"), ("current_club_id", "clubs")],
    "transfers.csv": [("player_id", "players"), ("from_club_id", "clubs"), ("to_club_id", "clubs")],
    "game_events.csv": [("game_id", "games"), ("player_id", "players"), ("club_id", "clubs")],
    "game_lineups.csv": [("game_id", "games"), ("player_id", "players"), ("club_id", "clubs")],
    "players.csv": [("current_club_id", "clubs"), ("current_national_team_id", "national_teams")],
}


def check(fname):
    cols = sorted({c for c, _ in CHECKS[fname]})
    res = {
        c: {"n_non_null": 0, "n_orphan": 0, "n_null": 0, "orphan_examples": set()}
        for c in cols
    }

    def accumulate(chunk):
        for c, dim in CHECKS[fname]:
            s = chunk[c]
            nn = s.dropna()
            res[c]["n_null"] += int(s.isna().sum())
            res[c]["n_non_null"] += int(nn.shape[0])
            mask = ~nn.isin(DIMS[dim])
            res[c]["n_orphan"] += int(mask.sum())
            for v in nn[mask].unique()[:5]:
                res[c]["orphan_examples"].add(str(v))

    if fname in BIG_FILES:
        for chunk in pd.read_csv(DATA_DIR / fname, usecols=cols, chunksize=CHUNKSIZE):
            accumulate(chunk)
    else:
        accumulate(pd.read_csv(DATA_DIR / fname, usecols=cols))
    out = {}
    for c, r in res.items():
        dim = dict(CHECKS[fname])[c]
        out[f"{c} -> {dim}"] = {
            "n_non_null": r["n_non_null"],
            "n_null": r["n_null"],
            "n_orphan": r["n_orphan"],
            "orphan_rate_over_non_null": round(r["n_orphan"] / r["n_non_null"], 8) if r["n_non_null"] else None,
            "orphan_examples": sorted(r["orphan_examples"])[:5],
        }
    return out


def main():
    out = {}
    for fname in CHECKS:
        out[fname] = check(fname)
        for k, v in out[fname].items():
            print(fname, k, "orphans:", v["n_orphan"], "rate:", v["orphan_rate_over_non_null"])
    save("08_referential", out)


if __name__ == "__main__":
    main()
