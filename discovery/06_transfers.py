"""06 — Transfer-fee semantics: null vs zero vs positive vs negative fees,
free-transfer counts, fee vs market-value ratio distribution, outliers.

Memory approach: transfers.csv is ~175k rows; reads only the needed columns
via usecols, full load (small).
"""
import pandas as pd

from common import DATA_DIR, save

RATIOS = [0.01, 0.05, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]


def main():
    t = pd.read_csv(
        DATA_DIR / "transfers.csv",
        usecols=["player_id", "transfer_date", "transfer_season", "transfer_fee", "market_value_in_eur"],
    )
    fee = pd.to_numeric(t["transfer_fee"], errors="coerce")
    mv = pd.to_numeric(t["market_value_in_eur"], errors="coerce")
    n = len(t)

    out = {"n_rows": n}
    out["transfer_fee_semantics"] = {
        "n_null": int(fee.isna().sum()),
        "n_zero": int((fee == 0).sum()),
        "n_positive": int((fee > 0).sum()),
        "n_negative": int((fee < 0).sum()),
        "min_positive": float(fee[fee > 0].min()) if (fee > 0).any() else None,
        "pct_zero": round(float((fee == 0).mean()), 6),
    }
    # fee==0 rows: how many still carry a positive market value (=> free or undisclosed)
    zero_mask = fee == 0
    out["zero_fee_breakdown"] = {
        "n_zero_fee_with_positive_mv": int(((mv > 0) & zero_mask).sum()),
        "n_zero_fee_with_null_mv": int((mv.isna() & zero_mask).sum()),
    }

    # small positive fees (potential undisclosed/sentinel pattern)
    pos = fee[fee > 0]
    out["small_positive_fees"] = {
        "n_fee_eq_1": int((pos == 1).sum()),
        "n_fee_lt_10k": int((pos < 10_000).sum()),
        "n_fee_lt_1k": int((pos < 1_000).sum()),
    }

    # fee vs market value at transfer date
    mask = (fee > 0) & (mv > 0)
    ratio = (fee[mask] / mv[mask])
    q = ratio.quantile(RATIOS)
    out["fee_vs_market_value"] = {
        "n_comparable": int(mask.sum()),
        "ratio_quantiles": {f"p{int(p * 100)}": float(q.loc[p]) for p in RATIOS},
        "n_fee_gt_2x_mv": int((ratio > 2).sum()),
        "n_fee_gt_5x_mv": int((ratio > 5).sum()),
        "n_fee_lt_half_mv": int((ratio < 0.5).sum()),
        "n_fee_lt_tenth_mv": int((ratio < 0.1).sum()),
    }
    # same comparison using transfers.market_value_in_eur vs the player's nearest
    # valuation snapshot is done in 09_temporal; here we just note nulls
    out["market_value_col"] = {
        "n_null": int(mv.isna().sum()),
        "n_zero": int((mv == 0).sum()),
        "n_negative": int((mv < 0).sum()),
    }
    save("06_transfers", out)
    print(out["transfer_fee_semantics"])
    print(out["fee_vs_market_value"]["ratio_quantiles"])


if __name__ == "__main__":
    main()
