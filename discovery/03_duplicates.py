"""03 — Duplicates: full-row duplicates and key-level duplicates per file.

Memory approach: full-row duplicate detection needs every column, so each file
is loaded once in full with dtype=str (pandas 3's compact string dtype keeps
game_lineups ~416MB CSV within ~a few GB of RAM; the machine has >20GB free).
Key-level duplicates then reuse the loaded frame.
"""
import pandas as pd

from common import DATA_DIR, save

# Key tuples whose uniqueness/duplication rate matters for the modeling design.
KEY_CHECKS = {
    "appearances.csv": [("appearance_id",), ("player_id", "game_id")],
    "club_games.csv": [("game_id", "club_id"), ("game_id",)],
    "clubs.csv": [("club_id",)],
    "competitions.csv": [("competition_id",)],
    "countries.csv": [("country_id",)],
    "game_events.csv": [("game_event_id",), ("game_id", "player_id", "type", "minute")],
    "game_lineups.csv": [
        ("game_lineups_id",),
        ("game_id", "player_id"),
        ("game_id", "player_id", "type"),
    ],
    "games.csv": [("game_id",)],
    "national_teams.csv": [("national_team_id",)],
    "players.csv": [("player_id",), ("name",)],
    "player_valuations.csv": [("player_id", "date")],
    "transfers.csv": [
        ("player_id", "transfer_date", "from_club_id", "to_club_id"),
        ("player_id", "transfer_date"),
    ],
}


def main():
    out = {}
    for fname, keysets in KEY_CHECKS.items():
        df = pd.read_csv(DATA_DIR / fname, dtype=str)
        n = len(df)
        full_dup = int(df.duplicated().sum())
        keys = []
        for key in keysets:
            ndup = int(df.duplicated(subset=list(key)).sum())
            keys.append(
                {
                    "columns": list(key),
                    "n_duplicate_rows": ndup,
                    "duplicate_rate": round(ndup / n, 6) if n else None,
                }
            )
        out[fname] = {
            "n_rows": n,
            "full_row_duplicates": full_dup,
            "full_row_duplicate_rate": round(full_dup / n, 6) if n else None,
            "key_checks": keys,
        }
        print(fname, "full dups:", full_dup, "; key dups:", [(k["columns"], k["n_duplicate_rows"]) for k in keys])
        del df
    save("03_duplicates", out)


if __name__ == "__main__":
    main()
