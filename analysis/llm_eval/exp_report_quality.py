"""E1–E3: report quality, Spanish register, and fact-card token budget (LLM_PLAN §17.2).

Input: the nine report cases resolved from the published database (`cases_report`), the
shipped backend report pipeline imported from `backend/src` (fact card, Spanish prompt,
draft schema, draft renderer, deterministic renderer, numeric verifier), and the
inference server through `harness`.
Output: `e1.jsonl`, `e2.jsonl`, `e3.jsonl` call/score/summary rows, the blind pairwise
artifacts `e1_blind_pairs.json` + `e1_pair_key.json`, and printed decision-rule readouts
under `analysis/output/llm/`.
Responsibility: run E1, E2 and E3 over ONE generation pass of the nine cases so the three
measurements see identical calls — E1 compares the LLM report against
`report_render.render_deterministic_report` in a blind pairwise write-up with the A/B
order randomised per case and recorded; E2 scores terminology and register as `pending`
for the later blind J1/human read and computes the deterministic format check over every
numeric token; E3 reads the server's `timings.prompt_n` / `predicted_n` and flags any
case over the 8000-prompt-token budget.

No judge runs here (§17.1: J1 is an offline blind pairwise step; the human read is the
tiebreaker). `--ratings` is the one offline mode: given an existing `e1_pair_key.json`
and a `case_id,preferred` CSV, it computes the blind human preference rate for the LLM
side and exits without contacting any server.

The formatting accept-set mirrors `backend/.../report_format.py` branch-for-branch:
`€25.0M` (M: exactly one decimal), `€540K` (K: toFixed(0), so `€1000K` is legal),
`€250` below 1e3, integer counts, `N%` (the renderer's literal `+32%` also passes),
`1.8x` ratios, `0.34`-style two-decimal `format_fixed(raw, 2)` residuals, and `N/D`
(which contains no digits and is therefore never a numeric token).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cases_report import ReportCase, resolve_report_cases
from harness import (
    CompletionResult,
    HarnessConfig,
    HarnessError,
    active_run_id,
    backend_import,
    build_request,
    build_row,
    call_server,
    connect_readonly,
    connect_readonly_async,
    fail,
    load_config,
    output_dir,
    preflight,
    record,
)

SCRIPT = "exp_report_quality"
E1, E2, E3 = "e1", "e2", "e3"
DEFAULT_SEED = 101
PROMPT_BUDGET = 8000
REPORT_MAX_TOKENS = 1400
"""Default `DELPHOS_LLM_REPORT_MAX_TOKENS` (LLM_PLAN §13); the chat cap is 512."""

# Output grammar of report_format.py (see module docstring); fullmatch per token.
_PRODUCT_TOKEN_SHAPES: tuple[re.Pattern[str], ...] = (
    re.compile(r"€-?\d+\.\dM"),  # format_eur_m >= 1e6: toFixed(1) + "M"
    re.compile(r"€-?\d+K"),  # >= 1e3: toFixed(0) + "K" (€1000K is legal)
    re.compile(r"€-?\d+"),  # < 1e3: toFixed(0)
    re.compile(r"[+-]?\d+%"),  # format_pct / points_entry integers; "+" from the renderer
    re.compile(r"-?\d+\.\dx"),  # format_ratio: toFixed(1) + "x"
    re.compile(r"-?\d+\.\d{2}"),  # format_fixed(raw, 2) residuals (residual_log10)
    re.compile(r"-?\d+"),  # format_count integers (years, minutes, goals)
)


def format_violations(text: str, *, script: str = SCRIPT) -> list[str]:
    """Numeric tokens in `text` that are not in the product's display formats (E2).

    Extraction is the shipped verifier's tokeniser (`report_verify`, the same one D1
    uses, imported through `harness.backend_import`); this function only applies the
    accept-set above, so the check is exact and free per §17.2.
    """
    report_verify = backend_import("delphos_backend.services.report_verify", script)
    return [
        token.token
        for token in report_verify.extract_number_tokens(text)
        if not any(pattern.fullmatch(token.token) for pattern in _PRODUCT_TOKEN_SHAPES)
    ]


def blind_pair(
    rng: random.Random, texts: Mapping[str, str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Randomise a pairwise presentation: returns ({label: text}, {label: source}).

    The first dict is what the reader sees (no source names); the second is the key
    written to a separate file so the read stays blind (§17.1).
    """
    sources = list(texts)
    rng.shuffle(sources)
    labels = [chr(ord("A") + i) for i in range(len(sources))]
    blinded = {label: texts[source] for label, source in zip(labels, sources, strict=True)}
    key = dict(zip(labels, sources, strict=True))
    return blinded, key


