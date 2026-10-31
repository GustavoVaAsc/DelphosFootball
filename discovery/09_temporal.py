"""09 — Temporal coverage and alignment.

- per-table date ranges (key tables)
- game_lineups: future-dated rows (date > reference date), with examples
- games: season counts and date range per season
- transfers: per-season transfer counts
- valuations: snapshot counts per calendar year (snapshot cadence)
- valuation snapshots vs transfer dates: nearest-snapshot gap distribution and
  whether snapshots bracket transfer dates (valuation before AND after within
  symmetric windows)

Memory approach: full loads with usecols only (games 89k, transfers 175k,
valuations 656k rows); the transfers x valuations merge is a many-to-many
player_id join (~a few M rows worst case), fine in RAM.
"""
import pandas as pd

from common import DATA_DIR, save

TODAY = pd.Timestamp.today().normalize()


def main():
    out = {}

    # --- transfers per season
    t = pd.read_csv(
        DATA_DIR / "transfers.csv",
        usecols=["player_id", "transfer_date", "transfer_season"],
    )
    t["transfer_date"] = pd.to_datetime(t["transfer_date"], errors="coerce")
    vc = t["transfer_season"].value_counts()
    out["transfers_per_season"] = [
        {"season": str(k), "count": int(v)} for k, v in vc.sort_index().items()
    ]
    out["transfers_date_range"] = {
        "min": str(t["transfer_date"].min().date()),
        "max": str(t["transfer_date"].max().date()),
        "n_future_dated": int((t["transfer_date"] > TODAY).sum()),
        "n_null_date": int(t["transfer_date"].isna().sum()),
    }

    # --- game_lineups: future-dated rows (closes the "not checked" gap in section 9)
    gl = pd.read_csv(
        DATA_DIR / "game_lineups.csv",
        usecols=["game_lineups_id", "game_id", "date"],
    )
    gl["date"] = pd.to_datetime(gl["date"], errors="coerce")
    gl_fut = gl[gl["date"] > TODAY]
    out["lineups_date_range"] = {
        "n_rows": int(len(gl)),
        "min": str(gl["date"].min().date()),
        "max": str(gl["date"].max().date()),
        "n_future_dated": int(len(gl_fut)),
        "pct_future_dated": round(len(gl_fut) / len(gl), 6),
        "n_null_date": int(gl["date"].isna().sum()),
        "min_future_date": str(gl_fut["date"].min().date()) if len(gl_fut) else None,
        "max_future_date": str(gl_fut["date"].max().date()) if len(gl_fut) else None,
        "future_examples": [
            {
                "game_lineups_id": str(r["game_lineups_id"]),
                "game_id": int(r["game_id"]),
                "date": str(r["date"].date()),
            }
            for _, r in gl_fut.head(5).iterrows()
        ],
    }

    # --- games: seasons
    g = pd.read_csv(DATA_DIR / "games.csv", usecols=["season", "date"])
    g["date"] = pd.to_datetime(g["date"], errors="coerce")
    per_season = g.groupby("season")["date"].agg(["count", "min", "max"])
    out["games_per_season"] = [
        {
            "season": str(idx),
            "count": int(r["count"]),
            "min_date": str(r["min"].date()) if pd.notna(r["min"]) else None,
            "max_date": str(r["max"].date()) if pd.notna(r["max"]) else None,
        }
        for idx, r in per_season.iterrows()
    ]

    # --- valuation snapshots per year
    v = pd.read_csv(
        DATA_DIR / "player_valuations.csv",
        usecols=["player_id", "date", "market_value_in_eur"],
    )
    v["date"] = pd.to_datetime(v["date"], errors="coerce")
    yearly = v["date"].dt.year.value_counts().sort_index()
    out["valuation_snapshots_per_year"] = [
        {"year": int(y), "count": int(c)} for y, c in yearly.items()
    ]
    out["valuations_date_range"] = {
        "min": str(v["date"].min().date()),
        "max": str(v["date"].max().date()),
        "n_future_dated": int((v["date"] > TODAY).sum()),
    }

    # --- valuation snapshots vs transfer dates
    t["tid"] = t.index  # stable per-transfer row id across the merge
    m = t.merge(v[["player_id", "date", "market_value_in_eur"]], on="player_id", how="left")
    m["gap_days"] = (m["date"] - m["transfer_date"]).dt.days
    m["abs_gap"] = m["gap_days"].abs()
    gaps = m.groupby("tid")["abs_gap"].min().dropna()  # nearest snapshot, any direction
    out["transfer_to_nearest_valuation_gap_days"] = {
        "n_transfers": int(len(t)),
        "n_with_any_snapshot": int(gaps.shape[0]),
        "pct_without_any_snapshot": round(1 - gaps.shape[0] / len(t), 6),
        "p50": float(gaps.quantile(0.50)),
        "p90": float(gaps.quantile(0.90)),
        "pct_within_7d": float((gaps <= 7).mean()),
        "pct_within_30d": float((gaps <= 30).mean()),
        "pct_within_90d": float((gaps <= 90).mean()),
    }
    # bracketing: snapshot before AND after the transfer within +-365d
    in_window = m[m["gap_days"].abs() <= 365]
    tids_before = set(in_window[in_window["gap_days"] <= 0]["tid"])
    tids_after = set(in_window[in_window["gap_days"] >= 0]["tid"])
    out["valuation_brackets_transfer"] = {
        "pct_with_snapshot_in_minus365d": round(len(tids_before) / len(t), 6),
        "pct_with_snapshot_in_plus365d": round(len(tids_after) / len(t), 6),
        "pct_bracketed_within_365d": round(len(tids_before & tids_after) / len(t), 6),
    }
    save("09_temporal", out)
    print("lineups date range:", out["lineups_date_range"])
    print("transfers date range:", out["transfers_date_range"])
    print("gap:", out["transfer_to_nearest_valuation_gap_days"])
    print("bracketed:", out["valuation_brackets_transfer"])


if __name__ == "__main__":
    main()
