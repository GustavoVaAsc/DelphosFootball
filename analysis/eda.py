"""Exploratory data analysis over the ingested Transfermarkt Parquet tables.

Input: `<data dir>/ingest/*.parquet` and `<data dir>/ingest/_snapshot.json` resolved through
`delphos_ml.config.load_settings()`.
Output: CSV summary tables, `summary.json`, and six PNG figures under
`<repo root>/analysis/output/eda/`. Writes nothing to PostgreSQL.
Responsibility: quantify schema quality, missingness and string sentinels, seasonal and
competition coverage, target log-normality and market inflation, the population funnel under
Option A (one end-of-season valuation snapshot per player-season) versus Option B (all valuation
rows), Empirical Bayes minute-smoothing stability, static-column temporal leakage in `players`,
`game_events` marginal signal, and paid-transfer join survival for the market inefficiency test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import seaborn as sns
from scipy import stats

from delphos_ml.config import ConfigError, find_project_root, load_settings
from delphos_ml.features.windows import TrailingWindowIndex

EXPECTED_TABLES: tuple[str, ...] = (
    "appearances",
    "club_games",
    "clubs",
    "competitions",
    "countries",
    "game_events",
    "game_lineups",
    "games",
    "national_teams",
    "player_valuations",
    "players",
    "transfers",
)

PRIMARY_KEYS: dict[str, list[str]] = {
    "appearances": ["appearance_id"],
    "club_games": ["game_id", "club_id"],
    "clubs": ["club_id"],
    "competitions": ["competition_id"],
    "countries": ["country_id"],
    "game_events": ["game_event_id"],
    "game_lineups": ["game_lineups_id"],
    "games": ["game_id"],
    "national_teams": ["national_team_id"],
    "player_valuations": ["player_id", "date"],
    "players": ["player_id"],
    "transfers": ["player_id", "transfer_date", "from_club_id", "to_club_id"],
}

BIG5_COMPETITION_IDS: frozenset[str] = frozenset({"GB1", "ES1", "IT1", "L1", "FR1"})
CORE_14_LEAGUE_IDS: frozenset[str] = frozenset(
    {
        "GB1",
        "ES1",
        "IT1",
        "L1",
        "FR1",
        "PO1",
        "NL1",
        "BE1",
        "TR1",
        "RU1",
        "SC1",
        "DK1",
        "GR1",
        "UKR1",
    }
)
EPOCH_ANCHOR = pd.Timestamp("1900-01-01")


def _fail(reason: str) -> None:
    print(f"eda failed: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _load_tables(ingest_dir: Path) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    snapshot_path = ingest_dir / "_snapshot.json"
    if not snapshot_path.is_file():
        _fail(f"missing {snapshot_path}; run `uv run delphos-pipeline ingest` from ml/ first")
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot read {snapshot_path}: {exc}")

    frames: dict[str, pd.DataFrame] = {}
    for name in EXPECTED_TABLES:
        parquet_path = ingest_dir / f"{name}.parquet"
        if not parquet_path.is_file():
            _fail(f"missing table file {parquet_path}")
        table = pq.read_table(parquet_path)
        frames[name] = table.to_pandas()
    return snapshot, frames


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _to_days(date_series: pd.Series) -> tuple[pd.Series, pd.Series]:
    sliced = date_series.str.slice(0, 10)
    parsed = pd.to_datetime(sliced, format="%Y-%m-%d", errors="coerce")
    days = (parsed - EPOCH_ANCHOR).dt.days
    return parsed, days


def _season_from_dates(dates: pd.Series) -> pd.Series:
    return dates.dt.year.where(dates.dt.month >= 7, dates.dt.year - 1)


def _audit_tables_and_missingness(
    frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    inv_rows: list[dict[str, Any]] = []
    miss_rows: list[dict[str, Any]] = []

    date_cols: dict[str, str] = {
        "appearances": "date",
        "game_events": "date",
        "game_lineups": "date",
        "games": "date",
        "player_valuations": "date",
        "players": "date_of_birth",
        "transfers": "transfer_date",
    }

    for name, df in frames.items():
        n_rows, n_cols = df.shape
        pk_cols = PRIMARY_KEYS[name]
        pk_non_null = df.dropna(subset=pk_cols)
        dup_pk = int(pk_non_null.duplicated(subset=pk_cols).sum())
        exact_dups = int(df.duplicated().sum())

        min_date = ""
        max_date = ""
        if name in date_cols:
            parsed, _ = _to_days(df[date_cols[name]])
            valid_dates = parsed.dropna()
            if not valid_dates.empty:
                min_date = str(valid_dates.min().date())
                max_date = str(valid_dates.max().date())

        inv_rows.append(
            {
                "table": name,
                "rows": n_rows,
                "columns": n_cols,
                "primary_key": "+".join(pk_cols),
                "duplicate_pk_rows": dup_pk,
                "exact_duplicate_rows": exact_dups,
                "date_column": date_cols.get(name, ""),
                "min_date": min_date,
                "max_date": max_date,
            }
        )

        for col in df.columns:
            s = df[col]
            null_count = int(s.isna().sum())
            non_null = s.dropna()
            empty_str = int((non_null == "").sum())
            dash_str = int((non_null == "-").sum())
            zero_str = int(non_null.isin(["0", "0.0", "0.00", "0.000"]).sum())
            has_decimal_dot = int(non_null.str.contains(r"^\d+\.\d+$", regex=True).sum())
            miss_rows.append(
                {
                    "table": name,
                    "column": col,
                    "rows": n_rows,
                    "null_count": null_count,
                    "null_pct": round(100.0 * null_count / max(n_rows, 1), 3),
                    "empty_string_count": empty_str,
                    "dash_sentinel_count": dash_str,
                    "zero_literal_count": zero_str,
                    "decimal_numeric_count": has_decimal_dot,
                    "distinct_non_null": int(non_null.nunique(dropna=True)),
                }
            )

    return pd.DataFrame(inv_rows), pd.DataFrame(miss_rows)


def _audit_coverage(
    frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    games = frames["games"]
    apps = frames["appearances"]
    lineups = frames["game_lineups"]
    vals = frames["player_valuations"]
    transfers = frames["transfers"]
    comps = frames["competitions"]

    g_dates, _ = _to_days(games["date"])
    g_season_num = _to_numeric(games["season"]).astype("Int64")
    derived_g_season = _season_from_dates(g_dates).astype("Int64")
    both_valid = g_season_num.notna() & derived_g_season.notna()
    season_match_pct = float(
        100.0 * (g_season_num[both_valid] == derived_g_season[both_valid]).mean()
    )

    a_dates, _ = _to_days(apps["date"])
    l_dates, _ = _to_days(lineups["date"])
    v_dates, _ = _to_days(vals["date"])
    t_dates, _ = _to_days(transfers["transfer_date"])

    g_by_s = g_season_num.value_counts().rename("games")
    a_by_s = _season_from_dates(a_dates).astype("Int64").value_counts().rename("appearances")
    l_by_s = _season_from_dates(l_dates).astype("Int64").value_counts().rename("game_lineups")
    v_by_s = _season_from_dates(v_dates).astype("Int64").value_counts().rename("player_valuations")
    t_by_s = _season_from_dates(t_dates).astype("Int64").value_counts().rename("transfers")

    core14_g_mask = games["competition_id"].isin(CORE_14_LEAGUE_IDS)
    core14_a_mask = apps["competition_id"].isin(CORE_14_LEAGUE_IDS)
    core14_g_by_s = g_season_num[core14_g_mask].value_counts().rename("core14_games")
    core14_a_by_s = (
        _season_from_dates(a_dates[core14_a_mask])
        .astype("Int64")
        .value_counts()
        .rename("core14_appearances")
    )

    seasons_idx = pd.Index(range(2004, 2026), name="season")
    seasonal = (
        pd.concat([g_by_s, a_by_s, l_by_s, v_by_s, t_by_s, core14_g_by_s, core14_a_by_s], axis=1)
        .reindex(seasons_idx)
        .fillna(0)
        .astype(int)
        .reset_index()
    )
    # Approximate lineup completeness ratio: expected ~22-36 lineup rows per game
    seasonal["lineups_per_game"] = np.where(
        seasonal["games"] > 0,
        (seasonal["game_lineups"] / seasonal["games"]).round(2),
        0.0,
    )
    seasonal["appearances_per_game"] = np.where(
        seasonal["games"] > 0,
        (seasonal["appearances"] / seasonal["games"]).round(2),
        0.0,
    )
    seasonal["core14_appearances_per_game"] = np.where(
        seasonal["core14_games"] > 0,
        (seasonal["core14_appearances"] / seasonal["core14_games"]).round(2),
        0.0,
    )

    comp_df = comps[
        [
            "competition_id",
            "competition_code",
            "name",
            "type",
            "sub_type",
            "country_name",
            "confederation",
        ]
    ].copy()
    comp_df["is_big5"] = comp_df["competition_id"].isin(BIG5_COMPETITION_IDS)
    comp_df["is_core14"] = comp_df["competition_id"].isin(CORE_14_LEAGUE_IDS)
    comp_games = games["competition_id"].value_counts().rename("total_games")
    comp_apps = apps["competition_id"].value_counts().rename("total_appearances")
    comp_vals = vals["player_club_domestic_competition_id"].value_counts().rename("valuation_rows")
    comp_summary = (
        comp_df.merge(comp_games, on="competition_id", how="left")
        .merge(comp_apps, on="competition_id", how="left")
        .merge(
            comp_vals,
            left_on="competition_id",
            right_index=True,
            how="left",
        )
        .fillna({"total_games": 0, "total_appearances": 0, "valuation_rows": 0})
    )
    for col in ("total_games", "total_appearances", "valuation_rows"):
        comp_summary[col] = comp_summary[col].astype(int)
    comp_summary = comp_summary.sort_values(
        ["type", "total_appearances", "valuation_rows"], ascending=[True, False, False]
    )

    domestic_leagues = comp_summary[comp_summary["type"] == "domestic_league"]
    covered_domestic = domestic_leagues[domestic_leagues["total_appearances"] > 0]
    zero_app_domestic = domestic_leagues[domestic_leagues["total_appearances"] == 0]
    zero_app_all_comps = comp_summary[
        (comp_summary["total_games"] > 0) & (comp_summary["total_appearances"] == 0)
    ]
    coverage_meta = {
        "games_season_vs_july_june_rule_agreement_pct": round(season_match_pct, 2),
        "total_competitions": int(len(comp_summary)),
        "all_domestic_league_rows": int(len(domestic_leagues)),
        "covered_domestic_first_tier_leagues_with_appearances": int(len(covered_domestic)),
        "covered_domestic_league_ids": covered_domestic["competition_id"].tolist(),
        "covered_domestic_league_countries": covered_domestic["country_name"].tolist(),
        "zero_appearance_domestic_leagues_count": int(len(zero_app_domestic)),
        "zero_appearance_domestic_league_ids": zero_app_domestic["competition_id"].tolist(),
        "zero_appearance_all_competition_ids": zero_app_all_comps["competition_id"].tolist(),
        "first_season_with_full_lineups_ge_25_per_game": int(
            seasonal.loc[seasonal["lineups_per_game"] >= 25.0, "season"].min()
        ),
    }
    return seasonal, comp_summary, coverage_meta


def _prepare_valuations(
    vals_raw: pd.DataFrame,
    players_raw: pd.DataFrame,
    comps_raw: pd.DataFrame,
    window_index: TrailingWindowIndex,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    vals = vals_raw.copy()
    vals["pid"] = _to_numeric(vals["player_id"])
    vals["val_date"], vals["day"] = _to_days(vals["date"])
    vals["mv_eur"] = _to_numeric(vals["market_value_in_eur"])

    players = players_raw[
        [
            "player_id",
            "name",
            "date_of_birth",
            "position",
            "sub_position",
            "foot",
            "height_in_cm",
            "country_of_citizenship",
            "current_club_id",
            "contract_expiration_date",
            "international_caps",
            "highest_market_value_in_eur",
            "market_value_in_eur",
        ]
    ].copy()
    players = players.rename(
        columns={
            "current_club_id": "static_2026_club_id",
            "market_value_in_eur": "static_2026_mv_eur",
        }
    )
    players["pid"] = _to_numeric(players["player_id"])
    players["dob"], players["dob_day"] = _to_days(players["date_of_birth"])
    players["height_num"] = _to_numeric(players["height_in_cm"])
    players["highest_mv_num"] = _to_numeric(players["highest_market_value_in_eur"])
    players["contract_dt"], _ = _to_days(players["contract_expiration_date"])

    all_domestic_31_ids = set(
        comps_raw.loc[comps_raw["type"] == "domestic_league", "competition_id"]
    )

    merged = vals.merge(players.drop(columns=["player_id"]), on="pid", how="left")
    merged = merged.dropna(subset=["pid", "day"]).copy()
    merged["pid"] = merged["pid"].astype(np.int64)
    merged["day"] = merged["day"].astype(np.int64)
    merged["season"] = _season_from_dates(merged["val_date"]).astype(np.int64)
    merged["age"] = (merged["day"] - merged["dob_day"]) / 365.25
    merged["in_all_domestic_31"] = merged["player_club_domestic_competition_id"].isin(
        all_domestic_31_ids
    )
    merged["in_domestic_14"] = merged["player_club_domestic_competition_id"].isin(
        CORE_14_LEAGUE_IDS
    )
    merged["is_big5"] = merged["player_club_domestic_competition_id"].isin(BIG5_COMPETITION_IDS)

    win = window_index.query(
        merged["pid"].to_numpy(),
        merged["day"].to_numpy(),
        strict_before=False,
    )
    for k, v in win.items():
        merged[f"w365_{k}"] = v

    # Temporal leakage quantification on historical rows (seasons 2017-2023)
    hist = merged[(merged["season"] >= 2017) & (merged["season"] <= 2023) & (merged["mv_eur"] > 0)]
    club_mismatch_pct = float(
        100.0 * (hist["current_club_id"] != hist["static_2026_club_id"]).mean()
    )
    future_peak_leak_pct = float(100.0 * (hist["highest_mv_num"] > hist["mv_eur"]).mean())
    contract_non_null = hist["contract_dt"].dropna()
    contract_2025_or_later_pct = float(
        100.0 * (contract_non_null.dt.year >= 2025).mean() if not contract_non_null.empty else 0.0
    )

    leakage_stats = {
        "historical_rows_2017_2023_checked": int(len(hist)),
        "static_club_id_mismatch_pct": round(club_mismatch_pct, 2),
        "static_highest_mv_exceeds_point_in_time_mv_pct": round(future_peak_leak_pct, 2),
        "non_null_contract_expiration_in_2025_or_later_pct": round(contract_2025_or_later_pct, 2),
    }
    return merged, leakage_stats


def _audit_target_and_funnel(
    merged: pd.DataFrame,
    players_raw: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    valid_mv = merged[merged["mv_eur"] > 0].copy()
    valid_mv["log10_mv"] = np.log10(valid_mv["mv_eur"])
    valid_mv["ln_mv"] = np.log(valid_mv["mv_eur"])

    season_stats = (
        valid_mv[valid_mv["season"].between(2010, 2025)]
        .groupby("season")
        .agg(
            valuation_rows=("mv_eur", "count"),
            distinct_players=("pid", "nunique"),
            median_mv_eur=("mv_eur", "median"),
            mean_mv_eur=("mv_eur", "mean"),
            p75_mv_eur=("mv_eur", lambda s: float(np.percentile(s, 75))),
            p90_mv_eur=("mv_eur", lambda s: float(np.percentile(s, 90))),
            raw_skew=("mv_eur", lambda s: float(stats.skew(s))),
            log10_skew=("log10_mv", lambda s: float(stats.skew(s))),
        )
        .reset_index()
    )

    # Funnel steps from all player_valuations -> Option A candidate population
    s0 = merged
    s1 = s0[s0["mv_eur"].notna() & (s0["mv_eur"] > 0)]
    s2 = s1[s1["position"].notna() & (s1["position"] != "Missing") & (s1["position"] != "")]
    s2_gk = s2[s2["position"] == "Goalkeeper"]
    s3_outfield = s2[s2["position"] != "Goalkeeper"]
    s4_all31 = s3_outfield[s3_outfield["in_all_domestic_31"]]
    s4_14leagues = s3_outfield[s3_outfield["in_domestic_14"]]
    s5_2017 = s4_14leagues[s4_14leagues["season"].between(2017, 2025)]

    # Measure Option B valuation-update skew within s5_2017 before deduplication
    updates_per_ps = s5_2017.groupby(["pid", "season"]).size()
    # Option A: latest valuation date per (pid, season)
    s6_opt_a = (
        s5_2017.sort_values(["pid", "season", "day"])
        .drop_duplicates(subset=["pid", "season"], keep="last")
        .copy()
    )

    # Also compare all clubs (not restricting player_club_domestic_competition_id to 14 leagues)
    s5_all_comps_2017 = (
        s3_outfield[s3_outfield["season"].between(2017, 2025)]
        .sort_values(["pid", "season", "day"])
        .drop_duplicates(subset=["pid", "season"], keep="last")
    )

    funnel_steps = [
        ("0_raw_player_valuations", s0),
        ("1_positive_market_value", s1),
        ("2_known_player_position", s2),
        ("2b_goalkeepers_excluded_branch", s2_gk),
        ("3_outfield_players_only", s3_outfield),
        ("4a_in_all_31_domestic_leagues_incl_zero_app", s4_all31),
        ("4_in_14_covered_european_domestic_leagues", s4_14leagues),
        ("5_seasons_2017_2025_all_updates_option_b", s5_2017),
        ("6_option_a_player_season_snapshot_all_comps", s5_all_comps_2017),
        ("6_option_a_player_season_snapshot_14_leagues", s6_opt_a),
    ]
    for floor in (90, 180, 270, 450, 630, 900):
        sub = s6_opt_a[s6_opt_a["w365_minutes_played"] >= floor]
        funnel_steps.append((f"7_option_a_14_leagues_min_{floor}m", sub))

    funnel_rows = [
        {
            "step": label,
            "rows": int(len(df_step)),
            "distinct_players": int(df_step["pid"].nunique()),
            "median_mv_eur": float(df_step["mv_eur"].median()) if len(df_step) else 0.0,
        }
        for label, df_step in funnel_steps
    ]

    pos_counts_players = players_raw["position"].fillna("NULL").value_counts().to_dict()
    gk_active = s2_gk[s2_gk["w365_minutes_played"] >= 450]
    target_meta = {
        "players_table_position_counts": {k: int(v) for k, v in pos_counts_players.items()},
        "gk_mean_goals_per90": round(
            float((gk_active["w365_goals"] / (gk_active["w365_minutes_played"] / 90.0)).mean()),
            5,
        ),
        "gk_mean_assists_per90": round(
            float((gk_active["w365_assists"] / (gk_active["w365_minutes_played"] / 90.0)).mean()),
            5,
        ),
        "raw_mv_skewness_2017_2025": round(float(stats.skew(s6_opt_a["mv_eur"])), 3),
        "log10_mv_skewness_2017_2025": round(float(stats.skew(np.log10(s6_opt_a["mv_eur"]))), 3),
        "raw_mv_kurtosis_2017_2025": round(float(stats.kurtosis(s6_opt_a["mv_eur"])), 3),
        "log10_mv_kurtosis_2017_2025": round(
            float(stats.kurtosis(np.log10(s6_opt_a["mv_eur"]))), 3
        ),
        "option_b_updates_per_player_season_p50": float(updates_per_ps.median()),
        "option_b_updates_per_player_season_p90": float(np.percentile(updates_per_ps, 90)),
        "option_b_updates_per_player_season_max": int(updates_per_ps.max()),
        "option_b_share_with_3plus_updates_pct": round(
            float(100.0 * (updates_per_ps >= 3).mean()), 2
        ),
    }
    return season_stats, pd.DataFrame(funnel_rows), target_meta


def _audit_minute_smoothing(opt_a: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Evaluate Empirical Bayes / pad-90s smoothing across m values and year-to-year stability."""
    active = opt_a[opt_a["w365_minutes_played"] >= 90].copy()
    active["n90"] = active["w365_minutes_played"] / 90.0
    active["raw_g90"] = active["w365_goals"] / active["n90"]
    active["raw_a90"] = active["w365_assists"] / active["n90"]
    active["ga_count"] = active["w365_goals"] + active["w365_assists"]
    active["raw_ga90"] = active["ga_count"] / active["n90"]

    # Fit positional priors strictly on seasons 2017-2023 (no 2024-2025 leakage)
    train_slice = active[active["season"] <= 2023]
    priors_ga: dict[str, float] = {}
    priors_g: dict[str, float] = {}
    eb_m_by_pos: dict[str, float] = {}

    for pos, grp in train_slice.groupby("position"):
        mu_ga = float(grp["ga_count"].sum() / grp["n90"].sum())
        mu_g = float(grp["w365_goals"].sum() / grp["n90"].sum())
        priors_ga[str(pos)] = mu_ga
        priors_g[str(pos)] = mu_g

        # Poisson-Gamma method-of-moments: Var(y/n) approx sigma^2_lambda + mu * E[1/n]
        reg = grp[grp["n90"] >= 3.0]
        obs_var = float(np.var(reg["raw_ga90"], ddof=1))
        poisson_noise = float(mu_ga * np.mean(1.0 / reg["n90"]))
        signal_var = max(obs_var - poisson_noise, 1e-4)
        eb_m_by_pos[str(pos)] = round(mu_ga / signal_var, 2)

    active["prior_ga90"] = active["position"].map(priors_ga)
    active["prior_g90"] = active["position"].map(priors_g)

    # Next-season ground truth pairs: low-minute in season t (90..630m) -> regular in t+1 (>=900m)
    nxt = active[active["w365_minutes_played"] >= 900][
        ["pid", "season", "raw_ga90", "raw_g90"]
    ].copy()
    nxt["season"] = nxt["season"] - 1
    nxt = nxt.rename(columns={"raw_ga90": "next_ga90", "raw_g90": "next_g90"})

    low_min = active[active["w365_minutes_played"] < 450]
    low_pairs = active[active["w365_minutes_played"].between(90, 630)].merge(
        nxt, on=["pid", "season"], how="inner"
    )

    rows: list[dict[str, Any]] = []
    for m in (0.0, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0):
        sm_ga = (active["ga_count"] + m * active["prior_ga90"]) / (active["n90"] + m)
        sm_low = (low_min["ga_count"] + m * low_min["prior_ga90"]) / (low_min["n90"] + m)
        pair_pred_ga = (low_pairs["ga_count"] + m * low_pairs["prior_ga90"]) / (
            low_pairs["n90"] + m
        )
        rmse_next = float(np.sqrt(np.mean((pair_pred_ga - low_pairs["next_ga90"]) ** 2)))
        corr_next = float(np.corrcoef(pair_pred_ga, low_pairs["next_ga90"])[0, 1])

        rows.append(
            {
                "pad_90s_m": m,
                "all_ge90m_ga90_p99": round(float(np.percentile(sm_ga, 99)), 4),
                "low_90_450m_ga90_p99": round(float(np.percentile(sm_low, 99)), 4),
                "low_90_450m_ga90_max": round(float(sm_low.max()), 4),
                "low_90_450m_ga90_std": round(float(sm_low.std()), 4),
                "low_to_regular_next_season_pairs": int(len(low_pairs)),
                "next_season_ga90_rmse": round(rmse_next, 4),
                "next_season_ga90_pearson_r": round(corr_next, 4),
            }
        )

    meta = {
        "positional_priors_ga90_2017_2023": {k: round(v, 4) for k, v in priors_ga.items()},
        "positional_priors_g90_2017_2023": {k: round(v, 4) for k, v in priors_g.items()},
        "empirical_bayes_mom_m_by_position": eb_m_by_pos,
        "low_to_regular_transition_pairs_n": int(len(low_pairs)),
    }
    return pd.DataFrame(rows), meta