def preference_rate(
    key: Mapping[str, Mapping[str, str]], ratings: Mapping[str, str]
) -> dict[str, Any]:
    """Blind human preference rate for the LLM side, from the key and the ratings.

    `key` maps case_id -> {label: source}; `ratings` maps case_id -> chosen label.
    Unrated or unkeyed cases are reported, never silently dropped from the denominator.
    """
    rated = sorted(c for c in key if ratings.get(c) in key[c])
    llm_preferred = sum(1 for c in rated if key[c][ratings[c]] == "llm")
    return {
        "rated": len(rated),
        "llm_preferred": llm_preferred,
        "preference_rate": (llm_preferred / len(rated)) if rated else None,
        "unrated": sorted(set(key) - set(rated)),
        "unknown_ratings": sorted(c for c in ratings if c not in key),
    }


@dataclass(frozen=True)
class ReportContext:
    """One report case with its shipped fact card and deterministic baseline text."""

    case: ReportCase
    card: dict[str, Any]
    deterministic_text: str


@dataclass(frozen=True)
class ReportGenOutcome:
    """One report generation: everything E1/E2/E3/E7/E9 score from a single call."""

    case_id: str
    arm: str
    seed: int
    ok: bool
    error: str | None
    latency_ms: float
    schema_valid: bool
    prose: str | None
    draft_text: str | None
    fact_refs: tuple[str, ...]
    d1_violations: int | None
    format_violations: tuple[str, ...]
    prompt_n: int
    predicted_n: int
    request: dict[str, Any] | None
    result: CompletionResult | None


def report_max_tokens() -> int:
    """`DELPHOS_LLM_REPORT_MAX_TOKENS`, the §13 report cap (the chat cap stays 512)."""
    import os

    raw = os.environ.get("DELPHOS_LLM_REPORT_MAX_TOKENS")
    if raw is None or raw == "":
        return REPORT_MAX_TOKENS
    try:
        return int(raw)
    except ValueError as exc:
        raise HarnessError(f"DELPHOS_LLM_REPORT_MAX_TOKENS={raw!r} is not an integer") from exc


async def load_report_contexts(
    cases: list[ReportCase], run_id: str, script: str = SCRIPT
) -> dict[str, ReportContext]:
    """Fetch profile/valuation/replacements with the shipped repositories and build cards.

    A case without a published profile or valuation is a broken case, so it exits with
    `<script> failed: ...` instead of generating from missing facts.
    """
    players = backend_import("delphos_backend.repositories.players", script)
    valuations = backend_import("delphos_backend.repositories.valuations", script)
    replacements = backend_import("delphos_backend.repositories.replacements", script)
    facts = backend_import("delphos_backend.services.report_facts", script)
    render = backend_import("delphos_backend.services.report_render", script)

    conn = await connect_readonly_async(script)
    contexts: dict[str, ReportContext] = {}
    try:
        for case in cases:
            profile = await players.get_player_profile(conn, run_id, case.player_id)
            valuation = await valuations.get_player_valuation(conn, run_id, case.player_id)
            if profile is None or valuation is None:
                fail(
                    f"{case.case_id}: player {case.player_id} has no published profile/"
                    "valuation for the active run; the report case cannot be grounded",
                    script=script,
                )
            payload = await replacements.get_player_replacements(conn, run_id, case.player_id)
            card = facts.build_fact_card(profile, valuation, payload)
            contexts[case.case_id] = ReportContext(
                case=case, card=card, deterministic_text=render.render_deterministic_report(card)
            )
    finally:
        await conn.close()
    return contexts


