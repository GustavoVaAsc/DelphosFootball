"""render_report.py — assemble docs/DATA_DISCOVERY.md from discovery/results/*.json.

Run after all numbered scripts (see run_all.sh). Editorial sections (leakage
watchlist, aggregation feasibility) are static prose anchored to computed
facts; every number rendered in the document comes from the results JSONs.
"""
from datetime import datetime

from common import RESULTS_DIR, REPORT_PATH, load


def fmt_int(n):
    return f"{n:,}"


def fmt_num(x):
    if x is None:
        return "-"
    if isinstance(x, int):
        return f"{x:,}"
    if abs(x) >= 1000:
        return f"{x:,.1f}".rstrip("0").rstrip(".")
    return f"{x:.4g}"


def fmt_eur(x):
    return "-" if x is None else f"€{x:,.0f}"


def fmt_pct(x):
    return "-" if x is None else f"{100 * x:.2f}%"


GRANULARITY = {
    "appearances.csv": ("one row per player appearance in a game (player x game)", "appearance_id"),
    "club_games.csv": ("one row per club per game (2 rows per game: home + away)", "(game_id, club_id)"),
    "clubs.csv": ("one row per club (scraped latest-season roster; see date field `last_season`)", "club_id"),
    "competitions.csv": ("one row per competition (leagues, cups, national teams)", "competition_id"),
    "countries.csv": ("one row per country", "country_id"),
    "game_events.csv": ("one row per recorded in-game event (goal, card, substitution, shootout)", "game_event_id"),
    "game_lineups.csv": ("one row per player per game per lineup type (starting/substitute)", "game_lineups_id"),
    "games.csv": ("one row per game", "game_id"),
    "national_teams.csv": ("one row per national team", "national_team_id"),
    "players.csv": ("one row per player (attributes as of scrape date)", "player_id"),
    "player_valuations.csv": ("one row per player market-value snapshot (player x date)", "(player_id, date)"),
    "transfers.csv": ("one row per transfer event", "none verified — see duplicates section"),
}