def _audit_features_and_events(
    opt_a: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    sample = opt_a[
        (opt_a["w365_minutes_played"] >= 180)
        & opt_a["age"].between(15.0, 43.0)
        & (opt_a["mv_eur"] > 0)
    ].copy()
    sample["log10_mv"] = np.log10(sample["mv_eur"])
    sample["n90"] = sample["w365_minutes_played"] / 90.0
    sample["starter_ratio"] = np.where(
        sample["w365_squad_inclusions"] > 0,
        sample["w365_starts"] / sample["w365_squad_inclusions"],
        0.0,
    )
    sample["clean_sheet_rate"] = np.where(
        sample["w365_apps_count"] > 0,
        sample["w365_clean_sheet_flag"] / sample["w365_apps_count"],
        0.0,
    )
    sample["win_rate"] = np.where(
        sample["w365_apps_count"] > 0,
        sample["w365_win_flag"] / sample["w365_apps_count"],
        0.0,
    )

    # Compare univariate linear vs quadratic R^2 of age on log10(mv_eur)
    x_age = sample["age"].to_numpy()
    y_log = sample["log10_mv"].to_numpy()
    lin_fit = np.polyval(np.polyfit(x_age, y_log, 1), x_age)
    quad_coefs = np.polyfit(x_age, y_log, 2)
    quad_fit = np.polyval(quad_coefs, x_age)
    ss_tot = float(np.sum((y_log - y_log.mean()) ** 2))
    r2_age_linear = 1.0 - float(np.sum((y_log - lin_fit) ** 2)) / ss_tot
    r2_age_quadratic = 1.0 - float(np.sum((y_log - quad_fit) ** 2)) / ss_tot
    peak_age = float(-quad_coefs[1] / (2.0 * quad_coefs[0]))

    pos_profiles = (
        sample.groupby("position")
        .agg(
            player_seasons=("pid", "count"),
            median_mv_eur=("mv_eur", "median"),
            mean_minutes=("w365_minutes_played", "mean"),
            mean_starter_ratio=("starter_ratio", "mean"),
            mean_goals_per90=(
                "w365_goals",
                lambda s: float((s / sample.loc[s.index, "n90"]).mean()),
            ),
            mean_assists_per90=(
                "w365_assists",
                lambda s: float((s / sample.loc[s.index, "n90"]).mean()),
            ),
            mean_clean_sheet_rate=("clean_sheet_rate", "mean"),
            mean_win_rate=("win_rate", "mean"),
        )
        .reset_index()
    )

    # Tactical versatility in game_lineups: distinct tactical positions played per player
    lu = frames["game_lineups"]
    valid_lu_pos = lu[lu["position"].notna() & (lu["position"] != "")]
    distinct_pos_per_player = valid_lu_pos.groupby("player_id")["position"].nunique()
    pct_multi_role = float(100.0 * (distinct_pos_per_player >= 2).mean())

    # Audit game_events
    ge = frames["game_events"]
    ge_summary = (
        ge.groupby("type", dropna=False)
        .agg(
            rows=("game_event_id", "count"),
            null_description=("description", lambda s: int(s.isna().sum())),
            empty_description=("description", lambda s: int((s == "").sum())),
            non_empty_description=(
                "description",
                lambda s: int((s.notna() & (s != "")).sum()),
            ),
        )
        .reset_index()
    )
    goal_events = ge[ge["type"] == "Goals"]
    desc_lower = goal_events["description"].fillna("").str.lower()
    penalty_goals = int(desc_lower.str.contains("penalty").sum())
    own_goals_ev = int(desc_lower.str.contains("own-goal|own goal").sum())

    feat_meta = {
        "age_linear_r2_on_log10_mv": round(r2_age_linear, 4),
        "age_quadratic_r2_on_log10_mv": round(r2_age_quadratic, 4),
        "quadratic_peak_valuation_age": round(peak_age, 2),
        "players_with_2plus_tactical_positions_in_lineups_pct": round(pct_multi_role, 2),
        "distinct_lineup_positions": int(valid_lu_pos["position"].nunique()),
        "game_events_total_rows": int(len(ge)),
        "game_events_goal_rows": int(len(goal_events)),
        "game_events_penalty_tagged_goals": penalty_goals,
        "game_events_penalty_share_of_goal_events_pct": round(
            100.0 * penalty_goals / max(len(goal_events), 1), 2
        ),
        "game_events_own_goal_tagged": own_goals_ev,
    }
    return pos_profiles, ge_summary, feat_meta


def _audit_transfers(
    frames: dict[str, pd.DataFrame],
    window_index: TrailingWindowIndex,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    tr = frames["transfers"].copy()
    players = frames["players"][["player_id", "position"]].copy()
    clubs = frames["clubs"][["club_id", "domestic_competition_id"]].copy()

    tr["pid"] = _to_numeric(tr["player_id"])
    tr["t_date"], tr["day"] = _to_days(tr["transfer_date"])
    tr["fee_eur"] = _to_numeric(tr["transfer_fee"])
    tr["mv_at_transfer_eur"] = _to_numeric(tr["market_value_in_eur"])
    tr["season"] = _season_from_dates(tr["t_date"])

    tr = tr.merge(players, on="player_id", how="left")
    tr = tr.merge(
        clubs.rename(columns={"club_id": "to_club_id", "domestic_competition_id": "to_comp_id"}),
        on="to_club_id",
        how="left",
    )
    tr = tr.merge(
        clubs.rename(
            columns={"club_id": "from_club_id", "domestic_competition_id": "from_comp_id"}
        ),
        on="from_club_id",
        how="left",
    )

    domestic_14 = set(CORE_14_LEAGUE_IDS)

    valid_key = tr["pid"].notna() & tr["day"].notna()
    tr_valid = tr[valid_key].copy()
    tr_valid["pid_i"] = tr_valid["pid"].astype(np.int64)
    tr_valid["day_i"] = tr_valid["day"].astype(np.int64)

    win = window_index.query(
        tr_valid["pid_i"].to_numpy(),
        tr_valid["day_i"].to_numpy(),
        strict_before=True,
    )
    tr_valid["pre365_minutes"] = win["minutes_played"]

    paid_all = tr_valid[tr_valid["fee_eur"] > 0]
    paid_outfield = paid_all[paid_all["position"].notna() & (paid_all["position"] != "Goalkeeper")]
    paid_2017_2025 = paid_outfield[paid_outfield["season"].between(2017, 2025)]
    paid_14 = paid_2017_2025[
        paid_2017_2025["to_comp_id"].isin(domestic_14)
        | paid_2017_2025["from_comp_id"].isin(domestic_14)
    ]

    # Feeder-to-Big5 transfers: from non-Big5 in the 14 leagues -> into Big 5
    feeder_to_big5 = paid_14[
        paid_14["from_comp_id"].isin(domestic_14 - BIG5_COMPETITION_IDS)
        & paid_14["to_comp_id"].isin(BIG5_COMPETITION_IDS)
    ]

    audit_rows = [
        {"stage": "all_transfers_rows", "rows": int(len(tr))},
        {"stage": "null_transfer_fee", "rows": int(tr["fee_eur"].isna().sum())},
        {"stage": "zero_transfer_fee_free_or_loan", "rows": int((tr["fee_eur"] == 0).sum())},
        {"stage": "paid_transfers_fee_gt_0", "rows": int(len(paid_all))},
        {"stage": "paid_outfield_transfers", "rows": int(len(paid_outfield))},
        {"stage": "paid_outfield_2017_2025", "rows": int(len(paid_2017_2025))},
        {"stage": "paid_outfield_2017_2025_involving_14_leagues", "rows": int(len(paid_14))},
        {
            "stage": "paid_14_leagues_with_mv_and_ge90_pre_minutes",
            "rows": int(
                len(
                    paid_14[(paid_14["mv_at_transfer_eur"] > 0) & (paid_14["pre365_minutes"] >= 90)]
                )
            ),
        },
        {
            "stage": "paid_14_leagues_with_mv_and_ge180_pre_minutes",
            "rows": int(
                len(
                    paid_14[
                        (paid_14["mv_at_transfer_eur"] > 0) & (paid_14["pre365_minutes"] >= 180)
                    ]
                )
            ),
        },
        {
            "stage": "paid_14_leagues_with_mv_and_ge450_pre_minutes",
            "rows": int(
                len(
                    paid_14[
                        (paid_14["mv_at_transfer_eur"] > 0) & (paid_14["pre365_minutes"] >= 450)
                    ]
                )
            ),
        },
        {
            "stage": "paid_non_big5_to_big5_feeder_corridor_2017_2025",
            "rows": int(len(feeder_to_big5)),
        },
    ]

    eval_sample = paid_14[
        (paid_14["mv_at_transfer_eur"] > 0) & (paid_14["pre365_minutes"] >= 180)
    ].copy()
    eval_sample["log10_fee"] = np.log10(eval_sample["fee_eur"])
    eval_sample["log10_mv"] = np.log10(eval_sample["mv_at_transfer_eur"])
    eval_sample["log10_premium"] = eval_sample["log10_fee"] - eval_sample["log10_mv"]
    eval_sample["fee_to_mv_ratio"] = eval_sample["fee_eur"] / eval_sample["mv_at_transfer_eur"]

    wilcoxon_stat, wilcoxon_p = stats.wilcoxon(eval_sample["log10_premium"])
    ttest_stat, ttest_p = stats.ttest_1samp(eval_sample["log10_premium"], popmean=0.0)

    tr_meta = {
        "eval_sample_paid_14_ge180m_n": int(len(eval_sample)),
        "median_fee_to_mv_ratio": round(float(eval_sample["fee_to_mv_ratio"].median()), 4),
        "mean_fee_to_mv_ratio": round(float(eval_sample["fee_to_mv_ratio"].mean()), 4),
        "overpaid_fee_exceeds_mv_pct": round(
            float(100.0 * (eval_sample["fee_eur"] > eval_sample["mv_at_transfer_eur"]).mean()),
            2,
        ),
        "log10_premium_mean": round(float(eval_sample["log10_premium"].mean()), 4),
        "log10_premium_ttest_t": round(float(ttest_stat), 3),
        "log10_premium_ttest_p": float(ttest_p),
        "log10_premium_wilcoxon_p": float(wilcoxon_p),
        "non_big5_to_big5_paid_transfers_2017_2025": int(len(feeder_to_big5)),
    }
    return pd.DataFrame(audit_rows), eval_sample, tr_meta


def _render_figures(
    out_dir: Path,
    seasonal_cov: pd.DataFrame,
    season_mv: pd.DataFrame,
    opt_a: pd.DataFrame,
    funnel_df: pd.DataFrame,
    smooth_df: pd.DataFrame,
    pos_profiles: pd.DataFrame,
    transfer_sample: pd.DataFrame,
) -> list[str]:
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.1)
    palette = ["#1b4965", "#ca6702", "#2a9d8f", "#9b2226", "#5f0f40"]
    saved: list[str] = []

    # Figure 1: Temporal coverage and game_lineups completeness
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    cov_plot = seasonal_cov[seasonal_cov["season"].between(2008, 2025)]
    axes[0].plot(
        cov_plot["season"],
        cov_plot["appearances"] / 1_000.0,
        marker="o",
        color=palette[0],
        label="Appearances (k)",
    )
    axes[0].plot(
        cov_plot["season"],
        cov_plot["game_lineups"] / 1_000.0,
        marker="s",
        color=palette[1],
        label="Game lineups (k)",
    )
    axes[0].plot(
        cov_plot["season"],
        cov_plot["player_valuations"] / 1_000.0,
        marker="^",
        color=palette[2],
        label="Player valuations (k)",
    )
    axes[0].axvline(2017, color="#444444", linestyle="--", linewidth=1.1, label="2017/18 cutoff")
    axes[0].set_title("A. Row volume by season (thousands)")
    axes[0].set_xlabel("Season start year")
    axes[0].set_ylabel("Rows (thousands)")
    axes[0].legend(frameon=True)

    axes[1].plot(
        cov_plot["season"],
        cov_plot["lineups_per_game"],
        marker="s",
        color=palette[1],
        label="Lineup rows per game (all)",
    )
    axes[1].plot(
        cov_plot["season"],
        cov_plot["appearances_per_game"],
        marker="o",
        linestyle=":",
        color=palette[0],
        label="Appearances per game (all 65 comps)",
    )
    axes[1].plot(
        cov_plot["season"],
        cov_plot["core14_appearances_per_game"],
        marker="^",
        color=palette[2],
        label="Appearances per game (core 14 leagues)",
    )
    axes[1].axvline(2017, color="#444444", linestyle="--", linewidth=1.1)
    axes[1].set_title("B. Completeness density per match")
    axes[1].set_xlabel("Season start year")
    axes[1].set_ylabel("Mean rows per game")
    axes[1].legend(frameon=True)

    f1 = out_dir / "fig01_temporal_coverage.png"
    fig.savefig(f1, dpi=240)
    plt.close(fig)
    saved.append(f1.name)

    # Figure 2: Raw vs log10 market value + seasonal market inflation
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.3), constrained_layout=True)
    mv_m = opt_a["mv_eur"] / 1_000_000.0
    axes[0].hist(mv_m.clip(upper=60), bins=45, color=palette[0], edgecolor="white")
    axes[0].set_title("A. Raw market value (clipped at 60M EUR)")
    axes[0].set_xlabel("Market value (million EUR)")
    axes[0].set_ylabel("Player-seasons")

    axes[1].hist(np.log10(opt_a["mv_eur"]), bins=40, color=palette[2], edgecolor="white")
    axes[1].set_title("B. Log10(market value in EUR)")
    axes[1].set_xlabel("log10(EUR)")
    axes[1].set_ylabel("Player-seasons")

    inf = season_mv[season_mv["season"].between(2012, 2025)]
    axes[2].plot(
        inf["season"],
        inf["median_mv_eur"] / 1e6,
        marker="o",
        color=palette[0],
        label="Median",
    )
    axes[2].plot(
        inf["season"],
        inf["p90_mv_eur"] / 1e6,
        marker="s",
        color=palette[3],
        label="P90",
    )
    axes[2].axvline(2017, color="#444444", linestyle="--", linewidth=1.1)
    axes[2].set_title("C. Market value inflation over time")
    axes[2].set_xlabel("Season start year")
    axes[2].set_ylabel("Million EUR")
    axes[2].legend(frameon=True)

    f2 = out_dir / "fig02_market_value_distribution.png"
    fig.savefig(f2, dpi=240)
    plt.close(fig)
    saved.append(f2.name)

    # Figure 3: Minimum minutes retention vs Empirical Bayes smoothing next-season RMSE
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    min_rows = funnel_df[funnel_df["step"].str.startswith("7_option_a_14_leagues_min_")].copy()
    min_rows["floor"] = min_rows["step"].str.extract(r"min_(\d+)m")[0].astype(int)
    axes[0].plot(
        min_rows["floor"],
        min_rows["rows"],
        marker="o",
        color=palette[0],
        linewidth=2,
    )
    axes[0].set_title("A. Player-season retention by minimum-minutes floor")
    axes[0].set_xlabel("Trailing 365-day minimum minutes")
    axes[0].set_ylabel("Retained player-seasons (2017-2025)")

    ax_r = axes[1]
    ax_r.plot(
        smooth_df["pad_90s_m"],
        smooth_df["next_season_ga90_rmse"],
        marker="o",
        color=palette[3],
        linewidth=2,
        label="Next-season G+A/90 RMSE",
    )
    ax_r.set_title("B. Empirical Bayes pad-90s smoothing on low-minute players")
    ax_r.set_xlabel("Prior strength m (90-minute equivalents)")
    ax_r.set_ylabel("Out-of-sample next-season G+A/90 RMSE")
    ax_r.legend(loc="upper right", frameon=True)

    f3 = out_dir / "fig03_population_and_smoothing.png"
    fig.savefig(f3, dpi=240)
    plt.close(fig)
    saved.append(f3.name)

    # Figure 4: Age vs log10(market_value) non-linearity by position
    fig, ax = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    age_df = opt_a[(opt_a["w365_minutes_played"] >= 180) & opt_a["age"].between(17, 38)].copy()
    age_df["age_int"] = age_df["age"].round().astype(int)
    age_df["log10_mv"] = np.log10(age_df["mv_eur"])
    curve = age_df.groupby(["position", "age_int"])["log10_mv"].agg(["mean", "count"]).reset_index()
    curve = curve[curve["count"] >= 25]
    for idx, (pos, grp) in enumerate(curve.groupby("position")):
        ax.plot(
            grp["age_int"],
            grp["mean"],
            marker="o",
            color=palette[idx % len(palette)],
            linewidth=2,
            label=str(pos),
        )
    ax.set_title("Non-linear age-valuation trajectory by outfield line (2017-2025)")
    ax.set_xlabel("Age at valuation (years)")
    ax.set_ylabel("Mean log10(market value in EUR)")
    ax.legend(frameon=True)

    f4 = out_dir / "fig04_age_valuation_nonlinearity.png"
    fig.savefig(f4, dpi=240)
    plt.close(fig)
    saved.append(f4.name)

    # Figure 5: Position profiles (starter ratio, G+A/90, clean-sheet rate)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), constrained_layout=True)
    p_ord = pos_profiles.set_index("position").reindex(["Defender", "Midfield", "Attack"]).dropna()
    axes[0].bar(
        p_ord.index,
        p_ord["mean_goals_per90"] + p_ord["mean_assists_per90"],
        color=palette[1],
    )
    axes[0].set_title("A. Mean G+A per 90")
    axes[0].set_ylabel("Count per 90 min")

    axes[1].bar(p_ord.index, p_ord["mean_clean_sheet_rate"], color=palette[2])
    axes[1].set_title("B. Mean clean-sheet rate (club_games)")
    axes[1].set_ylabel("Share of appearances")

    axes[2].bar(p_ord.index, p_ord["mean_starter_ratio"], color=palette[0])
    axes[2].set_title("C. Mean starter ratio (game_lineups)")
    axes[2].set_ylabel("Starts / squad inclusions")

    f5 = out_dir / "fig05_tactical_and_lineup_profiles.png"
    fig.savefig(f5, dpi=240)
    plt.close(fig)
    saved.append(f5.name)

    # Figure 6: Paid transfer fee vs pre-transfer market valuation
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), constrained_layout=True)
    axes[0].scatter(
        transfer_sample["log10_mv"],
        transfer_sample["log10_fee"],
        alpha=0.22,
        s=12,
        color=palette[0],
    )
    lims = [4.5, 8.5]
    axes[0].plot(lims, lims, color=palette[3], linestyle="--", linewidth=1.4, label="Fee = MV")
    axes[0].set_xlim(lims)
    axes[0].set_ylim(lims)
    axes[0].set_title("A. Paid transfer fee vs Transfermarkt value (log10 EUR)")
    axes[0].set_xlabel("log10(Market value at transfer)")
    axes[0].set_ylabel("log10(Paid transfer fee)")
    axes[0].legend(frameon=True)

    axes[1].hist(
        transfer_sample["log10_premium"].clip(-1.5, 1.5),
        bins=45,
        color=palette[1],
        edgecolor="white",
    )
    axes[1].axvline(0.0, color=palette[3], linestyle="--", linewidth=1.4)
    axes[1].set_title("B. Transfer premium: log10(Fee) - log10(Market value)")
    axes[1].set_xlabel("Log10 residual")
    axes[1].set_ylabel("Paid outfield transfers")

    f6 = out_dir / "fig06_transfer_fee_vs_valuation.png"
    fig.savefig(f6, dpi=240)
    plt.close(fig)
    saved.append(f6.name)

    return saved