def generate_one_report(
    ctx: ReportContext,
    *,
    experiment: str,
    arm: str,
    seed: int,
    config: HarnessConfig | None = None,
    enable_thinking: bool | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    presence_penalty: float | None = None,
    script: str = SCRIPT,
) -> ReportGenOutcome:
    """One schema-constrained draft call via the harness; records one JSONL call row.

    This is the shipped §7.2 request (report SYSTEM_PROMPT + fact-card JSON +
    `ScoutingReportDraft` json_schema), rendered by the shipped `draft_render` and
    scored by the shipped verifier — with an explicit seed the shipped path cannot
    guarantee. Generation failures are recorded and returned, never raised, so one bad
    case cannot abort an experiment mid-run.
    """
    report_prompt = backend_import("delphos_backend.services.report_prompt", script)
    schema_mod = backend_import("delphos_backend.services.report_schema", script)
    draft_render = backend_import("delphos_backend.services.draft_render", script)
    facts = backend_import("delphos_backend.services.report_facts", script)
    verify = backend_import("delphos_backend.services.report_verify", script)

    messages = [
        {"role": "system", "content": report_prompt.SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(ctx.card, ensure_ascii=False)},
    ]
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "scouting_report_draft",
            "schema": schema_mod.ScoutingReportDraft.model_json_schema(),
        },
    }
    request = build_request(
        messages,
        seed=seed,
        config=config,
        enable_thinking=enable_thinking,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        presence_penalty=presence_penalty,
        max_tokens=report_max_tokens(),
        response_format=response_format,
    )

    started = time.perf_counter()
    try:
        result = call_server(request, config=config)
    except HarnessError as exc:
        record(
            experiment,
            {
                "ts": now_iso(),
                "experiment": experiment,
                "kind": "call",
                "case_id": ctx.case.case_id,
                "arm": arm,
                "seed": seed,
                "error": str(exc),
            },
        )
        return ReportGenOutcome(
            case_id=ctx.case.case_id,
            arm=arm,
            seed=seed,
            ok=False,
            error=str(exc),
            latency_ms=(time.perf_counter() - started) * 1000.0,
            schema_valid=False,
            prose=None,
            draft_text=None,
            fact_refs=(),
            d1_violations=None,
            format_violations=(),
            prompt_n=0,
            predicted_n=0,
            request=request,
            result=None,
        )
    latency_ms = (time.perf_counter() - started) * 1000.0
    prompt_n, predicted_n = timings_of(result)

    fact_refs = tuple(report_prompt.PLACEHOLDER_RE.findall(result.content))
    prose: str | None = None
    schema_valid = False
    d1: int | None = None
    fmt: tuple[str, ...] = ()
    error: str | None = None
    try:
        draft = schema_mod.ScoutingReportDraft.model_validate_json(result.content)
        prose = draft_render.render_draft(draft, ctx.card)
        schema_valid = True
        allowed = facts.allowed_number_tokens(ctx.card)
        d1 = len(verify.verify_prose_numbers(prose, allowed).violations)
        fmt = tuple(format_violations(prose, script=script))
    except ValueError as exc:  # pydantic ValidationError and UnknownPlaceholderError
        error = f"schema/render failure: {exc}"

    record(
        experiment,
        build_row(
            request,
            result,
            experiment=experiment,
            case_id=ctx.case.case_id,
            extra={
                "kind": "call",
                "arm": arm,
                "latency_ms": round(latency_ms, 1),
                "schema_valid": schema_valid,
                "fact_ref_count": len(fact_refs),
                "d1_violations": d1,
                "format_violations": list(fmt),
                "prompt_n": prompt_n,
                "predicted_n": predicted_n,
                **({"error": error} if error else {}),
            },
        ),
    )
    return ReportGenOutcome(
        case_id=ctx.case.case_id,
        arm=arm,
        seed=seed,
        ok=True,
        error=error,
        latency_ms=latency_ms,
        schema_valid=schema_valid,
        prose=prose,
        draft_text=result.content,
        fact_refs=fact_refs,
        d1_violations=d1,
        format_violations=fmt,
        prompt_n=prompt_n,
        predicted_n=predicted_n,
        request=request,
        result=result,
    )


