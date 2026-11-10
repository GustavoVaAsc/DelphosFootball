"""E7–E9: sampling sweeps and the presence-penalty knob (LLM_PLAN §17.4).

Input: the 9 report cases and the 20 chat cases, the shipped generation paths from
`exp_report_quality` and `exp_tool_calling`, and the inference server through `harness`.
Output: `e7.jsonl`, `e8.jsonl`, `e9.jsonl` call/score/summary rows, the blind
`e7_j1_pairs.json` + `e7_j1_key.json` artifacts for the prose-quality read, and printed
decision-rule readouts under `analysis/output/llm/`.
Responsibility: run the §17.4 grids — E7 report sweep 9 cases x 4 arms x **3 seeds**,
E8 chat sweep 20 cases x 4 arms x **2 seeds**, E9 presence-penalty A/B on both case sets
x 1 seed — and score them: D1 violation rate, **cross-seed Jaccard similarity of the
fact-reference sets** (higher = MORE repeatable; named similarity, never "variance",
because inverting the name would invert the decision), argument exact-match plus error
magnitude on failures for E8, and degeneracy (repeated 8-gram rate, lexically identical
outputs across seeds) and distinct-3-gram diversity for the prose arms.

`presence_penalty` is the only repetition knob under test: the request builder has no
`repeat_penalty` field and this module never sets one — a repeat penalty would punish
re-using `€` and the player's name, which a grounded report must do (§17.4 E9).
Prose quality is judged later, blind and paired against arm A; the pairs are written
here with a randomised order and a separate key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import exp_report_quality as erq
import exp_tool_calling as etc
from cases_chat import ChatCase, resolve_cases
from cases_report import ReportCase, resolve_report_cases
from harness import (
    HarnessConfig,
    active_run_id,
    connect_readonly,
    fail,
    load_config,
    output_dir,
    preflight,
    record,
)

SCRIPT = "exp_sampling"
E7, E8, E9 = "e7", "e8", "e9"
DEFAULT_EXPERIMENT = E7

E7_SEEDS: tuple[int, ...] = (101, 202, 303)
"""§17.4: three seeds per report cell — one seed cannot measure repeatability."""
E8_SEEDS: tuple[int, ...] = (101, 202)
"""Two seeds per chat cell: one seed's standard error (~9 pts at 80%) hides the sweep."""
E9_SEEDS: tuple[int, ...] = (101,)


@dataclass(frozen=True)
class SamplingArm:
    """One grid point: the three §13 sampling knobs plus the E9 penalty variant."""

    name: str
    temperature: float
    top_p: float
    top_k: int
    presence_penalty: float = 0.0
    note: str = ""


REPORT_ARMS: tuple[SamplingArm, ...] = (
    SamplingArm("A", 0.7, 0.8, 20, note="shipped default (Qwen3.5 card)"),
    SamplingArm("B", 0.2, 0.8, 20, note="lower temperature"),
    SamplingArm("C", 0.4, 0.9, 40, note="midpoint; llama.cpp-ish top_k/top_p"),
    SamplingArm("D", 0.1, 0.8, 20, note="near-greedy faithfulness ceiling"),
)
CHAT_ARMS: tuple[SamplingArm, ...] = REPORT_ARMS
"""E8 uses the same grid as E7, scored on tool arguments instead of prose."""

E9_ARMS: tuple[SamplingArm, ...] = (
    SamplingArm("A", 0.7, 0.8, 20, note="shipped default, no penalty"),
    SamplingArm("A_pp1.5", 0.7, 0.8, 20, presence_penalty=1.5, note="card's presence_penalty"),
)
"""E9's A/B pair; `repeat_penalty` is deliberately not a knob anywhere in this file."""


