"""05 — Target analysis: distribution of market_value_in_eur (player_valuations
history + players.csv current snapshot), zeros/negatives, quantiles incl.
p1/p5/p95, log-transform diagnostics, valuation coverage and per-player
valuation-history depth.

Memory approach: reads only (player_id, date, market_value_in_eur) via usecols
(656k rows, fits comfortably); players.csv subset likewise.
"""
import numpy as np
import pandas as pd

from common import DATA_DIR, save

QPS = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]


def dist(s: pd.Series, label: str) -> dict:
    valid = pd.to_numeric(s, errors="coerce").dropna()
    q = valid.quantile(QPS)
    return {
        "label": label,
        "n": int(valid.shape[0]),
        "min": float(valid.min()),
        "max": float(valid.max()),
        "mean": float(valid.mean()),
        "std": float(valid.std()),
        "skew": float(valid.skew()),
        "quantiles": {f"p{int(p * 100)}": float(q.loc[p]) for p in QPS},
        "n_zero": int((valid == 0).sum()),
        "n_negative": int((valid < 0).sum()),
        "pct_top1pct_share_of_sum": float(valid[valid >= q.loc[0.99]].sum() / valid.sum()),
    }


def log_diag(s: pd.Series) -> dict:
    v = pd.to_numeric(s, errors="coerce").dropna()
    v = v[v >= 0]
    lv = np.log1p(v)
    return {
        "log1p_skew": float(pd.Series(lv).skew()),
        "raw_skew": float(v.skew()),
        "log1p_mean": float(lv.mean()),
        "log1p_std": float(lv.std()),
        "log1p_quantiles": {
            f"p{int(p * 100)}": float(np.quantile(lv, p)) for p in QPS
        },
    }


def main():
    val = pd.read_csv(
        DATA_DIR / "player_valuations.csv",
        usecols=["player_id", "date", "market_value_in_eur"],
    )
    players = pd.read_csv(
        DATA_DIR / "players.csv",
        usecols=["player_id", "market_value_in_eur", "highest_market_value_in_eur"],
    )

    out = {}
    out["valuations_history"] = dist(val["market_value_in_eur"], "player_valuations.market_value_in_eur (all snapshots)")
    out["players_current_value"] = dist(players["market_value_in_eur"], "players.market_value_in_eur (current snapshot)")
    out["players_highest_value"] = dist(players["highest_market_value_in_eur"], "players.highest_market_value_in_eur (post-hoc; leakage)")
    out["log_transform_diag"] = log_diag(val["market_value_in_eur"])

    # coverage: players with vs without any valuation history
    players_with_val = set(val["player_id"].dropna().unique())
    all_players = set(players["player_id"].dropna().unique())
    out["coverage"] = {
        "n_players_in_players_csv": len(all_players),
        "n_players_with_valuation_history": len(players_with_val & all_players),
        "n_players_without_valuation_history": len(all_players - players_with_val),
        "n_valuation_player_ids_not_in_players_csv": len(players_with_val - all_players),
    }

    # valuation-history depth per player
    depth = val.groupby("player_id").size()
    out["history_depth_per_player"] = {
        "min": int(depth.min()),
        "median": float(depth.median()),
        "mean": float(depth.mean()),
        "p90": float(depth.quantile(0.90)),
        "p99": float(depth.quantile(0.99)),
        "max": int(depth.max()),
        "histogram": {
            "1": int((depth == 1).sum()),
            "2-5": int(((depth >= 2) & (depth <= 5)).sum()),
            "6-10": int(((depth >= 6) & (depth <= 10)).sum()),
            "11-20": int(((depth >= 11) & (depth <= 20)).sum()),
            "21-50": int(((depth >= 21) & (depth <= 50)).sum()),
            ">50": int((depth > 50).sum()),
        },
    }

    # is players.market_value_in_eur the last snapshot or the max-ever?
    last_val = val.sort_values("date").groupby("player_id").tail(1).set_index("player_id")
    max_val = val.groupby("player_id")["market_value_in_eur"].max()
    p = players.dropna(subset=["player_id"]).set_index("player_id")
    cmp = pd.DataFrame(
        {
            "current": p["market_value_in_eur"],
            "last": last_val["market_value_in_eur"],
            "maxever": max_val,
        }
    ).dropna()
    out["players_value_vs_history"] = {
        "n_comparable": int(len(cmp)),
        "pct_equal_last_snapshot": float((cmp["current"] == cmp["last"]).mean()),
        "pct_equal_max_ever": float((cmp["current"] == cmp["maxever"]).mean()),
    }

    save("05_target", out)
    print("coverage:", out["coverage"])
    print("depth:", out["history_depth_per_player"]["histogram"])


if __name__ == "__main__":
    main()