def timings_of(result: CompletionResult) -> tuple[int, int]:
    """prompt_n / predicted_n from the server's timings, with usage as the fallback."""
    timings = result.timings
    prompt_n = int(timings.get("prompt_n") or result.usage.get("prompt_tokens") or 0)
    predicted_n = int(timings.get("predicted_n") or result.usage.get("completion_tokens") or 0)
    return prompt_n, predicted_n


def now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds")


async def run_passes(
    cases: list[ReportCase], run_id: str, seed: int, config: HarnessConfig
) -> None:
    """The single generation pass feeding E1 (pairs + D1), E2 (format) and E3 (budget)."""
    contexts = await load_report_contexts(cases, run_id, SCRIPT)
    pairs: dict[str, Any] = {}
    keys: dict[str, Any] = {}
    e1_scores: list[dict[str, Any]] = []
    e2_scores: list[dict[str, Any]] = []
    e3_scores: list[dict[str, Any]] = []
    failed = 0

    for case in cases:
        ctx = contexts[case.case_id]
        outcome = generate_one_report(ctx, experiment=E1, arm="default", seed=seed, config=config)
        if not outcome.ok:
            failed += 1
            e1_scores.append({"case_id": case.case_id, "ok": False, "error": outcome.error})
            continue
        if outcome.schema_valid and outcome.prose is not None:
            blinded, key = blind_pair(
                random.Random(f"{seed}:{case.case_id}"),
                {"llm": outcome.prose, "deterministic": ctx.deterministic_text},
            )
            pairs[case.case_id] = blinded
            keys[case.case_id] = key
            e1_scores.append(
                {
                    "case_id": case.case_id,
                    "ok": True,
                    "schema_valid": True,
                    "d1_violations": outcome.d1_violations,
                    "fact_ref_count": len(outcome.fact_refs),
                }
            )
            e2_scores.append(
                {
                    "case_id": case.case_id,
                    "ok": True,
                    "schema_valid": True,
                    "format_violations": list(outcome.format_violations),
                    "formatting_ok": not outcome.format_violations,
                    "terminology": "pending-j1",
                    "register": "pending-j1",
                    "judged": False,
                }
            )
        else:
            e1_scores.append(
                {"case_id": case.case_id, "ok": True, "schema_valid": False, "error": outcome.error}
            )
            e2_scores.append(
                {"case_id": case.case_id, "ok": True, "schema_valid": False, "error": outcome.error}
            )
        e3_scores.append(
            {
                "case_id": case.case_id,
                "ok": True,
                "prompt_n": outcome.prompt_n,
                "predicted_n": outcome.predicted_n,
                "over_prompt_budget": outcome.prompt_n > PROMPT_BUDGET,
            }
        )

    out = output_dir()
    (out / "e1_blind_pairs.json").write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "e1_pair_key.json").write_text(
        json.dumps(keys, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    for score in e1_scores:
        record(E1, {"experiment": E1, "kind": "score", "arm": "default", "seed": seed, **score})
    for score in e2_scores:
        record(E2, {"experiment": E2, "kind": "score", "arm": "default", "seed": seed, **score})
    for score in e3_scores:
        record(E3, {"experiment": E3, "kind": "score", "arm": "default", "seed": seed, **score})

    scored = [s for s in e1_scores if s.get("ok")]
    d1_total = sum(int(s.get("d1_violations") or 0) for s in scored if s.get("schema_valid"))
    record(
        E1,
        {
            "experiment": E1,
            "kind": "summary",
            "arm": "default",
            "cases": len(cases),
            "generations_failed": failed,
            "blind_pairs_written": len(pairs),
            "d1_total_violations": d1_total,
            "d1_zero": d1_total == 0,
            "human_preference_rate": None,
            "judge": "pending-j1-and-human-read",
        },
    )
    fmt_scored = [s for s in e2_scores if s.get("schema_valid")]
    fmt_ok = sum(1 for s in fmt_scored if s.get("formatting_ok"))
    record(
        E2,
        {
            "experiment": E2,
            "kind": "summary",
            "arm": "default",
            "schema_valid_reports": len(fmt_scored),
            "formatting_pass": f"{fmt_ok}/{len(fmt_scored)}",
            "formatting_threshold": "8/9",
            "terminology_pass": None,
            "register_pass": None,
            "judged": False,
        },
    )
    over = [s["case_id"] for s in e3_scores if s.get("over_prompt_budget")]
    record(
        E3,
        {
            "experiment": E3,
            "kind": "summary",
            "arm": "default",
            "cases": len(e3_scores),
            "max_prompt_n": max((int(s["prompt_n"]) for s in e3_scores), default=0),
            "mean_prompt_n": (sum(int(s["prompt_n"]) for s in e3_scores) // max(len(e3_scores), 1)),
            "prompt_budget": PROMPT_BUDGET,
            "cases_over_budget": over,
            "budget_ok": not over,
        },
    )

    print(f"E1: {len(pairs)} blind pairs written (e1_blind_pairs.json + e1_pair_key.json)")
    print(f"E1: D1 violations {d1_total} (must be 0); human preference pending the blind read")
    print(
        f"E2: formatting pass {fmt_ok}/{len(fmt_scored)} (threshold 8/9); "
        "terminology/register pending J1"
    )
    print(
        f"E3: max prompt_n {max((int(s['prompt_n']) for s in e3_scores), default=0)} "
        f"vs budget {PROMPT_BUDGET}; over-budget: {over or 'none'}"
    )


def run_ratings(ratings_path: str) -> None:
    """Offline: compute the blind human preference rate from the existing key + CSV.

    No server, no database: `--ratings` only reads `e1_pair_key.json` and the CSV
    (`case_id,preferred` with preferred in A/B) from the finished blind read.
    """
    key_path = output_dir() / "e1_pair_key.json"
    if not key_path.is_file():
        fail(f"missing {key_path}; run E1 first", script=SCRIPT)
    try:
        key = json.loads(key_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        fail(f"cannot parse {key_path}: {exc}", script=SCRIPT)
    ratings: dict[str, str] = {}
    try:
        with open(ratings_path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                ratings[row["case_id"].strip()] = row["preferred"].strip().upper()
    except (OSError, KeyError) as exc:
        fail(f"cannot read ratings {ratings_path}: {exc}", script=SCRIPT)
    rate = preference_rate(key, ratings)
    print(json.dumps(rate, ensure_ascii=False, indent=2))
    if rate["preference_rate"] is None:
        fail("no rated cases; nothing to compute", script=SCRIPT)
    record(
        E1,
        {"experiment": E1, "kind": "summary", "arm": "human_read", **rate},
    )


def main() -> None:
    """Run E1, E2 and E3 over one seeded generation pass of the nine report cases.

    `--help` prints this text without contacting a server, the database, or the backend.
    `--ratings FILE` is the offline mode described in the module docstring.
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="explicit seed for every generation (default: %(default)s)",
    )
    parser.add_argument(
        "--ratings", metavar="CSV", help="offline: compute the E1 preference rate from this CSV"
    )
    args = parser.parse_args()
    if args.ratings:
        run_ratings(args.ratings)
        return

    config = load_config()
    preflight()
    print(f"E1–E3: 9 report cases x 1 seed = 9 generations (seed {args.seed})")
    cases = resolve_report_cases(script=SCRIPT)
    with connect_readonly(SCRIPT) as conn:
        run_id = active_run_id(conn, SCRIPT)
    asyncio.run(run_passes(cases, run_id, args.seed, config))


if __name__ == "__main__":
    main()
