"""The 20-question Spanish chat case set for E4 (LLM_PLAN §17.3).

Input: the case data defined in this file; optionally `ml/data/clean/players.parquet`
(offline validation) and the published `analytics` schema (player_id resolution).
Output: `list[ChatCase]` — question, expected tool, exact-match expected arguments, and
the outcome kind (`tool_call` / `refusal` / `not_found`); the CLI either validates the
set against the local Parquet or resolves it against the database.
Responsibility: encode each question's right answer as data the experiment scripts and
tests share, and own the two hard entity rules of §17.3: a non-existent entity must have
zero matches in the dataset, and a real player must be spelled exactly as the dataset
spells them (recorded `player_id` values make the expectation a fact, not a guess).

Two documented expectations to note when reviewing:

- The league cases expect `league_id` as the argument, per §17.3's case table. The
  backend's shipped chat tool schema (`chat_prompt.py`) does not advertise `league_id`
  on `search_players` today and `search_players_tool` ignores it — a plan/tool mismatch
  for the backend owner, recorded here rather than silently dropped: the plan's §17.3
  table is the authority for this case set.
- Cases 17–18 are the §17.3 multi-step shape. Their second call targets the top-valued
  hit of the expected search below the stated price cap (case 17) or the top hit
  outright (case 18). That target was derived when this set was written from the
  pipeline's own transform rows using the backend's ordering
  (`market_value_eur DESC, name ASC`), and `resolve_cases` records its `player_id` from
  the published database at load. Case 17's price cap is not expressible in the
  tool's arguments — an ambiguity in the *question* that §18 says writing the cases is
  meant to surface; it is kept and flagged in `notes`, not smoothed over.

The module keeps the cases, the database resolution and the Parquet validation together
because they are one artifact: a case without its validation rules is exactly the bug
("João Silva" is a real player) this set exists to prevent.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd
from harness import active_run_id, connect_readonly, fail

from delphos_ml.config import ConfigError, load_settings

ACTIVE_SEASON = 2025
SCRIPT = "cases_chat"

OUTCOME_TOOL_CALL = "tool_call"
OUTCOME_REFUSAL = "refusal"
OUTCOME_NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ChatCase:
    """One chat case: the Spanish question and the exact behaviour the model must show."""

    case_id: str
    shape: str
    question: str
    expected_tool: str | None
    expected_args: dict[str, Any] | None
    outcome: str = OUTCOME_TOOL_CALL
    player_name: str | None = None
    """Real player named in the question; resolved to `player_id` against the database."""
    fictional_name: str | None = None
    """Entity that must have zero matches in the dataset (empty-result path)."""
    next_tool: str | None = None
    """Second call of a multi-step case (§17.3 cases 17–18)."""
    next_args: dict[str, Any] | None = None
    notes: str = ""


CHAT_CASES: tuple[ChatCase, ...] = (
    # --- 1-4 search_players: position, league, valuation zone, compound filter ---
    ChatCase(
        "q01",
        "search-by-position",
        "¿Qué delanteros hay en el conjunto de datos?",
        "search_players",
        {"position": "Attack"},
        notes="Position enum per the shipped tool schema: Attack|Midfield|Defender.",
    ),
    ChatCase(
        "q02",
        "search-by-league",
        "Muéstrame jugadores de la Bundesliga.",
        "search_players",
        {"league_id": "L1"},
        notes=(
            "League must arrive as league_id (Transfermarkt id), not the display name. "
            "See the module docstring on the shipped tool schema not advertising it yet."
        ),
    ),
    ChatCase(
        "q03",
        "search-by-zone",
        "¿Qué jugadores están infravalorados?",
        "search_players",
        {"valuation_status": "undervalued"},
    ),
    ChatCase(
        "q04",
        "search-compound",
        "Muéstrame defensores infravalorados de la Premier League.",
        "search_players",
        {"position": "Defender", "valuation_status": "undervalued", "league_id": "GB1"},
        notes="Compound filter: every argument must match for argument exact-match (E4).",
    ),
    # --- 5-8 get_player_profile / get_player_valuation, resolved from the name ---
    ChatCase(
        "q05",
        "profile-by-name",
        "¿Quién es Lionel Messi?",
        "get_player_profile",
        {"player_id": None},
        player_name="Lionel Messi",
    ),
    ChatCase(
        "q06",
        "valuation-by-name",
        "¿Cuánto vale Erling Haaland?",
        "get_player_valuation",
        {"player_id": None},
        player_name="Erling Haaland",
    ),
    ChatCase(
        "q07",
        "profile-by-name",
        "Háblame del perfil de Neymar.",
        "get_player_profile",
        {"player_id": None},
        player_name="Neymar",
    ),
    ChatCase(
        "q08",
        "valuation-by-name",
        "¿Cuál es el valor justo de Lamine Yamal?",
        "get_player_valuation",
        {"player_id": None},
        player_name="Lamine Yamal",
    ),
    # --- 9-12 get_player_replacements ---
    ChatCase(
        "q09",
        "replacements-by-name",
        "¿Quién podría reemplazar a Vinicius Junior?",
        "get_player_replacements",
        {"player_id": None},
        player_name="Vinicius Junior",
    ),
    ChatCase(
        "q10",
        "replacements-by-name",
        "Busco alternativas más baratas para Jude Bellingham.",
        "get_player_replacements",
        {"player_id": None},
        player_name="Jude Bellingham",
    ),
    ChatCase(
        "q11",
        "replacements-by-name",
        "¿Qué candidatos de reposición tiene Robert Lewandowski?",
        "get_player_replacements",
        {"player_id": None},
        player_name="Robert Lewandowski",
    ),
    ChatCase(
        "q12",
        "replacements-by-name",
        "Dime los reemplazos tácticos de Mohamed Salah.",
        "get_player_replacements",
        {"player_id": None},
        player_name="Mohamed Salah",
    ),
    # --- 13-16 get_cluster_summary: the right cluster ---
    ChatCase(
        "q13",
        "cluster-summary",
        "¿Qué es un Box-to-Box?",
        "get_cluster_summary",
        {"cluster_id": 1},
        notes="delphos_domain CLUSTER_LABELS short name for cluster 1.",
    ),
    ChatCase(
        "q14",
        "cluster-summary",
        "Háblame de los creadores ofensivos.",
        "get_cluster_summary",
        {"cluster_id": 0},
        notes="Cluster 0 archetype name: Creadores Ofensivos y Finalizadores.",
    ),
    ChatCase(
        "q15",
        "cluster-summary",
        "¿Qué perfil táctico tiene un ancla defensiva?",
        "get_cluster_summary",
        {"cluster_id": 2},
    ),
    ChatCase(
        "q16",
        "cluster-summary",
        "Resume a los especialistas de contención.",
        "get_cluster_summary",
        {"cluster_id": 2},
        notes="Cluster 2 full-name vocabulary: Anclas Defensivas y Especialistas de Contención.",
    ),
    # --- 17-18 multi-step: search_players, then get_player_valuation on the best hit ---
    ChatCase(
        "q17",
        "multi-step",
        "Búscame un delantero barato por debajo de 10M en LaLiga y dime cuánto vale.",
        "search_players",
        {"position": "Attack", "league_id": "ES1"},
        next_tool="get_player_valuation",
        next_args={"player_id": None},
        player_name="Adnan Januzaj",
        notes=(
            "Target = top-valued ES1 attacker below €10M under the backend ordering "
            "(market_value_eur DESC, name ASC), derived when the set was written; "
            "resolved name -> player_id at load. The price cap is not expressible in "
            "search_players: ambiguity in the question, flagged per §18."
        ),
    ),
    ChatCase(
        "q18",
        "multi-step",
        "Encuéntrame un centrocampista de la Serie A y dime su valor justo.",
        "search_players",
        {"position": "Midfield", "league_id": "IT1"},
        next_tool="get_player_valuation",
        next_args={"player_id": None},
        player_name="Sergej Milinković-Savić",
        notes="Target = top-valued IT1 midfielder under the backend ordering, derived at "
        "write time; resolved name -> player_id at load.",
    ),
    # --- 19 out-of-scope: no tool, a refusal ---
    ChatCase(
        "q19",
        "out-of-scope",
        "¿Quién ganó la final de la Champions League de 2019?",
        None,
        None,
        outcome=OUTCOME_REFUSAL,
        notes="Must produce a refusal, not a fabricated answer; any tool call fails the case.",
    ),
    # --- 20 non-existent entity: empty-result path, honest "not found" ---
    ChatCase(
        "q20",
        "non-existent-entity",
        "Escribe un informe sobre Marco Nobody.",
        None,
        None,
        outcome=OUTCOME_NOT_FOUND,
        fictional_name="Marco Nobody",
        notes=(
            "Zero matches in the dataset by construction. A tool call returning an empty "
            "result is allowed; a fabricated report about a player that does not exist fails."
        ),
    ),
)

FORBIDDEN_REAL_SPELLINGS: dict[str, str] = {
    "Kylian Mbappe": 'absent from the dataset; the dataset spells it "Kylian Mbappé"',
    "João Silva": "a real player in players.parquet (2 matches); never use it as a "
    "fictional entity — it would test name resolution, not the empty-result path",
}


class ParquetValidationError(RuntimeError):
    """Data-directory resolution failed while validating the chat case set."""


def players_parquet_path() -> Path:
    """`<data dir>/clean/players.parquet`, resolved the way the pipeline resolves it."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        raise ParquetValidationError(str(exc)) from exc
    return settings.data_dir / "clean" / "players.parquet"