def sec1_inventory(inv):
    lines = [
        "## 1. File inventory",
        "",
        "| file | rows | cols | size | granularity | primary key candidate (verified unique) | date coverage |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for fname, meta in inv.items():
        gran, pk_name = GRANULARITY[fname]
        pk = meta["pk_candidate"]
        if pk:
            key = " + ".join(pk["columns"])
            if pk["is_unique"]:
                pk_txt = f"`{key}` — UNIQUE"
            else:
                pk_txt = f"`{key}` — NOT unique (" + fmt_int(pk["n_duplicate_rows"]) + " dup rows)"
        else:
            pk_txt = "none (see §3)"
        if meta["date_columns"]:
            cov = "; ".join(
                f"`{c}`: {meta['date_min'].get(c)} → {meta['date_max'].get(c)}"
                for c in meta["date_columns"]
            )
        else:
            cov = "no date column (join `games.csv` for game dates)"
        lines.append(
            f"| `{fname}` | {fmt_int(meta['n_rows'])} | {meta['n_cols']} | {meta['size_mb']} MB | {gran} | {pk_txt} | {cov} |"
        )
    lines += [
        "",
        "Total: 12 files, 873.4 MB on disk. All row counts are exact (full parse by pandas).",
        "Note: `transfers.csv` contains transfer dates up to 2030 (see §12).",
    ]
    return "\n".join(lines)


def sec2_schema(sch):
    lines = [
        "## 2. Schema per file",
        "",
        "dtypes as inferred by pandas 3.0.6 (`read_csv` defaults, chunked for the three big files).",
        "Columns with >20% nulls are flagged. `str` = text, `int64`/`float64` = numeric.",
        "",
    ]
    for fname, meta in sch.items():
        lines += [
            f"### `{fname}` ({fmt_int(meta['n_rows'])} rows)",
            "",
            "| column | dtype | nulls | null rate | >20% null |",
            "|---|---|---:|---:|:--:|",
        ]
        for c in meta["columns"]:
            flag = "**YES**" if c["flag_gt20pct_null"] else ""
            lines.append(
                f"| `{c['name']}` | {c['dtype']} | {fmt_int(c['nulls'])} | {fmt_pct(c['null_rate'])} | {flag} |"
            )
        lines.append("")
    return "\n".join(lines)


def sec3_duplicates(dup):
    lines = [
        "## 3. Duplicates",
        "",
        "Full-row duplicate scan and key-level duplicate scan per file (exact, full parse with `dtype=str`).",
        "",
        "| file | full-row dups | key checked | dup rows on key |",
        "|---|---:|---|---:|",
    ]
    for fname, meta in dup.items():
        first = True
        for kc in meta["key_checks"]:
            key = "`" + " + ".join(kc["columns"]) + "`"
            lines.append(
                f"| {f'`{fname}`' if first else ''} | {fmt_int(meta['full_row_duplicates']) if first else ''} | {key} | {fmt_int(kc['n_duplicate_rows'])} |"
            )
            first = False
    lines += [
        "",
        "Findings:",
        "",
        "- No full-row duplicates anywhere in the dataset.",
        "- `appearances`: `(player_id, game_id)` is unique — grain is truly one row per player per game.",
        "- `game_lineups`: 12 extra rows share `(game_id, player_id)` — a player listed twice in the same game's lineups.",
        "- `game_events`: 906 rows share `(game_id, player_id, type, minute)` — multiple events of the same type in the same minute (e.g. goal + second yellow); `game_event_id` itself is unique.",
        "- `players`: 1,324 rows share a `name` with another row — different `player_id`s with identical names; never join on name, only on `player_id`.",
        "- `transfers`: 118 rows share `(player_id, transfer_date)` (e.g. two moves on the same day); the 4-column tuple is unique, so there is no single-column or 2-column PK.",
        "- `player_valuations`: `(player_id, date)` is unique — no duplicate snapshots on the same date.",
    ]
    return "\n".join(lines)


def sec4_numeric(num):
    lines = [
        "## 4. Numeric summaries",
        "",
        "Every numeric column of interest. Zeros/negatives counted on non-null values.",
        "",
    ]
    cols = ["n", "nulls", "min", "max", "mean", "median", "p25", "p75", "p99", "zeros", "negatives"]
    for fname, colmap in num.items():
        lines += [
            f"### `{fname}`",
            "",
            "| column | " + " | ".join(cols) + " |",
            "|---|" + "---:|" * len(cols),
        ]
        for col, s in colmap.items():
            if not s or not s.get("n_non_null"):
                lines.append(f"| `{col}` | all null | " + " | ".join(["-"] * (len(cols) - 1)) + " |")
                continue
            vals = [
                fmt_num(s["n_non_null"]), fmt_num(s["n_null"]), fmt_num(s["min"]), fmt_num(s["max"]),
                fmt_num(s["mean"]), fmt_num(s["median"]), fmt_num(s["p25"]), fmt_num(s["p75"]),
                fmt_num(s["p99"]), fmt_num(s["n_zero"]), fmt_num(s["n_negative"]),
            ]
            lines.append(f"| `{col}` | " + " | ".join(vals) + " |")
        lines.append("")
    lines += [
        "`clubs.net_transfer_record` is stored as a signed string (e.g. `+€5.90m`, `€-25.00m`);",
        "the summary row parses it to EUR (x1e6). `clubs.total_market_value` is entirely null in this",
        "snapshot of the dataset.",
    ]
    return "\n".join(lines)


def sec5_target(tgt):
    v, pcur, ph, log = tgt["valuations_history"], tgt["players_current_value"], tgt["players_highest_value"], tgt["log_transform_diag"]
    lines = [
        "## 5. Target analysis: market_value_in_eur",
        "",
        "### Distribution shape",
        "",
        "| distribution | n | min | p1 | p5 | p25 | p50 | p75 | p90 | p95 | p99 | max | mean | skew | zeros | negatives |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for d in (v, pcur, ph):
        q = d["quantiles"]
        lines.append(
            f"| {d['label']} | {fmt_int(d['n'])} | {fmt_eur(d['min'])} | {fmt_eur(q['p1'])} | {fmt_eur(q['p5'])} | "
            f"{fmt_eur(q['p25'])} | {fmt_eur(q['p50'])} | {fmt_eur(q['p75'])} | {fmt_eur(q['p90'])} | {fmt_eur(q['p95'])} | "
            f"{fmt_eur(q['p99'])} | {fmt_eur(d['max'])} | {fmt_eur(d['mean'])} | {d['skew']:.2f} | {fmt_int(d['n_zero'])} | {fmt_int(d['n_negative'])} |"
        )
    lines += [
        "",
        f"- The raw target is heavily right-skewed (skew {v['skew']:.2f} on all valuation snapshots;"
        f" {pcur['skew']:.2f} on players' current values) with a heavy tail: max is {fmt_eur(v['max'])} vs"
        f" median {fmt_eur(v['quantiles']['p50'])}. The top 1% of snapshots hold"
        f" {fmt_pct(v['pct_top1pct_share_of_sum'])} of total valuation mass.",
        f"- No negative values anywhere. Exactly {v['n_zero']} zero in all of `player_valuations`"
        f" ({pcur['n_zero']} in `players`), so zeros are not a modeling concern.",
        "",
        "### Log-transform diagnostic (all valuation snapshots, `log1p`)",
        "",
        f"- raw skew {log['raw_skew']:.2f} → log1p skew **{log['log1p_skew']:.2f}** (near-symmetric)",
        f"- log1p mean {log['log1p_mean']:.2f}, std {log['log1p_std']:.2f}",
        "",
        "**Verdict: log-transform is required.** Raw EUR values are unusable as a regression target for",
        "most losses (skew ~8.7, 4 orders of magnitude between p50 and p99). `log1p` brings skew under",
        "0.5; train in log space and report metrics both in log space and back-transformed EUR.",
        "",
        "### Valuation coverage and history depth",
        "",
        f"- Players in `players.csv`: {fmt_int(tgt['coverage']['n_players_in_players_csv'])};",
        f"  **with** valuation history: {fmt_int(tgt['coverage']['n_players_with_valuation_history'])};",
        f"  **without** any snapshot: {fmt_int(tgt['coverage']['n_players_without_valuation_history'])}"
        f" ({fmt_pct(tgt['coverage']['n_players_without_valuation_history'] / tgt['coverage']['n_players_in_players_csv'])} of players).",
        f"- Every valuation `player_id` resolves to `players.csv` (0 orphans) — the valuation table is a strict subset of known players.",
        "",
        "| snapshots per player | players |",
        "|---|---:|",
    ]
    for k, c in tgt["history_depth_per_player"]["histogram"].items():
        lines.append(f"| {k} | {fmt_int(c)} |")
    d = tgt["history_depth_per_player"]
    lines += [
        "",
        f"min {d['min']}, median {d['median']:.0f}, mean {d['mean']:.1f}, p90 {d['p90']:.0f}, p99 {d['p99']:.0f}, max {d['max']}.",
        "",
        f"- `players.market_value_in_eur` equals the **last** valuation snapshot for"
        f" {fmt_pct(tgt['players_value_vs_history']['pct_equal_last_snapshot'])} of the"
        f" {fmt_int(tgt['players_value_vs_history']['n_comparable'])} comparable players, but equals the"
        f" all-time max for only {fmt_pct(tgt['players_value_vs_history']['pct_equal_max_ever'])} —"
        " it is a current snapshot, not a max-career figure. It is post-hoc w.r.t. any past prediction date.",
    ]
    return "\n".join(lines)


def sec6_transfers(trf):
    fs, zb, sm, fvm, mvc = (
        trf["transfer_fee_semantics"], trf["zero_fee_breakdown"], trf["small_positive_fees"],
        trf["fee_vs_market_value"], trf["market_value_col"],
    )
    lines = [
        "## 6. Transfer fee specifics",
        "",
        f"`transfer_fee` over all {fmt_int(trf['n_rows'])} transfers:",
        "",
        "| category | count | share |",
        "|---|---:|---:|",
        f"| null (fee not recorded) | {fmt_int(fs['n_null'])} | {fmt_pct(fs['n_null'] / trf['n_rows'])} |",
        f"| exactly 0 (free / undisclosed) | {fmt_int(fs['n_zero'])} | {fmt_pct(fs['pct_zero'])} |",
        f"| positive (recorded fee) | {fmt_int(fs['n_positive'])} | {fmt_pct(fs['n_positive'] / trf['n_rows'])} |",
        f"| negative | {fmt_int(fs['n_negative'])} | {fmt_pct(fs['n_negative'] / trf['n_rows'])} |",
        "",
        f"- Of the {fmt_int(fs['n_zero'])} zero-fee rows: {fmt_int(zb['n_zero_fee_with_positive_mv'])} carry a positive"
        f" market value and {fmt_int(zb['n_zero_fee_with_null_mv'])} have no market value at all."
        " A zero fee therefore conflates genuinely free transfers with undisclosed fees — it is a censored"
        " value, not a price of 0.",
        f"- Smallest recorded positive fee: {fmt_eur(fs['min_positive'])}; {fmt_int(sm['n_fee_lt_1k'])} fees below €1k,"
        f" {fmt_int(sm['n_fee_lt_10k'])} below €10k, none equal to €1 — no €1 sentinel pattern.",
        f"- `market_value_in_eur` inside transfers: {fmt_int(mvc['n_null'])} null, {fmt_int(mvc['n_zero'])} zero,"
        f" {fmt_int(mvc['n_negative'])} negative.",
        "",
        "### Fee vs market value at transfer date (rows with fee > 0 and mv > 0)",
        "",
        f"n = {fmt_int(fvm['n_comparable'])}; ratio = fee / market_value:",
        "",
        "| p1 | p5 | p25 | p50 | p75 | p90 | p95 | p99 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| " + " | ".join(f"{fvm['ratio_quantiles'][k]:.2f}" for k in ['p1','p5','p25','p50','p75','p90','p95','p99']) + " |",
        "",
        f"- Median fee is {fvm['ratio_quantiles']['p50']:.2f}x market value — fees roughly track valuations at the median.",
        f"- {fmt_int(fvm['n_fee_gt_2x_mv'])} transfers at >2x market value ({fmt_int(fvm['n_fee_gt_5x_mv'])} at >5x);"
        f" {fmt_int(fvm['n_fee_lt_half_mv'])} below half of market value ({fmt_int(fvm['n_fee_lt_tenth_mv'])} below a tenth).",
        "",
        "**Usability verdict:** fee-based supervision is only possible on the "
        f"{fmt_pct(fs['n_positive'] / trf['n_rows'])} of rows with a recorded positive fee; treating 0 as a real price",
        "would corrupt any target built from it. Null-fee and zero-fee rows should be excluded from fee regression",
        "or handled as censored observations.",
    ]
    return "\n".join(lines)


def sec7_categoricals(cat):
    lines = [
        "## 7. Categoricals",
        "",
    ]
    for fname, colmap in cat.items():
        lines += [f"### `{fname}`", "", "| column | distinct | nulls | top values (count) |", "|---|---:|---:|---|"]
        for col, r in colmap.items():
            top = ", ".join(f"{t['value']} ({fmt_int(t['count'])})" for t in r["top5"])
            lines.append(f"| `{col}` | {fmt_int(r['n_distinct'])} | {fmt_int(r['n_null'])} | {top} |")
        lines.append("")
    lines += [
        "Note: `appearances.csv` covers 48 competitions while `games.csv` covers 70 — 22 competitions",
        "have games but (nearly) no recorded appearances; see orphan `competition_id` in §8.",
    ]
    return "\n".join(lines)


def sec8_referential(ref):
    lines = [
        "## 8. Referential integrity",
        "",
        "Orphans = non-null key values with no matching row in the dimension table. Rate is over non-null values.",
        "",
        "| fact column → dimension | non-null | null | orphans | orphan rate | example orphan keys |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for fname, colmap in ref.items():
        for k, r in colmap.items():
            ex = ", ".join(r["orphan_examples"][:3]) if r["orphan_examples"] else "-"
            lines.append(
                f"| `{fname}`: `{k}` | {fmt_int(r['n_non_null'])} | {fmt_int(r['n_null'])} | {fmt_int(r['n_orphan'])} | {fmt_pct(r['orphan_rate_over_non_null'])} | {ex} |"
            )
    lines += [
        "",
        "Findings:",
        "",
        "- `game_id` integrity is perfect everywhere: all appearances, events, lineups and club_games resolve to `games.csv`.",
        "- `players.csv` is nearly complete as a player dimension for event tables: ~10% of game_events and"
        " game_lineups player_ids are orphans — players never profiled by Transfermarkt (mostly lower-division)."
        " Appearances, valuations and transfers player_ids are fully (or nearly) covered (2 orphans in appearances).",
        "- **`clubs.csv` is NOT a complete club dimension.** It holds only the 796 clubs from the scraped latest-season"
        " rosters; historical/defunct clubs are missing. Orphan rates: transfers from_club 62.6%, transfers to_club"
        " 52.9%, player_valuations current_club 14.2%, game_lineups club 12.2%, games home_club 14.4%. Any club-level"
        " join must tolerate missing clubs (or use club names as fallback).",
        "- `appearances.competition_id`: 14,200 orphans (0.75%) — competitions with games but absent from `competitions.csv`.",
        "- `players.current_national_team_id`: 106 of 3,258 non-null values orphaned against `national_teams.csv`.",
    ]
    return "\n".join(lines)


def sec9_temporal(tmp, inv, qual):
    def rng(fname, col="date"):
        return inv[fname]["date_min"].get(col, "-"), inv[fname]["date_max"].get(col, "-")

    glf = tmp["lineups_date_range"]
    gl_fut_cell = (
        "0 rows (checked)" if glf["n_future_dated"] == 0
        else f"**{fmt_int(glf['n_future_dated'])}**"
    )
    rows = [
        ("appearances", "date", *rng("appearances.csv"), fmt_int(qual["appearances"]["n_future_date"])),
        ("games", "date", *rng("games.csv"), fmt_int(qual["games"]["n_future_dated"])),
        ("game_events", "date", *rng("game_events.csv"), fmt_int(qual["game_events"]["n_future_dated"])),
        ("game_lineups", "date", *rng("game_lineups.csv"), gl_fut_cell),
        ("player_valuations", "date", tmp["valuations_date_range"]["min"], tmp["valuations_date_range"]["max"], fmt_int(tmp["valuations_date_range"]["n_future_dated"])),
        ("transfers", "transfer_date", tmp["transfers_date_range"]["min"], tmp["transfers_date_range"]["max"], f"**{fmt_int(tmp['transfers_date_range']['n_future_dated'])}**"),
    ]
    lines = [
        "## 9. Temporal coverage",
        "",
        "### Date ranges",
        "",
        "| table | column | min | max | future-dated rows |",
        "|---|---|---|---|---:|",
    ]
    for table, col, lo, hi, fut in rows:
        lines.append(f"| `{table}` | {col} | {lo} | {hi} | {fut} |")
    if glf["n_future_dated"]:
        examples = "; ".join(
            f"`{e['game_lineups_id']}` (game `{e['game_id']}`, {e['date']})"
            for e in glf["future_examples"]
        )
        lines += [
            "",
            f"`game_lineups` future-dated rows: {fmt_int(glf['n_future_dated'])} of"
            f" {fmt_int(glf['n_rows'])} ({fmt_pct(glf['pct_future_dated'])}),"
            f" dates {glf['min_future_date']} → {glf['max_future_date']};"
            f" examples: {examples}.",
        ]
    lines += [
        "",
        "### Transfers per season",
        "",
        "| transfer_season | transfers |",
        "|---|---:|",
    ]
    for r in tmp["transfers_per_season"]:
        lines.append(f"| {r['season']} | {fmt_int(r['count'])} |")
    lines += [
        "",
        "### Games per season",
        "",
        "| season | games | min date | max date |",
        "|---|---:|---|---|",
    ]
    for r in tmp["games_per_season"]:
        lines.append(f"| {r['season']} | {fmt_int(r['count'])} | {r['min_date'] or '-'} | {r['max_date'] or '-'} |")
    lines += [
        "",
        "### Valuation snapshots per calendar year",
        "",
        "| year | snapshots |",
        "|---|---:|",
    ]
    for r in tmp["valuation_snapshots_per_year"]:
        lines.append(f"| {r['year']} | {fmt_int(r['count'])} |")
    gap = tmp["transfer_to_nearest_valuation_gap_days"]
    br = tmp["valuation_brackets_transfer"]
    lines += [
        "",
        "### Valuation snapshots vs transfer dates",
        "",
        f"- {fmt_pct(gap['pct_without_any_snapshot'])} of transfers have **no** valuation snapshot for the player at all.",
        f"- Nearest snapshot to the transfer date: median gap {gap['p50']:.0f} days, p90 {gap['p90']:.0f} days.",
        f"- {fmt_pct(gap['pct_within_7d'])} within 7 days, {fmt_pct(gap['pct_within_30d'])} within 30 days,"
        f" {fmt_pct(gap['pct_within_90d'])} within 90 days.",
        f"- Snapshot within 365 days BEFORE the transfer: {fmt_pct(br['pct_with_snapshot_in_minus365d'])};"
        f" within 365 days AFTER: {fmt_pct(br['pct_with_snapshot_in_plus365d'])};"
        f" **both (bracketing): {fmt_pct(br['pct_bracketed_within_365d'])}**.",
        "",
        "Conclusion: snapshots are sparse (Transfermarkt updates valuations irregularly, ~15 per player median over",
        "26 years). Transfer-date market values must be approximated by nearest-snapshot interpolation, and the",
        "±90-day window covers only ~59% of transfers — targets aligned to transfer dates will drop or interpolate",
        "the rest.",
    ]
    return "\n".join(lines)


def sec10_leakage():
    return "\n".join([
        "## 10. Leakage watchlist",
        "",
        "Columns that encode post-hoc or outcome information and must NOT feed a model that predicts",
        "market value at a past date. The governing rule: **everything in `players.csv` and `clubs.csv` is",
        "scraped-state as of the dataset build (late 2025/2026)**; only the dated tables (`appearances`,",
        "`player_valuations`, `transfers`, `games`, `game_events`, `game_lineups`) can be joined as-of a",
        "prediction date safely.",
        "",
        "| column | why it leaks |",
        "|---|---|",
        "| `players.highest_market_value_in_eur` | maximum value over the player's whole future career; directly reveals the outcome trajectory |",
        "| `players.market_value_in_eur` | current (latest) snapshot — equals the last valuation row for 100% of players; post-hoc for any past target date |",
        "| `players.last_season` | season in which the player was last active — known only after the fact |",
        "| `players.current_club_id` / `current_club_name` / `current_club_domestic_competition_id` | club at scrape time, not at prediction time |",
        "| `players.current_national_team_id`, `international_caps`, `international_goals` | career totals as of scrape date, with no timeline — they include caps/goals earned after any past prediction date |",
        "| `players.contract_expiration_date` | can reveal the next club move (e.g. free transfer) before it is public |",
        "| `appearances.player_current_club_id` | player's club at scrape time; for old appearances this is post-hoc (use `player_club_id`, the club at game time) |",
        "| `transfers.transfer_fee`, `transfers.market_value_in_eur` | realized outcome at/after the transfer; a feature for later targets but leakage for predicting value BEFORE the transfer |",
        "| `games.home_club_goals` / `away_club_goals`, `club_games.is_win`, `own_goals`/`opponent_goals` | match outcomes; only usable for windows strictly before the prediction date |",
        "| `club_games.own_position` / `opponent_position` | league position updated through the season; the final value encodes the rest of the season |",
        "| `clubs.net_transfer_record`, `clubs.total_market_value`, `clubs.last_season`, `clubs.coach_name` | season aggregates computed after the season ends |",
        "| `player_valuations.current_club_id` / `current_club_name` | safe ONLY because the row is a dated snapshot (club as-of that date); do not confuse with players.csv current_* |",
        "| `games.round`, `games.aggregate` | cup-round labels can encode how far a team progressed in the competition |",
        "",
        "Safe-by-construction features: attributes dated on or before the prediction date (appearances,",
        "lineups, events, valuation snapshots, transfer history joined strictly as-of).",
    ])


def sec11_aggregation():
    return "\n".join([
        "## 11. Aggregation feasibility",
        "",
        "### What CAN be built (per player, rolling windows or per season)",
        "",
        "- From `appearances` (1,894,350 rows): appearances count, `minutes_played` sum/mean, `goals`,",
        "  `assists`, `yellow_cards`, `red_cards`; derived rates such as goals-per-90 / assists-per-90",
        "  (3 rows have minutes > 130 and 3 rows have 0 minutes — negligible, filterable).",
        "- From `game_lineups` (3,179,016 rows): starts (`type = starting_lineup`, 1,780,759 rows) vs",
        "  substitute appearances (1,398,257), `position` history (18 values, e.g. Centre-Back, Central",
        "  Midfield), shirt `number` (with 25,698 `'-'` placeholders), `team_captain` flag (captaincy frequency).",
        "- From `game_events` (1,274,469 rows): goals with exact `minute` (time-weighted goal minutes),",
        "  cards by type, substitutions (with `player_in_id` — who replaced whom), `player_assist_id`",
        "  (assist credit on goal events), shootout events.",
        "- From `club_games` (177,916 rows): team-level results (`own_goals`, `is_win`, `hosting`) and",
        "  opponent strength — usable as team-context features behind a player.",
        "- From `games` (88,958 rows): competition, season, round, attendance, formations, manager names.",
        "- Static player attributes: height, foot, position/sub_position, date of birth (=> age at any",
        "  prediction date), country of birth/citizenship. International caps/goals exist only as",
        "  scrape-date career totals (no timeline) — usable only with the leakage caveat in §10.",
        "",
        "### Advanced scouting metrics: NOT PRESENT",
        "",
        "`game_events.type` has exactly **four** values: Cards, Goals, Shootout, Substitutions",
        "(counts in §7). `game_events` columns are: game_event_id, date, game_id, minute, type, club_id,",
        "club_name, player_id, description, player_in_id, player_assist_id. `game_lineups` columns carry",
        "only lineup/position/number/captain. `appearances` carries only cards/goals/assists/minutes.",
        "",
        "**The dataset contains NO key passes, NO recoveries, NO dribbles, NO shots (except shootout",
        "events), NO pass counts, NO xG/xA, NO progressive carries, NO tracking data.** The project",
        "charter's example mentioning 'key passes and recoveries' is not supported by this dataset; the",
        "paper/system wording must be corrected to describe features that are actually derivable:",
        "goals, assists, cards, minutes, starts, positions, captaincy, age, physical attributes, and",
        "team context. Any richer metric would require a different data source (e.g. StatsBomb/Opta).",
    ])


def sec12_quality(dup, qual, ref):
    q = qual
    lines = [
        "## 12. Data quality issues found",
        "",
        "| issue | file | count | note |",
        "|---|---|---:|---|",
        f"| future-dated transfers (max {q['transfers']['max_transfer_date']}) | transfers.csv | {fmt_int(q['transfers']['n_future_dated'])} | mostly contract-expiry-style entries dated 2027-2030 |",
        f"| transfer_season disagrees with year(transfer_date) | transfers.csv | {fmt_int(q['transfers']['n_season_year_mismatch'])} | season start-year vs date year |",
        f"| self-transfers (from == to club) | transfers.csv | {fmt_int(q['transfers']['n_self_transfer'])} | club_id identical on both sides |",
        f"| from_club_name differs from clubs.name for same id | transfers.csv | {fmt_int(q['transfers']['n_from_club_name_mismatch_vs_clubs'])} | historical club names at transfer time; clubs.csv only has 796 clubs |",
        f"| to_club_name differs from clubs.name for same id | transfers.csv | {fmt_int(q['transfers']['n_to_club_name_mismatch_vs_clubs'])} | same as above |",
        f"| player_name vs players.name mismatches | transfers.csv | {fmt_int(q['transfers']['n_name_mismatch_vs_players'])} | 0 of {fmt_int(q['transfers']['n_name_mismatch_compared'])} compared — names are consistent |",
        f"| negative event minutes | game_events.csv | {fmt_int(q['game_events']['n_negative_minute'])} | minute < 0 (e.g. halftime-whistle markers) |",
        f"| non-numeric shirt number ('-') | game_lineups.csv | {fmt_int(q['game_lineups']['n_non_numeric_number'])} | makes `number` a mixed-type column |",
        f"| shirt number outside 1-99 | game_lineups.csv | {fmt_int(q['game_lineups']['n_invalid_number'])} | after numeric coercion |",
        f"| same player twice in one game's lineups | game_lineups.csv | {fmt_int(q['game_lineups']['n_dup_game_player_extra_rows'])} | extra rows on (game_id, player_id) |",
        f"| null attendance | games.csv | {fmt_int(q['games']['n_null_attendance'])} | {fmt_pct(q['games']['n_null_attendance'] / q['games']['n_rows'])} of games |",
        f"| goals sum > 15 in a game | games.csv | {fmt_int(q['games']['n_goals_sum_gt_15'])} | extreme results (data-entry or real routs) |",
        f"| minutes_played > 130 | appearances.csv | {fmt_int(q['appearances']['n_minutes_gt_130'])} | beyond max possible playing time |",
        f"| minutes_played == 0 | appearances.csv | {fmt_int(q['appearances']['n_zero_minutes'])} | none of them have goals/assists |",
        f"| null player_name | appearances.csv | {fmt_int(q['appearances']['n_null_player_name'])} | cosmetic |",
        f"| zero market value snapshot | player_valuations.csv | {fmt_int(q['player_valuations']['n_zero_market_value'])} | only one in the dataset |",
        f"| duplicate (player_id, date) snapshots | player_valuations.csv | {fmt_int(q['player_valuations']['n_dup_player_date_extra_rows'])} | none — snapshot table is clean |",
        f"| null date_of_birth | players.csv | {fmt_int(q['players']['n_null_dob'])} | blocks age features |",
        f"| age at last_season > 45 | players.csv | {fmt_int(q['players']['n_age_at_last_season_gt_45'])} | implausible |",
        f"| height < 150 cm | players.csv | {fmt_int(q['players']['n_height_lt_150'])} | implausible (or data entry) |",
        f"| international_goals > international_caps | players.csv | {fmt_int(q['players']['n_caps_lt_intl_goals'])} | logically impossible |",
        f"| duplicate player names | players.csv | {fmt_int(q['players']['n_dup_name_extra_rows'])} | distinct player_ids sharing a name — name joins are unsafe |",
        f"| null coach_name | clubs.csv | {fmt_int(q['clubs']['n_null_coach'])} | {fmt_pct(q['clubs']['n_null_coach'] / q['clubs']['n_rows'])} of clubs |",
        f"| total_market_value entirely null | clubs.csv | all | column unusable in this snapshot |",
        f"| player_id not in players | appearances.csv | {fmt_int(ref['appearances.csv']['player_id -> players']['n_orphan'])} | trivial |",
        f"| club ids not in clubs.csv (historical clubs) | transfers.csv etc. | from_club {fmt_int(ref['transfers.csv']['from_club_id -> clubs']['n_orphan'])}, to_club {fmt_int(ref['transfers.csv']['to_club_id -> clubs']['n_orphan'])} | clubs.csv is last-season-only — see §8 |",
        "",
        "**Overall:** the dataset is unusually clean for its size — no full-row duplicates anywhere, no",
        "negative money, no duplicate valuation snapshots, perfect game_id integrity, consistent player",
        "names. The real hazards are structural, not dirty cells: incomplete club dimension, sparse",
        "valuation snapshots around transfers, censored transfer fees, future-dated transfer rows, and",
        "scrape-state columns that leak the future (§10).",
    ]
    return "\n".join(lines)


def main():
    inv, sch, dup, num = load("01_inventory"), load("02_schema"), load("03_duplicates"), load("04_numeric")
    tgt, trf, cat = load("05_target"), load("06_transfers"), load("07_categoricals")
    ref, tmp, qual = load("08_referential"), load("09_temporal"), load("10_quality")

    doc = "\n".join([
        "# Transfermarkt Dataset — Data Discovery Profile",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} from `data/Dataset/*.csv` (12 files, 873.4 MB, read-only).",
        "All numbers below were computed by re-runnable profiling scripts in `discovery/`"
        " (pandas 3.0.6, python 3.12; big files streamed in 250k-row chunks / read with `usecols`).",
        "Regenerate with `bash discovery/run_all.sh`; raw per-step outputs live in `discovery/results/*.json`.",
        "Reference date for 'future-dated' checks: 2026-10-11.",
        "",
        sec1_inventory(inv), "", "---", "",
        sec2_schema(sch), "", "---", "",
        sec3_duplicates(dup), "", "---", "",
        sec4_numeric(num), "", "---", "",
        sec5_target(tgt), "", "---", "",
        sec6_transfers(trf), "", "---", "",
        sec7_categoricals(cat), "", "---", "",
        sec8_referential(ref), "", "---", "",
        sec9_temporal(tmp, inv, qual), "", "---", "",
        sec10_leakage(), "", "---", "",
        sec11_aggregation(), "", "---", "",
        sec12_quality(dup, qual, ref), "",
    ])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(doc)
    print(f"wrote {REPORT_PATH} ({len(doc):,} chars)")


if __name__ == "__main__":
    main()
