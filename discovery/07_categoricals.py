"""07 — Categoricals: distinct counts + top-5 values for the categorical
columns that matter for modeling.

Memory approach: value_counts accumulated in chunks for the big files
(appearances, game_events, game_lineups); full read with usecols otherwise.
"""
import pandas as pd

from common import DATA_DIR, BIG_FILES, CHUNKSIZE, save

CATS = {
    "players.csv": ["position", "sub_position", "foot", "last_season"],
    "appearances.csv": ["competition_id"],
    "games.csv": ["competition_id", "season", "competition_type"],
    "game_events.csv": ["type"],
    "game_lineups.csv": ["type", "position"],
    "transfers.csv": ["transfer_season"],
    "player_valuations.csv": ["player_club_domestic_competition_id"],
    "competitions.csv": ["type", "sub_type", "confederation"],
    "club_games.csv": ["hosting", "is_win"],
}


def top_counts(fname, col):
    path = DATA_DIR / fname
    if fname in BIG_FILES:
        vc = None
        n = 0
        n_null = 0
        for chunk in pd.read_csv(path, usecols=[col], chunksize=CHUNKSIZE):
            n += len(chunk)
            n_null += int(chunk[col].isna().sum())
            part = chunk[col].value_counts(dropna=True)
            vc = part if vc is None else vc.add(part, fill_value=0)
    else:
        s = pd.read_csv(path, usecols=[col])[col]
        n, n_null = len(s), int(s.isna().sum())
        vc = s.value_counts(dropna=True)
    vc = vc.sort_values(ascending=False)
    top = [(str(k), int(v)) for k, v in vc.head(5).items()]
    return {
        "n_rows": n,
        "n_null": n_null,
        "n_distinct": int(vc.shape[0]),
        "top5": [{"value": k, "count": int(v)} for k, v in top],
    }


def main():
    out = {}
    for fname, cols in CATS.items():
        out[fname] = {}
        for col in cols:
            res = top_counts(fname, col)
            out[fname][col] = res
            print(fname, col, "distinct:", res["n_distinct"], "top:", res["top5"][:3])
    save("07_categoricals", out)


if __name__ == "__main__":
    main()