def validate_against_parquet(
    cases: tuple[ChatCase, ...] = CHAT_CASES, parquet_path: Path | None = None
) -> list[str]:
    """Return every entity-rule violation in the case set; empty means the set is valid.

    Checks against `ml/data/clean/players.parquet` (no database, no server): every
    `player_name` resolves to exactly one row, every `fictional_name` to zero rows, and
    the known-bad spellings of FORBIDDEN_REAL_SPELLINGS are not used anywhere.
    """
    path = parquet_path if parquet_path is not None else players_parquet_path()
    if not path.is_file():
        return [f"missing {path}; run `delphos-pipeline clean` first"]
    names = pd.read_parquet(path, columns=["player_id", "name"])["name"]
    counts = names.value_counts()

    def count_of(name: str) -> int:
        return int(counts.get(name, 0))

    errors: list[str] = []
    for name, why in FORBIDDEN_REAL_SPELLINGS.items():
        if any(name == case.player_name for case in cases):
            errors.append(f"{name!r} is used as a real player but is {why}")
        if any(name == case.fictional_name for case in cases):
            errors.append(f"{name!r} is used as a fictional entity but is {why}")
    for case in cases:
        if case.player_name is not None:
            found = count_of(case.player_name)
            if found != 1:
                errors.append(
                    f"{case.case_id}: player {case.player_name!r} matches {found} rows in "
                    f"{path.name}; expected exactly one (exact dataset spelling)"
                )
        if case.fictional_name is not None:
            found = count_of(case.fictional_name)
            if found != 0:
                errors.append(
                    f"{case.case_id}: fictional entity {case.fictional_name!r} matches "
                    f"{found} rows in {path.name}; expected zero (empty-result path)"
                )
    return errors