def run_eda() -> dict[str, Any]:
    """Execute the full exploratory analysis and write CSVs, JSON summary, and PNG figures."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        _fail(str(exc))

    project_root = find_project_root()
    repo_root = project_root.parent if project_root is not None else Path.cwd()
    ingest_dir = settings.data_dir / "ingest"
    out_dir = repo_root / "analysis" / "output" / "eda"
    out_dir.mkdir(parents=True, exist_ok=True)

    snapshot, frames = _load_tables(ingest_dir)

    inv_df, miss_df = _audit_tables_and_missingness(frames)
    inv_df.to_csv(out_dir / "01_table_inventory.csv", index=False)
    miss_df.to_csv(out_dir / "02_missingness_and_sentinels.csv", index=False)

    seasonal_cov, comp_summary, cov_meta = _audit_coverage(frames)
    seasonal_cov.to_csv(out_dir / "03a_coverage_by_season.csv", index=False)
    comp_summary.to_csv(out_dir / "03b_competitions_summary.csv", index=False)

    win_idx = TrailingWindowIndex(
        frames["appearances"],
        frames["club_games"],
        frames["game_lineups"],
        frames["competitions"],
    )
    merged_vals, leakage_meta = _prepare_valuations(
        frames["player_valuations"],
        frames["players"],
        frames["competitions"],
        win_idx,
    )

    season_mv, funnel_df, target_meta = _audit_target_and_funnel(merged_vals, frames["players"])
    season_mv.to_csv(out_dir / "04_target_distribution_by_season.csv", index=False)
    funnel_df.to_csv(out_dir / "05_population_funnel.csv", index=False)

    opt_a = (
        merged_vals[
            (merged_vals["mv_eur"] > 0)
            & merged_vals["position"].notna()
            & ~merged_vals["position"].isin(["Goalkeeper", "Missing", ""])
            & merged_vals["in_domestic_14"]
            & merged_vals["season"].between(2017, 2025)
        ]
        .sort_values(["pid", "season", "day"])
        .drop_duplicates(subset=["pid", "season"], keep="last")
        .copy()
    )

    smooth_df, smooth_meta = _audit_minute_smoothing(opt_a)
    smooth_df.to_csv(out_dir / "06_minute_smoothing_sensitivity.csv", index=False)

    pos_profiles, ge_summary, feat_meta = _audit_features_and_events(opt_a, frames)
    pos_profiles.to_csv(out_dir / "07a_position_profiles.csv", index=False)
    ge_summary.to_csv(out_dir / "07b_game_events_breakdown.csv", index=False)

    tr_audit_df, tr_sample, tr_meta = _audit_transfers(frames, win_idx)
    tr_audit_df.to_csv(out_dir / "08_transfers_join_audit.csv", index=False)

    figures = _render_figures(
        out_dir,
        seasonal_cov,
        season_mv,
        opt_a,
        funnel_df,
        smooth_df,
        pos_profiles,
        tr_sample,
    )

    # Extra data-hygiene anomaly counts for §3.5
    apps = frames["appearances"]
    mins = _to_numeric(apps["minutes_played"])
    players = frames["players"]
    heights = _to_numeric(players["height_in_cm"])
    anomalies = {
        "appearances_minutes_le_0": int((mins <= 0).sum()),
        "appearances_minutes_gt_120": int((mins > 120).sum()),
        "players_height_null": int(players["height_in_cm"].isna().sum()),
        "players_height_zero_or_lt_140": int(
            (((heights > 0) & (heights < 140)) | (heights == 0)).sum()
        ),
        "players_dob_null": int(players["date_of_birth"].isna().sum()),
        "players_foot_null_or_empty": int(
            (players["foot"].isna() | (players["foot"] == "") | (players["foot"] == "N/A")).sum()
        ),
        "player_valuations_zero_or_neg_mv": int(
            (_to_numeric(frames["player_valuations"]["market_value_in_eur"]) <= 0).sum()
        ),
    }

    summary = {
        "dataset": snapshot.get("dataset"),
        "version": snapshot.get("version"),
        "snapshot_sha256": snapshot.get("snapshot_sha256"),
        "output_dir": str(out_dir),
        "figures": figures,
        "coverage": cov_meta,
        "target_and_funnel": target_meta,
        "funnel_table": funnel_df.to_dict(orient="records"),
        "minute_smoothing": smooth_meta,
        "minute_smoothing_table": smooth_df.to_dict(orient="records"),
        "temporal_leakage_audit": leakage_meta,
        "features_and_events": feat_meta,
        "transfers_feasibility": tr_meta,
        "cleaning_anomalies": anomalies,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    summary = run_eda()
    print(
        f"EDA completed over {summary['dataset']} v{summary['version']} -> {summary['output_dir']}"
    )


if __name__ == "__main__":
    main()
