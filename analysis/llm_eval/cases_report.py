"""The 9-player report case set: one published player per (cluster × valuation-zone) cell.

Input: the published `analytics` schema through a read-only psycopg session —
`analytics.fct_player_predictions.valuation_status` (migrations/0002, line 149) and
`analytics.fct_clusters.cluster_id` (line 171) for the active model run, joined to
`analytics.dim_players` for the name.
Output: `list[ReportCase]`, each carrying its resolved `player_id`; the CLI prints the
table. Writes nothing and touches no inference server.
Responsibility: define the nine cells of LLM_PLAN §17.2's E1–E3 case set and resolve one
deterministic representative per cell so expected values are facts from the published
database, not guesses.

The cases come from the database, not from `ml/data/**.parquet`, because
`valuation_status` and `cluster_id` exist only after `train` and `publish`:
`ml/data/transform/player_seasons.parquet` carries neither (ADR-014 scope note,
WORK_PLAN 2026-11-08). The cell grid and the per-cell representative rule (lowest
`player_id` in the cell, i.e. first by primary-key order) live here as data so the
experiment scripts and the tests share one definition; the tests validate the grid
without a database.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from harness import active_run_id, connect_readonly, fail

ZONES: tuple[str, ...] = ("undervalued", "fair", "overvalued")
CLUSTERS: tuple[int, ...] = (0, 1, 2)
ACTIVE_SEASON = 2025

CELLS: tuple[tuple[int, str], ...] = tuple(
    (cluster, zone) for cluster in CLUSTERS for zone in ZONES
)
"""The nine (cluster × zone) cells, in a fixed order so runs are comparable."""

CELL_SQL = """
    SELECT p.player_id, p.name
    FROM analytics.fct_player_predictions pred
    JOIN analytics.fct_clusters cl
      ON cl.model_run_id = pred.model_run_id
     AND cl.player_id = pred.player_id AND cl.season = pred.season
    JOIN analytics.dim_players p
      ON p.model_run_id = pred.model_run_id AND p.player_id = pred.player_id
    WHERE pred.model_run_id = %s
      AND pred.season = %s
      AND cl.cluster_id = %s
      AND pred.valuation_status = %s
    ORDER BY p.player_id
    LIMIT 1;
"""


@dataclass(frozen=True)
class ReportCase:
    """One report case: the cell it represents and the published player resolved for it."""

    case_id: str
    cluster_id: int
    valuation_zone: str
    player_id: int
    player_name: str


def resolve_report_cases(script: str = "cases_report") -> list[ReportCase]:
    """Resolve one published player per cell from the active model run.

    Deterministic (lowest player_id per cell) so repeated runs compare the same nine
    players. Exits with `<script> failed: ...` when the database is unreachable, no run
    is active, or a cell is empty — an empty cell is a data fact, not a silent skip.
    """
    cases: list[ReportCase] = []
    with connect_readonly(script) as conn:
        run_id = active_run_id(conn, script)
        with conn.cursor() as cur:
            for cluster, zone in CELLS:
                cur.execute(CELL_SQL, (run_id, ACTIVE_SEASON, cluster, zone))
                row = cur.fetchone()
                if row is None:
                    fail(
                        f"cell (cluster={cluster}, zone={zone}) is empty for run {run_id} "
                        f"season {ACTIVE_SEASON}; the published data cannot fill the 3×3 grid",
                        script=script,
                    )
                cases.append(
                    ReportCase(
                        case_id=f"c{cluster}_{zone}",
                        cluster_id=cluster,
                        valuation_zone=zone,
                        player_id=int(row[0]),
                        player_name=str(row[1]),
                    )
                )
    return cases


def main() -> None:
    """Resolve the nine report cases from the published database and print the table.

    `--help` prints this text without contacting the database or any server.
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.parse_args()
    cases = resolve_report_cases(script="cases_report")
    print(f"{'case_id':<20} {'cluster':>7} {'zone':<13} {'player_id':>9}  name")
    for case in cases:
        print(
            f"{case.case_id:<20} {case.cluster_id:>7} {case.valuation_zone:<13} "
            f"{case.player_id:>9}  {case.player_name}"
        )
    print(f"\n{len(cases)} report cases resolved from the active model run")


if __name__ == "__main__":
    main()
