"""10 — Data-quality checks: impossible/inconsistent values with exact counts.

Memory approach: full loads with usecols (or full load for the small files);
checks are vectorized pandas ops.
"""
from datetime import date

import pandas as pd

from common import DATA_DIR, save

TODAY = pd.Timestamp.today().normalize()


def load(fname, cols=None):
    return pd.read_csv(DATA_DIR / fname, usecols=cols)


def num(s):
    """Coerce to numeric; '-' style sentinels become NaN."""
    return pd.to_numeric(s, errors="coerce")


def main():
    out = {}

    # ---------- appearances ----------
    a = load("appearances.csv")
    a_min, a_goals, a_assists = num(a["minutes_played"]), num(a["goals"]), num(a["assists"])
    zero_min = a_min == 0
    out["appearances"] = {
        "n_rows": int(len(a)),
        "n_negative_minutes": int((a_min < 0).sum()),
        "n_minutes_gt_130": int((a_min > 130).sum()),
        "n_zero_minutes": int(zero_min.sum()),
        "n_zero_minutes_with_goals": int((zero_min & (a_goals > 0)).sum()),
        "n_zero_minutes_with_assists": int((zero_min & (a_assists > 0)).sum()),
        "n_negative_goals": int((a_goals < 0).sum()),
        "n_negative_assists": int((a_assists < 0).sum()),
        "n_yellow_gt_2": int((num(a["yellow_cards"]) > 2).sum()),
        "n_red_gt_1": int((num(a["red_cards"]) > 1).sum()),
        "n_future_date": int((pd.to_datetime(a["date"], errors="coerce") > TODAY).sum()),
        "n_null_player_name": int(a["player_name"].isna().sum()),
    }

    # ---------- player_valuations ----------
    v = load("player_valuations.csv")
    dup_mask = v.duplicated(subset=["player_id", "date"], keep=False)
    dup_extra = v.duplicated(subset=["player_id", "date"], keep="first")
    dup_groups = v[dup_mask].groupby(["player_id", "date"])["market_value_in_eur"].nunique()
    vdate = pd.to_datetime(v["date"], errors="coerce")
    out["player_valuations"] = {
        "n_rows": int(len(v)),
        "n_dup_player_date_extra_rows": int(dup_extra.sum()),
        "n_dup_player_date_groups": int(dup_groups.shape[0]),
        "n_dup_groups_with_conflicting_values": int((dup_groups > 1).sum()),
        "n_negative_market_value": int((num(v["market_value_in_eur"]) < 0).sum()),
        "n_zero_market_value": int((num(v["market_value_in_eur"]) == 0).sum()),
        "n_future_date": int((vdate > TODAY).sum()),
        "n_date_before_2000": int((vdate < pd.Timestamp("2000-01-01")).sum()),
    }

    # ---------- transfers ----------
    t = load("transfers.csv")
    tdate = pd.to_datetime(t["transfer_date"], errors="coerce")
    out["transfers"] = {
        "n_rows": int(len(t)),
        "n_future_dated": int((tdate > TODAY).sum()),
        "max_transfer_date": str(tdate.max().date()),
        "n_self_transfer": int((t["from_club_id"] == t["to_club_id"]).sum()),
        "n_null_from_club": int(t["from_club_id"].isna().sum()),
        "n_null_to_club": int(t["to_club_id"].isna().sum()),
        "n_null_player_id": int(t["player_id"].isna().sum()),
        "n_negative_fee": int((num(t["transfer_fee"]) < 0).sum()),
    }
    # transfer_season vs year(transfer_date) consistency: season "24/25" should
    # contain the transfer date year (start year or start+1)
    season_start = t["transfer_season"].str.slice(0, 2).astype("float64") + 2000
    y = tdate.dt.year
    ok = (y == season_start) | (y == season_start + 1) | t["transfer_season"].isna()
    out["transfers"]["n_season_year_mismatch"] = int((~ok).sum())

    # name consistency: transfers player_name vs players.name
    p_names = load("players.csv", ["player_id", "name"]).set_index("player_id")["name"]
    tn = t.merge(p_names.rename("canonical"), left_on="player_id", right_index=True, how="left")
    both = tn.dropna(subset=["canonical"])
    out["transfers"]["n_name_mismatch_vs_players"] = int((both["player_name"] != both["canonical"]).sum())
    out["transfers"]["n_name_mismatch_compared"] = int(len(both))

    # club names: transfers from_club_name vs clubs.name
    c_names = load("clubs.csv", ["club_id", "name"]).set_index("club_id")["name"]
    for side in ["from", "to"]:
        tc = t.merge(c_names.rename("canonical"), left_on=f"{side}_club_id", right_index=True, how="left")
        bothc = tc.dropna(subset=["canonical"])
        out["transfers"][f"n_{side}_club_name_mismatch_vs_clubs"] = int(
            (bothc[f"{side}_club_name"] != bothc["canonical"]).sum()
        )

    # ---------- games ----------
    g = load("games.csv")
    gdate = pd.to_datetime(g["date"], errors="coerce")
    out["games"] = {
        "n_rows": int(len(g)),
        "n_future_dated": int((gdate > TODAY).sum()),
        "max_date": str(gdate.max().date()),
        "n_home_eq_away": int((g["home_club_id"] == g["away_club_id"]).sum()),
        "n_negative_goals": int(((num(g["home_club_goals"]) < 0) | (num(g["away_club_goals"]) < 0)).sum()),
        "n_null_home_goals": int(g["home_club_goals"].isna().sum()),
        "n_null_away_goals": int(g["away_club_goals"].isna().sum()),
        "n_negative_attendance": int((num(g["attendance"]) < 0).sum()),
        "n_null_attendance": int(g["attendance"].isna().sum()),
        "n_goals_sum_gt_15": int(((num(g["home_club_goals"]) + num(g["away_club_goals"])) > 15).sum()),
    }

    # ---------- game_lineups ----------
    gl = load("game_lineups.csv", ["game_lineups_id", "game_id", "player_id", "type", "team_captain", "number"])
    gl_num = num(gl["number"])
    out["game_lineups"] = {
        "n_rows": int(len(gl)),
        "n_dup_game_player_extra_rows": int(gl.duplicated(subset=["game_id", "player_id"]).sum()),
        "n_dup_game_player_type_extra_rows": int(gl.duplicated(subset=["game_id", "player_id", "type"]).sum()),
        "n_invalid_type": int((~gl["type"].isin(["starting_lineup", "substitutes"])).sum()),
        "n_invalid_captain_flag": int((~gl["team_captain"].isin([0, 1])).sum()),
        "n_non_numeric_number": int((gl_num.isna() & gl["number"].notna()).sum()),
        "n_invalid_number": int(((gl_num < 1) | (gl_num > 99)).sum()),
    }

    # ---------- game_events ----------
    ge = load("game_events.csv")
    getime = pd.to_datetime(ge["date"], errors="coerce")
    out["game_events"] = {
        "n_rows": int(len(ge)),
        "n_future_dated": int((getime > TODAY).sum()),
        "n_minute_lt_0": int((num(ge["minute"]) < 0).sum()),
        "n_minute_gt_130": int((num(ge["minute"]) > 130).sum()),
        "n_null_player_id": int(ge["player_id"].isna().sum()),
        "pct_null_player_id": round(float(ge["player_id"].isna().mean()), 6),
        "n_null_player_id_by_type_top5": [
            {"type": str(k), "count": int(c)}
            for k, c in ge[ge["player_id"].isna()]["type"].value_counts().head(5).items()
        ],
        "types": sorted(str(x) for x in ge["type"].dropna().unique()),
        "n_negative_minute": int((num(ge["minute"]) < 0).sum()),
        "negative_minute_by_type": [
            {"type": str(k), "count": int(c)}
            for k, c in ge[num(ge["minute"]) < 0]["type"].value_counts().items()
        ],
    }

    # ---------- players ----------
    p = load("players.csv")
    dob = pd.to_datetime(p["date_of_birth"], errors="coerce")
    last_season_start = pd.to_numeric(
        p["last_season"].astype(str).str.slice(0, 4), errors="coerce"
    )
    age_at_last_season = last_season_start - dob.dt.year
    out["players"] = {
        "n_rows": int(len(p)),
        "n_null_dob": int(dob.isna().sum()),
        "n_dob_in_future": int((dob > TODAY).sum()),
        "n_age_at_last_season_lt_14": int((age_at_last_season < 14).sum()),
        "n_age_at_last_season_gt_45": int((age_at_last_season > 45).sum()),
        "n_height_lt_150": int((num(p["height_in_cm"]) < 150).sum()),
        "n_height_gt_210": int((num(p["height_in_cm"]) > 210).sum()),
        "n_negative_caps": int((num(p["international_caps"]) < 0).sum()),
        "n_negative_intl_goals": int((num(p["international_goals"]) < 0).sum()),
        "n_caps_lt_intl_goals": int((num(p["international_goals"]) > num(p["international_caps"])).sum()),
        "n_negative_market_value": int((num(p["market_value_in_eur"]) < 0).sum()),
        "n_null_current_club": int(p["current_club_id"].isna().sum()),
        "n_dup_name_extra_rows": int(p.duplicated(subset=["name"]).sum()),
    }

    # ---------- club_games ----------
    cg = load("club_games.csv")
    out["club_games"] = {
        "n_rows": int(len(cg)),
        "n_club_eq_opponent": int((cg["club_id"] == cg["opponent_id"]).sum()),
        "n_negative_goals": int(((num(cg["own_goals"]) < 0) | (num(cg["opponent_goals"]) < 0)).sum()),
        "n_null_own_goals": int(cg["own_goals"].isna().sum()),
        "n_is_win_not_01": int((~cg["is_win"].isin([0, 1])).sum()),
    }

    # ---------- clubs ----------
    c = load("clubs.csv")
    out["clubs"] = {
        "n_rows": int(len(c)),
        "n_negative_total_mv": int((num(c["total_market_value"]) < 0).sum()),
        "n_null_coach": int(c["coach_name"].isna().sum()),
        "n_squad_size_gt_60": int((num(c["squad_size"]) > 60).sum()),
    }

    save("10_quality", out)
    for k, v in out.items():
        print(k, {kk: vv for kk, vv in v.items() if isinstance(vv, int) and vv})


if __name__ == "__main__":
    main()