def resolve_cases(script: str = SCRIPT) -> list[ChatCase]:
    """Resolve every named entity to a `player_id` against the published database.

    A real player must exist in `analytics.dim_players` for the active run and be
    published in `analytics.fct_player_predictions` for the active season — a player
    missing from the predictions would silently turn a resolution case into an
    empty-result case, so it exits with `<script> failed: ...` instead. A fictional
    entity must have zero matches there too. Multi-step cases put the id into
    `next_args`; single-call cases into `expected_args`.
    """
    resolved: list[ChatCase] = []
    with connect_readonly(script) as conn:
        run_id = active_run_id(conn, script)
        with conn.cursor() as cur:
            for case in CHAT_CASES:
                updated = case
                if case.fictional_name is not None:
                    cur.execute(
                        "SELECT COUNT(*) FROM analytics.dim_players "
                        "WHERE model_run_id = %s AND name = %s;",
                        (run_id, case.fictional_name),
                    )
                    if int(cur.fetchone()[0]) != 0:
                        fail(
                            f"{case.case_id}: fictional entity {case.fictional_name!r} exists "
                            "in the published dim_players; it would test name resolution, "
                            "not the empty-result path",
                            script=script,
                        )
                if case.player_name is not None:
                    cur.execute(
                        "SELECT player_id FROM analytics.dim_players "
                        "WHERE model_run_id = %s AND name = %s;",
                        (run_id, case.player_name),
                    )
                    ids = [int(row[0]) for row in cur.fetchall()]
                    if len(ids) != 1:
                        fail(
                            f"{case.case_id}: player {case.player_name!r} matches "
                            f"{len(ids)} rows in published dim_players for run {run_id}; "
                            "expected exactly one (exact dataset spelling)",
                            script=script,
                        )
                    player_id = ids[0]
                    cur.execute(
                        "SELECT 1 FROM analytics.fct_player_predictions "
                        "WHERE model_run_id = %s AND player_id = %s AND season = %s;",
                        (run_id, player_id, ACTIVE_SEASON),
                    )
                    if cur.fetchone() is None:
                        fail(
                            f"{case.case_id}: player {case.player_name!r} (id {player_id}) "
                            f"is not published in fct_player_predictions for season "
                            f"{ACTIVE_SEASON}; the case would test the empty-result path "
                            "by accident",
                            script=script,
                        )
                    if case.next_tool is not None:
                        updated = replace(updated, next_args={"player_id": player_id})
                    else:
                        updated = replace(updated, expected_args={"player_id": player_id})
                resolved.append(updated)
    return resolved


def main() -> None:
    """Validate the chat case set or resolve it against the published database.

    `--check-parquet` validates every entity rule against `ml/data/clean/players.parquet`
    and exits without touching the database or any server. The default resolves the set
    against `analytics` and prints the expected tools and arguments. `--help` prints this
    text and exits without any contact.
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--check-parquet",
        action="store_true",
        help="validate entity rules against the local Parquet only (no database)",
    )
    args = parser.parse_args()
    if args.check_parquet:
        try:
            errors = validate_against_parquet()
        except ParquetValidationError as exc:
            fail(str(exc), script=SCRIPT)
        if errors:
            for error in errors:
                print(f"- {error}")
            fail(f"{len(errors)} entity-rule violation(s) in the chat case set", script=SCRIPT)
        print(f"All {len(CHAT_CASES)} chat cases pass the players.parquet entity rules")
        return
    cases = resolve_cases()
    print(f"{'case_id':<6} {'outcome':<10} {'tool':<24} arguments")
    for case in cases:
        args_text = case.expected_args if case.expected_tool else f"({case.outcome})"
        print(f"{case.case_id:<6} {case.outcome:<10} {str(case.expected_tool):<24} {args_text}")
        if case.next_tool:
            print(f"{'':>6} {'->':<10} {case.next_tool:<24} {case.next_args}")
    print(f"\n{len(cases)} chat cases resolved from the active model run")


if __name__ == "__main__":
    main()