def expand_grid(
    cases: Sequence[Any], arms: Sequence[SamplingArm], seeds: Sequence[int]
) -> list[tuple[Any, SamplingArm, int]]:
    """Every (case, arm, seed) combination once — the §17.5 run counts follow from this."""
    return [(case, arm, seed) for arm in arms for seed in seeds for case in cases]


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard similarity of two fact-reference sets: identical 1.0, disjoint 0.0."""
    left, right = set(a), set(b)
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def cross_seed_similarity(sets: Sequence[Iterable[str]]) -> float:
    """Mean pairwise Jaccard across seeds: HIGHER means MORE repeatable (never 'variance')."""
    materialised = [set(s) for s in sets]
    if len(materialised) < 2:
        return 1.0
    pairs = [
        (materialised[i], materialised[j])
        for i in range(len(materialised))
        for j in range(i + 1, len(materialised))
    ]
    return sum(jaccard(a, b) for a, b in pairs) / len(pairs)


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def has_repeated_8gram(text: str) -> bool:
    """True when any run of eight words recurs — the quantization-repetition signal."""
    words = _WORD_RE.findall(text.lower())
    seen: set[tuple[str, ...]] = set()
    for index in range(len(words) - 7):
        gram = tuple(words[index : index + 8])
        if gram in seen:
            return True
        seen.add(gram)
    return False


def repeated_8gram_rate(outputs: Iterable[str]) -> float:
    """Fraction of outputs containing a repeated 8-gram (0.0 for an empty batch)."""
    texts = list(outputs)
    if not texts:
        return 0.0
    return round(sum(1 for text in texts if has_repeated_8gram(text)) / len(texts), 4)


def distinct_ngram_ratio(text: str, n: int = 3) -> float:
    """Distinct/total n-gram ratio (prose diversity); 0.0 when the text is shorter than n."""
    words = _WORD_RE.findall(text.lower())
    grams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    if not grams:
        return 0.0
    return round(len(set(grams)) / len(grams), 4)


def _mean(values: Iterable[float]) -> float:
    items = [float(v) for v in values]
    return round(sum(items) / len(items), 4) if items else 0.0


def _report_score(case: ReportCase, arm: SamplingArm, seed: int, outcome: Any) -> dict:
    """E7/E9 report score row: D1, fact references, degeneracy and diversity."""
    prose = outcome.prose if outcome.schema_valid else None
    return {
        "case_id": case.case_id,
        "arm": arm.name,
        "seed": seed,
        "ok": outcome.ok,
        "schema_valid": outcome.schema_valid,
        "error": outcome.error,
        "d1_violations": outcome.d1_violations,
        "fact_refs": list(outcome.fact_refs),
        "has_repeated_8gram": has_repeated_8gram(prose) if prose else None,
        "distinct3_ratio": distinct_ngram_ratio(prose) if prose else None,
        "prompt_n": outcome.prompt_n,
        "predicted_n": outcome.predicted_n,
        "latency_ms": round(outcome.latency_ms, 1),
    }


def summarise_report_arm(scores: Sequence[dict], prose_by_case: dict[str, list[str]]) -> dict:
    """Per-arm E7/E9-report metrics: D1 rate, cross-seed similarity, degeneracy, latency."""
    valid = [s for s in scores if s.get("ok") and s.get("schema_valid")]
    flagged = [s for s in valid if (s.get("d1_violations") or 0) > 0]
    refs_by_case: dict[str, list[set[str]]] = {}
    for score in valid:
        refs_by_case.setdefault(score["case_id"], []).append(set(score["fact_refs"]))
    similarities = [cross_seed_similarity(sets) for sets in refs_by_case.values() if len(sets) >= 2]
    identical = [
        1.0 if len({p for p in texts}) == 1 else 0.0
        for texts in prose_by_case.values()
        if len(texts) >= 2
    ]
    return {
        "outputs": len(scores),
        "schema_valid": len(valid),
        "d1_violation_rate": round(len(flagged) / len(valid), 4) if valid else 0.0,
        "d1_total_violations": sum(int(s.get("d1_violations") or 0) for s in valid),
        "cross_seed_similarity": _mean(similarities),
        "cases_in_similarity": len(similarities),
        "identical_across_seeds_rate": _mean(identical),
        "repeated_8gram_rate": repeated_8gram_rate(
            p for texts in prose_by_case.values() for p in texts
        ),
        "distinct3_ratio_mean": _mean(
            float(s["distinct3_ratio"]) for s in valid if s.get("distinct3_ratio") is not None
        ),
        "mean_prompt_n": _mean(s["prompt_n"] for s in scores),
        "mean_predicted_n": _mean(s["predicted_n"] for s in scores),
        "mean_latency_ms": _mean(s["latency_ms"] for s in scores),
        "judge": "pending-j1 vs arm A (blind, paired)",
    }


async def run_e7(report_cases: Sequence[ReportCase], run_id: str, config: HarnessConfig) -> None:
    """E7: the report sampling sweep with cross-seed fact-reference similarity."""
    contexts = await erq.load_report_contexts(list(report_cases), run_id, SCRIPT)
    grid = expand_grid(report_cases, REPORT_ARMS, E7_SEEDS)
    print(
        f"E7: {len(report_cases)} cases x {len(REPORT_ARMS)} arms x {len(E7_SEEDS)} seeds "
        f"= {len(grid)} generations"
    )
    scores_by_arm: dict[str, list[dict]] = {arm.name: [] for arm in REPORT_ARMS}
    prose_by_arm: dict[str, dict[str, list[str]]] = {arm.name: {} for arm in REPORT_ARMS}
    pairs: list[dict] = []
    keys: list[dict] = []

    for case, arm, seed in grid:
        outcome = erq.generate_one_report(
            contexts[case.case_id],
            experiment=E7,
            arm=arm.name,
            seed=seed,
            config=config,
            temperature=arm.temperature,
            top_p=arm.top_p,
            top_k=arm.top_k,
            presence_penalty=arm.presence_penalty,
            script=SCRIPT,
        )
        score = _report_score(case, arm, seed, outcome)
        scores_by_arm[arm.name].append(score)
        record(E7, {"experiment": E7, "kind": "score", **score})
        if outcome.schema_valid and outcome.prose is not None:
            prose_by_arm[arm.name].setdefault(case.case_id, []).append(outcome.prose)

    # Blind prose-quality pairs: each arm's first output vs arm A's, order randomised.
    for arm in REPORT_ARMS[1:]:
        for case in report_cases:
            arm_texts = prose_by_arm[arm.name].get(case.case_id) or []
            a_texts = prose_by_arm["A"].get(case.case_id) or []
            if not arm_texts or not a_texts:
                continue
            blinded, key = erq.blind_pair(
                random.Random(f"e7:{case.case_id}:{arm.name}"),
                {"A_seed": a_texts[0], "arm_text": arm_texts[0]},
            )
            pairs.append({"case_id": case.case_id, "arm": arm.name, "blinded": blinded})
            keys.append({"case_id": case.case_id, "arm": arm.name, "key": key})
    out = output_dir()
    (out / "e7_j1_pairs.json").write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "e7_j1_key.json").write_text(
        json.dumps(keys, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    for arm in REPORT_ARMS:
        summary = summarise_report_arm(scores_by_arm[arm.name], prose_by_arm[arm.name])
        record(
            E7,
            {
                "experiment": E7,
                "kind": "summary",
                "arm": arm.name,
                "params": {
                    "temperature": arm.temperature,
                    "top_p": arm.top_p,
                    "top_k": arm.top_k,
                    "presence_penalty": arm.presence_penalty,
                },
                **summary,
            },
        )
        print(
            f"E7 arm {arm.name}: D1 rate {summary['d1_violation_rate']}, cross-seed "
            f"similarity {summary['cross_seed_similarity']}, repeated-8gram "
            f"{summary['repeated_8gram_rate']}, mean latency "
            f"{summary['mean_latency_ms']} ms"
        )
    print(
        "E7 decision: pick an arm with zero D1 and the highest cross-seed similarity, "
        "unless a lower-temperature arm loses J1 prose by >1 point"
    )


def _chat_score(case: ChatCase, arm: SamplingArm, seed: int, outcome: Any) -> dict:
    """E8/E9-chat score row: the E4 bundle fields plus answer degeneracy/diversity."""
    base = etc.score_case(case, outcome)
    answer = outcome.final_answer
    return {
        **base,
        "arm": arm.name,
        "seed": seed,
        "answer_has_repeated_8gram": has_repeated_8gram(answer) if answer else None,
        "answer_distinct3_ratio": distinct_ngram_ratio(answer) if answer else None,
        "answer_d1_violations": (
            etc.chat_d1_violations(answer, etc.allowed_from_payloads(outcome.payloads))
            if outcome.ok and outcome.payloads
            else None
        ),
    }


def summarise_chat_arm(scores: Sequence[dict]) -> dict:
    """Per-arm E8 metrics: pooled argument exact-match plus error magnitude on failures."""
    aggregate = etc.aggregate_scores(scores)
    failures = [
        s for s in scores if s.get("ok") and s.get("answerable") and not s.get("args_exact")
    ]
    by_code: dict[str, int] = {}
    for failure in failures:
        code = str(failure.get("error_code", "unknown"))
        by_code[code] = by_code.get(code, 0) + 1
    return {
        **aggregate,
        "argument_failures": len(failures),
        "mean_error_magnitude": _mean(
            etc.ERROR_MAGNITUDE[str(s.get("error_code", "unknown"))] for s in failures
        )
        if failures
        else 0.0,
        "error_codes": by_code,
    }


async def run_e8(chat_cases: Sequence[ChatCase], run_id: str, config: HarnessConfig) -> None:
    """E8: the chat sampling sweep scored on argument exact-match and error magnitude."""
    grid = expand_grid(chat_cases, CHAT_ARMS, E8_SEEDS)
    print(
        f"E8: {len(chat_cases)} cases x {len(CHAT_ARMS)} arms x {len(E8_SEEDS)} seeds "
        f"= {len(grid)} tool-loop runs"
    )
    scores_by_arm: dict[str, list[dict]] = {arm.name: [] for arm in CHAT_ARMS}
    aconn = await etc.connect_readonly_async(SCRIPT)
    try:
        for case, arm, seed in grid:
            outcome = await etc.run_chat_case(
                case.case_id,
                case.question,
                aconn=aconn,
                run_id=run_id,
                seed=seed,
                experiment=E8,
                arm=arm.name,
                config=config,
            )
            score = _chat_score(case, arm, seed, outcome)
            scores_by_arm[arm.name].append(score)
            record(E8, {"experiment": E8, "kind": "score", **score})
    finally:
        await aconn.close()
    for arm in CHAT_ARMS:
        summary = summarise_chat_arm(scores_by_arm[arm.name])
        record(
            E8,
            {
                "experiment": E8,
                "kind": "summary",
                "arm": arm.name,
                "params": {
                    "temperature": arm.temperature,
                    "top_p": arm.top_p,
                    "top_k": arm.top_k,
                    "presence_penalty": arm.presence_penalty,
                },
                **summary,
            },
        )
        print(
            f"E8 arm {arm.name}: argument exact-match "
            f"{summary['argument_exact_match']}, no-call {summary['no_call_rate']}, "
            f"mean error magnitude {summary['mean_error_magnitude']}, failures "
            f"{summary['argument_failures']}"
        )
    print("E8 decision: highest argument exact-match wins, tie broken toward lower temperature")


async def run_e9(
    chat_cases: Sequence[ChatCase],
    report_cases: Sequence[ReportCase],
    run_id: str,
    config: HarnessConfig,
) -> None:
    """E9: presence_penalty 0.0 vs 1.5 on both case sets; repeat_penalty never set."""
    contexts = await erq.load_report_contexts(list(report_cases), run_id, SCRIPT)
    report_grid = expand_grid(report_cases, E9_ARMS, E9_SEEDS)
    chat_grid = expand_grid(chat_cases, E9_ARMS, E9_SEEDS)
    print(
        f"E9: report {len(report_grid)} + chat {len(chat_grid)} = "
        f"{len(report_grid) + len(chat_grid)} generations (presence_penalty only; "
        "repeat_penalty is never enabled)"
    )

    report_scores: dict[str, list[dict]] = {arm.name: [] for arm in E9_ARMS}
    report_prose: dict[str, dict[str, list[str]]] = {arm.name: {} for arm in E9_ARMS}
    for case, arm, seed in report_grid:
        outcome = erq.generate_one_report(
            contexts[case.case_id],
            experiment=E9,
            arm=arm.name,
            seed=seed,
            config=config,
            temperature=arm.temperature,
            top_p=arm.top_p,
            top_k=arm.top_k,
            presence_penalty=arm.presence_penalty,
            script=SCRIPT,
        )
        score = _report_score(case, arm, seed, outcome)
        report_scores[arm.name].append(score)
        record(E9, {"experiment": E9, "kind": "score", "path": "report", **score})
        if outcome.schema_valid and outcome.prose is not None:
            report_prose[arm.name].setdefault(case.case_id, []).append(outcome.prose)

    chat_scores: dict[str, list[dict]] = {arm.name: [] for arm in E9_ARMS}
    aconn = await etc.connect_readonly_async(SCRIPT)
    try:
        for case, arm, seed in chat_grid:
            outcome = await etc.run_chat_case(
                case.case_id,
                case.question,
                aconn=aconn,
                run_id=run_id,
                seed=seed,
                experiment=E9,
                arm=arm.name,
                config=config,
            )
            score = _chat_score(case, arm, seed, outcome)
            chat_scores[arm.name].append(score)
            record(E9, {"experiment": E9, "kind": "score", "path": "chat", **score})
    finally:
        await aconn.close()

    for arm in E9_ARMS:
        report_summary = summarise_report_arm(report_scores[arm.name], report_prose[arm.name])
        record(
            E9,
            {
                "experiment": E9,
                "kind": "summary",
                "arm": arm.name,
                "path": "report",
                "presence_penalty": arm.presence_penalty,
                **report_summary,
            },
        )
        chat_summary = summarise_chat_arm(chat_scores[arm.name])
        answers = [s for s in chat_scores[arm.name] if s.get("answer_distinct3_ratio") is not None]
        record(
            E9,
            {
                "experiment": E9,
                "kind": "summary",
                "arm": arm.name,
                "path": "chat",
                "presence_penalty": arm.presence_penalty,
                **chat_summary,
                "repeated_8gram_rate": repeated_8gram_rate_text_fields(chat_scores[arm.name]),
                "distinct3_ratio_mean": _mean(float(s["answer_distinct3_ratio"]) for s in answers),
                "answer_d1_total": sum(
                    int(s["answer_d1_violations"])
                    for s in chat_scores[arm.name]
                    if s.get("answer_d1_violations") is not None
                ),
                "judge": "pending-j1",
            },
        )
        print(
            f"E9 arm {arm.name} (presence_penalty {arm.presence_penalty}): report D1 rate "
            f"{report_summary['d1_violation_rate']}, chat exact-match "
            f"{chat_summary['argument_exact_match']}"
        )
    print(
        "E9 decision: adopt presence_penalty=1.5 only if D1 stays 0 and degeneracy "
        "improves; repeat_penalty stays off forever on the report path"
    )


def repeated_8gram_rate_text_fields(scores: Sequence[dict]) -> float:
    """Repeated-8-gram rate over chat answers recorded in score rows (None-safe)."""
    answers = [
        s["answer_has_repeated_8gram"]
        for s in scores
        if s.get("answer_has_repeated_8gram") is not None
    ]
    if not answers:
        return 0.0
    return round(sum(1 for flag in answers if flag) / len(answers), 4)


def main() -> None:
    """Run the E7/E8/E9 sampling sweeps (one per run — they are the expensive experiments).

    `--help` prints this text without contacting a server, the database, or the backend.
    The script prefights the inference server first: with no server it exits with one
    actionable line and sends nothing. Seeds are the plan's fixed sets (E7: 101/202/303,
    E8: 101/202, E9: 101) so runs are comparable.
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--experiment",
        choices=(E7, E8, E9, "all"),
        default=DEFAULT_EXPERIMENT,
        help="which sweep to run (default: %(default)s)",
    )
    args = parser.parse_args()

    config = load_config()
    preflight()
    wanted = {E7, E8, E9} if args.experiment == "all" else {args.experiment}
    with connect_readonly(SCRIPT) as conn:
        run_id = active_run_id(conn, SCRIPT)
    if E7 in wanted or E9 in wanted:
        report_cases = resolve_report_cases(script=SCRIPT)
    else:
        report_cases = []
    if E8 in wanted or E9 in wanted:
        chat_cases = resolve_cases(script=SCRIPT)
    else:
        chat_cases = []

    if E7 in wanted:
        asyncio.run(run_e7(report_cases, run_id, config))
    if E8 in wanted:
        asyncio.run(run_e8(chat_cases, run_id, config))
    if E9 in wanted:
        if not report_cases or not chat_cases:
            fail("E9 needs both case sets", script=SCRIPT)
        asyncio.run(run_e9(chat_cases, report_cases, run_id, config))


if __name__ == "__main__":
    main()
