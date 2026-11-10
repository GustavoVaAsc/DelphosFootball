"""E4–E6: tool calling, thinking on/off, and multi-turn conversation (LLM_PLAN §17.3).

Input: the 20 resolved chat cases (`cases_chat`), the first six report cases as E6
conversation players, the shipped chat stack imported from `backend/src`
(`chat_prompt.SYSTEM_PROMPT`, `chat_agent.build_messages` / `parse_tool_call` /
`FALLBACK_ANSWER`, `chat_tools.execute_tool` over read-only `analytics`), and the
inference server through `harness`.
Output: `e4.jsonl`, `e5.jsonl`, `e6.jsonl` call/score/summary rows under
`analysis/output/llm/`, plus printed decision-rule readouts.
Responsibility: drive the shipped tool-loop protocol with a seeded request and score it
deterministically — E4 (tool selection, argument exact-match, no-call rate, refusal
accuracy, loop exhaustion, call count), E5 (three thinking arms: per-request template
off/on and, only with `--reasoning-off`, the server-level switch after a llama-server
restart), and E6 (six scripted 5-turn conversations with a correction and an
unanswerable turn).

The loop mirrors `chat_agent.stream_chat_turn` exactly (same message format, same
4-iteration cap, same fallback answer) so the experiment measures the shipped
conversation, not a reimplementation; the only differences are the explicit seed and
the per-call JSONL recording. Semantic judgements (context use, correction handling,
consistency, drift) are recorded as `pending-j1`; the deterministic residue — D1 on
every turn, retracted-value mentions, refusal and not-found markers, latencies and
context growth — is computed here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import exp_report_quality as erq
from cases_chat import (
    OUTCOME_REFUSAL,
    OUTCOME_TOOL_CALL,
    ChatCase,
    resolve_cases,
)
from cases_report import ReportCase, resolve_report_cases
from harness import (
    HarnessConfig,
    HarnessError,
    active_run_id,
    backend_import,
    build_request,
    build_row,
    call_server,
    connect_readonly,
    connect_readonly_async,
    load_config,
    preflight,
    record,
)

SCRIPT = "exp_tool_calling"
E4, E5, E6 = "e4", "e5", "e6"
DEFAULT_SEED = 101
N_CONVERSATIONS = 6
TURNS_PER_CONVERSATION = 5

REFUSAL_MARKERS: tuple[str, ...] = (
    "no puedo",
    "no pue",
    "no dispongo",
    "no cuento con",
    "no tengo acceso",
    "no tengo esa",
    "no tengo información",
    "no se puede responder",
    "no corresponde",
    "no está en",
    "no se encuentra",
    "no figura",
    "fuera de",
    "las herramientas no",
    "el conjunto de datos no",
    "no puedo responder",
)
NOT_FOUND_MARKERS: tuple[str, ...] = (
    "no encont",
    "no se encont",
    "no existe",
    "no figura",
    "ningún",
    "ningun",
    "no hay datos",
    "no se hall",
    "no están",
    "no estan",
)

ERROR_MAGNITUDE: dict[str, int] = {
    "none": 0,
    "missing_arg": 1,
    "extra_arg": 1,
    "wrong_value": 2,
    "wrong_enum_value": 2,
    "wrong_cluster_id": 3,
    "sequence_mismatch": 3,
    "wrong_league_id": 4,
    "wrong_player_id": 5,
    "wrong_tool": 6,
    "no_call": 6,
    "not_applicable": 0,
}
"""E8's error scale: a wrong league (4) is a different bug than a wrong player (5)."""

RETRACTED_VALUES: tuple[str, ...] = (
    "€999.0M",
    "€888.0M",
    "€777.0M",
    "€666.0M",
    "€555.0M",
    "€444.0M",
)
"""Fictional market values E6 turn 2 asserts and turn 3 retracts (never in the data)."""


@dataclass(frozen=True)
class ThinkingArm:
    """One E5 condition: a per-request template flag, or the server-level switch."""

    name: str
    enable_thinking: bool


def e5_arms(reasoning_off: bool = False) -> list[ThinkingArm]:
    """The three §17.3 arms; the third exists only when the operator restarted the server.

    T-off and T-on are the per-request Jinja variable. T-on-reasoning-off sends
    `enable_thinking=true` against a llama-server started with `--reasoning off`, so the
    comparison isolates whether the server flag and the template flag are the same
    switch — and it can only run after that restart.
    """
    arms = [ThinkingArm("t_off", False), ThinkingArm("t_on", True)]
    if reasoning_off:
        arms.append(ThinkingArm("t_server_reasoning_off", True))
    return arms


@dataclass
class ChatOutcome:
    """One chat case run: the calls, the answer, and the server's per-call accounting."""

    case_id: str
    arm: str
    seed: int
    ok: bool = True
    error: str | None = None
    final_answer: str = ""
    calls: list[dict[str, Any]] = field(default_factory=list)
    payloads: list[str] = field(default_factory=list)
    first_parsed: bool = False
    exhausted: bool = False
    prompt_ns: list[int] = field(default_factory=list)
    completion_tokens: list[int] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)


def expected_calls(case: ChatCase) -> list[dict[str, Any]]:
    """The exact call sequence a case expects (resolved player_ids included)."""
    sequence: list[dict[str, Any]] = []
    if case.expected_tool is not None:
        sequence.append({"tool": case.expected_tool, "arguments": case.expected_args or {}})
    if case.next_tool is not None:
        sequence.append({"tool": case.next_tool, "arguments": case.next_args or {}})
    return sequence


def arguments_match(expected: Mapping[str, Any], actual: Mapping[str, Any] | None) -> bool:
    """Argument exact-match: every argument equal, no extras, nothing missing."""
    return dict(expected) == dict(actual or {})


def _args_error(expected: Mapping[str, Any], actual: Mapping[str, Any] | None) -> str | None:
    actual = dict(actual or {})
    for key, want in expected.items():
        if key not in actual:
            return "missing_arg"
        if actual[key] != want:
            if key == "player_id":
                return "wrong_player_id"
            if key == "league_id":
                return "wrong_league_id"
            if key == "cluster_id":
                return "wrong_cluster_id"
            if key in ("position", "valuation_status"):
                return "wrong_enum_value"
            return "wrong_value"
    for key in actual:
        if key not in expected:
            return "extra_arg"
    return None


def classify_call_error(
    expected: Sequence[Mapping[str, Any]], actual: Sequence[Mapping[str, Any]]
) -> str:
    """The most specific failure code for a call sequence (E8's error magnitude)."""
    if not expected:
        return "not_applicable"
    if not actual:
        return "no_call"
    for index, want in enumerate(expected):
        if index >= len(actual):
            return "sequence_mismatch"
        got = actual[index]
        if got["tool"] != want["tool"]:
            return "wrong_tool"
        if (code := _args_error(want.get("arguments") or {}, got.get("arguments"))) is not None:
            return code
    if len(actual) != len(expected):
        return "sequence_mismatch"
    return "none"


def is_refusal(answer: str) -> bool:
    """True when the answer declines instead of answering (heuristic, Spanish markers)."""
    lowered = answer.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def is_honest_not_found(answer: str) -> bool:
    """True when the answer reports an empty result honestly (case 20's requirement)."""
    lowered = answer.lower()
    return any(marker in lowered for marker in NOT_FOUND_MARKERS)


def score_case(case: ChatCase, outcome: ChatOutcome) -> dict[str, Any]:
    """Deterministic per-case score for E4/E5/E8: one flat dict, recorded as a score row."""
    score: dict[str, Any] = {
        "case_id": case.case_id,
        "ok": outcome.ok,
        "answerable": case.outcome == OUTCOME_TOOL_CALL,
        "call_count": len(outcome.calls),
        "exhausted": outcome.exhausted,
        "first_parsed": outcome.first_parsed,
        "first_completion_tokens": (
            outcome.completion_tokens[0] if outcome.completion_tokens else 0
        ),
        "first_latency_ms": outcome.latencies_ms[0] if outcome.latencies_ms else 0.0,
        "total_latency_ms": round(sum(outcome.latencies_ms), 1),
    }
    if outcome.error:
        score["error"] = outcome.error
        return score
    if case.outcome == OUTCOME_TOOL_CALL:
        expected = expected_calls(case)
        first = outcome.calls[0] if outcome.calls else None
        score["tool_selection_ok"] = first is not None and first["tool"] == expected[0]["tool"]
        score["args_exact"] = (
            classify_call_error(expected, [dict(c) for c in outcome.calls]) == "none"
        )
        score["no_call"] = first is None
        score["error_code"] = classify_call_error(expected, [dict(c) for c in outcome.calls])
        score["error_magnitude"] = ERROR_MAGNITUDE[score["error_code"]]
    elif case.outcome == OUTCOME_REFUSAL:
        score["refusal_ok"] = not outcome.calls and is_refusal(outcome.final_answer)
    else:
        score["not_found_ok"] = is_honest_not_found(outcome.final_answer)
    return score


def aggregate_scores(scores: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """The §17.3 metric bundle over per-case scores (failed cases leave the denominators)."""
    rows = [dict(s) for s in scores]
    usable = [s for s in rows if s.get("ok")]
    answerable = [s for s in usable if s.get("answerable")]
    refusals = [s for s in usable if "refusal_ok" in s]
    not_found = [s for s in usable if "not_found_ok" in s]

    def rate(count: int, total: int) -> float:
        return round(count / total, 4) if total else 0.0

    def count_of(key: str, rows: Sequence[Mapping[str, Any]]) -> int:
        return sum(1 for s in rows if s.get(key))

    return {
        "cases_scored": len(usable),
        "cases_failed": len(rows) - len(usable),
        "tool_selection_accuracy": rate(count_of("tool_selection_ok", answerable), len(answerable)),
        "argument_exact_match": rate(count_of("args_exact", answerable), len(answerable)),
        "no_call_rate": rate(count_of("no_call", answerable), len(answerable)),
        "refusal_accuracy": rate(count_of("refusal_ok", refusals), len(refusals)),
        "not_found_accuracy": rate(count_of("not_found_ok", not_found), len(not_found)),
        "loop_exhaustion_rate": rate(count_of("exhausted", usable), len(usable)),
        "mean_call_count": (
            round(sum(int(s.get("call_count", 0)) for s in answerable) / len(answerable), 4)
            if answerable
            else 0.0
        ),
    }


def allowed_from_payloads(payloads: Iterable[str]) -> set[str]:
    """Every canonical number present in the tool payloads seen so far (chat D1 scope)."""
    verify = backend_import("delphos_backend.services.report_verify", SCRIPT)
    allowed: set[str] = set()
    for payload in payloads:
        for token in verify.extract_number_tokens(payload):
            canonical = verify.canonicalize_number(token.token)
            if canonical is not None:
                allowed.add(canonical)
    return allowed


def chat_d1_violations(answer: str, allowed: set[str]) -> int:
    """Numbers in a chat answer that no tool payload grounds (drift, deterministic)."""
    verify = backend_import("delphos_backend.services.report_verify", SCRIPT)
    return len(verify.verify_prose_numbers(answer, allowed).violations)


def _chat_settings() -> SimpleNamespace:
    """Loop settings under the §13 env names (mirrors chat_agent's Settings fields)."""

    def env_int(name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None or raw == "":
            return default
        try:
            return int(raw)
        except ValueError as exc:
            raise HarnessError(f"{name}={raw!r} is not an integer") from exc

    return SimpleNamespace(
        llm_chat_history_turns=env_int("DELPHOS_LLM_CHAT_HISTORY_TURNS", 8),
        llm_max_tool_iterations=env_int("DELPHOS_LLM_MAX_TOOL_ITERATIONS", 4),
    )


async def run_chat_case(
    case_id: str,
    question: str,
    *,
    aconn: Any,
    run_id: str,
    seed: int,
    experiment: str,
    arm: str,
    config: HarnessConfig,
    enable_thinking: bool | None = None,
    history: list[dict[str, Any]] | None = None,
) -> ChatOutcome:
    """One chat case through the shipped loop protocol; records one JSONL row per call.

    Mirrors `chat_agent.stream_chat_turn`: build_messages + capped iterations + the
    «tool» result message, executed by the shipped `chat_tools.execute_tool`. A server
    failure is recorded and returned, never raised, so one bad case cannot abort a run.
    """
    chat_agent = backend_import("delphos_backend.services.chat_agent", SCRIPT)
    chat_tools = backend_import("delphos_backend.services.chat_tools", SCRIPT)
    settings = _chat_settings()
    max_iterations = settings.llm_max_tool_iterations
    messages = chat_agent.build_messages(question, history or [], settings)
    outcome = ChatOutcome(case_id=case_id, arm=arm, seed=seed)

    for iteration in range(max_iterations + 1):
        request = build_request(messages, seed=seed, config=config, enable_thinking=enable_thinking)
        started = time.perf_counter()
        try:
            result = call_server(request, config=config)
        except HarnessError as exc:
            record(
                experiment,
                {
                    "ts": erq.now_iso(),
                    "experiment": experiment,
                    "kind": "call",
                    "case_id": case_id,
                    "arm": arm,
                    "seed": seed,
                    "iteration": iteration,
                    "error": str(exc),
                },
            )
            outcome.ok = False
            outcome.error = str(exc)
            return outcome
        latency_ms = (time.perf_counter() - started) * 1000.0
        prompt_n, predicted_n = erq.timings_of(result)
        call = chat_agent.parse_tool_call(result.content)
        if iteration == 0:
            outcome.first_parsed = call is not None
        outcome.prompt_ns.append(prompt_n)
        outcome.completion_tokens.append(predicted_n)
        outcome.latencies_ms.append(round(latency_ms, 1))
        record(
            experiment,
            build_row(
                request,
                result,
                experiment=experiment,
                case_id=case_id,
                extra={
                    "kind": "call",
                    "arm": arm,
                    "iteration": iteration,
                    "latency_ms": round(latency_ms, 1),
                    "parsed_tool_call": call is not None,
                    "tool": call.get("tool") if isinstance(call, dict) else None,
                    "prompt_n": prompt_n,
                    "predicted_n": predicted_n,
                },
            ),
        )
        if call is None:
            outcome.final_answer = result.content.strip()
            return outcome
        tool_name = call.get("tool")
        arguments = call.get("arguments") or {}
        outcome.calls.append({"tool": tool_name, "arguments": arguments, "iteration": iteration})
        messages.append({"role": "assistant", "content": result.content.strip()})
        if iteration >= max_iterations:
            outcome.exhausted = True
            outcome.final_answer = chat_agent.FALLBACK_ANSWER
            return outcome
        payload = await chat_tools.execute_tool(aconn, run_id, tool_name, arguments)
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        outcome.payloads.append(serialized)
        messages.append(
            {
                "role": "user",
                "content": f"Resultado de la herramienta «{tool_name}»:\n{serialized}",
            }
        )
    return outcome  # pragma: no cover — the loop always returns on its final iteration


async def run_e4(cases: Sequence[ChatCase], run_id: str, seed: int, config: HarnessConfig) -> None:
    """E4: one default-arm run over the 20 cases and the §17.3 metric bundle."""
    scores: list[dict[str, Any]] = []
    aconn = await connect_readonly_async(SCRIPT)
    try:
        for case in cases:
            outcome = await run_chat_case(
                case.case_id,
                case.question,
                aconn=aconn,
                run_id=run_id,
                seed=seed,
                experiment=E4,
                arm="default",
                config=config,
            )
            score = score_case(case, outcome)
            scores.append(score)
            record(E4, {"experiment": E4, "kind": "score", "arm": "default", "seed": seed, **score})
    finally:
        await aconn.close()
    aggregate = aggregate_scores(scores)
    record(E4, {"experiment": E4, "kind": "summary", "arm": "default", "seed": seed, **aggregate})
    _print_e4_readout(aggregate, len(cases))


def _print_e4_readout(aggregate: Mapping[str, Any], n_cases: int) -> None:
    print(f"E4 over {n_cases} cases:")
    for key in (
        "tool_selection_accuracy",
        "argument_exact_match",
        "no_call_rate",
        "refusal_accuracy",
        "loop_exhaustion_rate",
        "mean_call_count",
    ):
        print(f"  {key}: {aggregate[key]}")
    shipped = (
        aggregate["argument_exact_match"] >= 0.80
        and aggregate["no_call_rate"] == 0.0
        and aggregate["refusal_accuracy"] == 1.0
    )
    print(
        f"  decision rule (exact>=0.80, no-call=0, refusal=1.0): "
        f"{'PASS' if shipped else 'FAIL'} (chat ships only on PASS)"
    )


async def run_e5(
    chat_cases: Sequence[ChatCase],
    report_cases: Sequence[ReportCase],
    run_id: str,
    seed: int,
    config: HarnessConfig,
    arms: Sequence[ThinkingArm],
    chat_only: bool,
) -> None:
    """E5: every case under every thinking arm, chat first, then the report path."""
    aconn = await connect_readonly_async(SCRIPT)
    try:
        for arm in arms:
            scores: list[dict[str, Any]] = []
            for case in chat_cases:
                outcome = await run_chat_case(
                    case.case_id,
                    case.question,
                    aconn=aconn,
                    run_id=run_id,
                    seed=seed,
                    experiment=E5,
                    arm=arm.name,
                    config=config,
                    enable_thinking=arm.enable_thinking,
                )
                score = score_case(case, outcome)
                scores.append(score)
                record(
                    E5, {"experiment": E5, "kind": "score", "arm": arm.name, "seed": seed, **score}
                )
            aggregate = aggregate_scores(scores)
            answerable = [s for s in scores if s.get("ok") and s.get("answerable")]
            parse_rate = (
                round(sum(1 for s in answerable if s.get("first_parsed")) / len(answerable), 4)
                if answerable
                else 0.0
            )
            ok_scores = [s for s in scores if s.get("ok")]
            summary = {
                **aggregate,
                "tool_call_parse_rate": parse_rate,
                "mean_first_completion_tokens": (
                    round(
                        sum(float(s.get("first_completion_tokens", 0)) for s in ok_scores)
                        / max(len(ok_scores), 1),
                        1,
                    )
                ),
                "mean_first_latency_ms": (
                    round(
                        sum(float(s.get("first_latency_ms", 0.0)) for s in ok_scores)
                        / max(len(ok_scores), 1),
                        1,
                    )
                ),
            }
            record(
                E5,
                {
                    "experiment": E5,
                    "kind": "summary",
                    "arm": arm.name,
                    "seed": seed,
                    "path": "chat",
                    **summary,
                },
            )
            print(
                f"E5 chat arm {arm.name}: argument_exact_match "
                f"{aggregate['argument_exact_match']}, no_call_rate "
                f"{aggregate['no_call_rate']}, parse_rate {parse_rate}, "
                f"mean first completion {summary['mean_first_completion_tokens']} tok, "
                f"mean first latency {summary['mean_first_latency_ms']} ms"
            )
    finally:
        await aconn.close()

    if not chat_only and report_cases:
        contexts = await erq.load_report_contexts(list(report_cases), run_id, SCRIPT)
        for arm in arms:
            outcomes = [
                erq.generate_one_report(
                    contexts[case.case_id],
                    experiment=E5,
                    arm=arm.name,
                    seed=seed,
                    config=config,
                    enable_thinking=arm.enable_thinking,
                    script=SCRIPT,
                )
                for case in report_cases
            ]
            valid = [o for o in outcomes if o.ok and o.schema_valid]
            summary = {
                "reports": len(outcomes),
                "schema_valid": len(valid),
                "d1_total_violations": sum(int(o.d1_violations or 0) for o in valid),
                "mean_latency_ms": round(
                    sum(o.latency_ms for o in outcomes) / max(len(outcomes), 1), 1
                ),
                "mean_prompt_n": round(
                    sum(o.prompt_n for o in outcomes) / max(len(outcomes), 1), 1
                ),
                "judge": "pending-j1",
            }
            record(
                E5,
                {
                    "experiment": E5,
                    "kind": "summary",
                    "arm": arm.name,
                    "seed": seed,
                    "path": "report",
                    **summary,
                },
            )
            print(
                f"E5 report arm {arm.name}: D1 total {summary['d1_total_violations']}, "
                f"mean latency {summary['mean_latency_ms']} ms (J1 pending)"
            )


def _print_reasoning_off_skip() -> None:
    """The third arm is a separate server run: say so loudly, never skip silently."""
    reason = (
        "the t_server_reasoning_off arm needs llama-server restarted with --reasoning off "
        "(LLM_PLAN §17.3: a separate server run). Re-run with --reasoning-off after that "
        "restart; the two per-request arms run now."
    )
    print(f"E5: third arm t_server_reasoning_off NOT RUN — {reason}")
    record(
        E5,
        {
            "experiment": E5,
            "kind": "summary",
            "arm": "t_server_reasoning_off",
            "status": "not-run",
            "reason": reason,
        },
    )


def conversations(cases: Sequence[ReportCase]) -> list[dict[str, Any]]:
    """The six scripted 5-turn conversations (§17.3 E6): one player, one retraction each."""
    convs = []
    for case, retracted in zip(list(cases)[:N_CONVERSATIONS], RETRACTED_VALUES, strict=False):
        name = case.player_name
        convs.append(
            {
                "conversation_id": f"conv_{case.case_id}",
                "player_name": name,
                "retracted": retracted,
                "turns": [
                    f"¿Quién es {name}?",
                    f"Me han dicho que {name} cotiza a {retracted}. ¿Es correcto?",
                    f"Corrijo: {retracted} era un error mío, descártalo.",
                    "Entonces, ¿cuál es su valor de mercado actual?",
                    "¿Cuánto gana al año este jugador?",
                ],
            }
        )
    return convs


async def run_e6(
    report_cases: Sequence[ReportCase], run_id: str, seed: int, config: HarnessConfig
) -> None:
    """E6: six 5-turn conversations; deterministic turn scores, semantic axes pending."""
    convs = conversations(report_cases)
    aconn = await connect_readonly_async(SCRIPT)
    turn_scores: list[dict[str, Any]] = []
    try:
        for conv in convs:
            history: list[dict[str, Any]] = []
            allowed: set[str] = set()
            retracted = conv["retracted"]
            previous_prompt_n = 0
            for index, question in enumerate(conv["turns"], start=1):
                outcome = await run_chat_case(
                    f"{conv['conversation_id']}_t{index}",
                    question,
                    aconn=aconn,
                    run_id=run_id,
                    seed=seed,
                    experiment=E6,
                    arm="default",
                    config=config,
                    history=history,
                )
                allowed |= allowed_from_payloads(outcome.payloads)
                answer = outcome.final_answer
                latency = sum(outcome.latencies_ms)
                prompt_n = outcome.prompt_ns[-1] if outcome.prompt_ns else previous_prompt_n
                context_growth = max(prompt_n - previous_prompt_n, 0)
                previous_prompt_n = prompt_n
                turn = {
                    "conversation_id": conv["conversation_id"],
                    "turn": index,
                    "ok": outcome.ok,
                    "d1_violations": chat_d1_violations(answer, allowed),
                    "retracted_mentioned": retracted in answer,
                    "is_refusal": is_refusal(answer),
                    "has_number": any(ch.isdigit() for ch in answer),
                    "latency_ms": round(latency, 1),
                    "prompt_n": prompt_n,
                    "context_growth_tokens": context_growth,
                    "context_use": "pending-j1",
                    "correction_handling": "pending-j1",
                    "consistency": "pending-j1",
                }
                turn_scores.append(turn)
                record(
                    E6, {"experiment": E6, "kind": "score", "arm": "default", "seed": seed, **turn}
                )
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": answer})
    finally:
        await aconn.close()

    ok_turns = [t for t in turn_scores if t["ok"]]
    unanswerable = [
        t
        for t in ok_turns
        if t["turn"] == TURNS_PER_CONVERSATION and (t["is_refusal"] or not t["has_number"])
    ]
    n_unans = sum(1 for t in ok_turns if t["turn"] == TURNS_PER_CONVERSATION)
    summary = {
        "conversations": len(convs),
        "turns": len(turn_scores),
        "turns_ok": len(ok_turns),
        "total_d1_violations": sum(int(t["d1_violations"]) for t in ok_turns),
        "retracted_mentions_after_correction": sum(
            1 for t in ok_turns if t["turn"] >= 4 and t["retracted_mentioned"]
        ),
        "unanswerable_ok": f"{len(unanswerable)}/{n_unans}",
        "mean_latency_per_turn_ms": round(
            sum(float(t["latency_ms"]) for t in ok_turns) / max(len(ok_turns), 1), 1
        ),
        "mean_context_growth_tokens": round(
            sum(int(t["context_growth_tokens"]) for t in ok_turns) / max(len(ok_turns), 1), 1
        ),
        "semantic_axes": "pending-j1 (context use, correction handling, consistency)",
        "stream_ship_rule": "no-drift (D1 total must be 0 across all turns)",
    }
    record(E6, {"experiment": E6, "kind": "summary", "arm": "default", "seed": seed, **summary})
    print(
        f"E6: {summary['conversations']} conversations, D1 total "
        f"{summary['total_d1_violations']} (must be 0), retracted mentions after "
        f"correction {summary['retracted_mentions_after_correction']}, unanswerable "
        f"{summary['unanswerable_ok']}; semantic axes pending J1"
    )


def main() -> None:
    """Run E4 (tool calling), E5 (three thinking arms), or E6 (multi-turn chat).

    `--help` prints this text without contacting a server, the database, or the backend.
    The script prefights the inference server before anything else: with no server it
    exits with one actionable line. E5's third arm additionally needs
    `--reasoning-off` after a llama-server restart; without it the arm is announced as
    NOT RUN rather than omitted silently.
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--experiment",
        choices=(E4, E5, E6),
        default=E4,
        help="which experiment to run (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="explicit seed for every request (default: %(default)s)",
    )
    parser.add_argument(
        "--reasoning-off",
        action="store_true",
        help="E5 only: include the third arm (server restarted with --reasoning off)",
    )
    parser.add_argument(
        "--chat-only", action="store_true", help="E5 only: skip the report-path three-arm pass"
    )
    args = parser.parse_args()

    config = load_config()
    preflight()
    cases = resolve_cases(script=SCRIPT)
    with connect_readonly(SCRIPT) as conn:
        run_id = active_run_id(conn, SCRIPT)

    if args.experiment == E4:
        print(f"E4: 20 cases x 1 arm x seed {args.seed} = 20 tool-loop runs")
        asyncio.run(run_e4(cases, run_id, args.seed, config))
    elif args.experiment == E5:
        arms = e5_arms(args.reasoning_off)
        report_cases: list[ReportCase] = []
        if not args.chat_only:
            report_cases = resolve_report_cases(script=SCRIPT)
        n_chat = len(cases) * len(arms)
        n_report = 0 if args.chat_only else len(report_cases) * len(arms)
        print(
            f"E5: {len(cases)} chat cases x {len(arms)} arms = {n_chat} chat runs, "
            f"{n_report} report runs (seed {args.seed})"
        )
        if not args.reasoning_off:
            _print_reasoning_off_skip()
        asyncio.run(run_e5(cases, report_cases, run_id, args.seed, config, arms, args.chat_only))
    else:
        report_cases = resolve_report_cases(script=SCRIPT)
        print(
            f"E6: {N_CONVERSATIONS} conversations x {TURNS_PER_CONVERSATION} turns, "
            f"seed {args.seed}"
        )
        asyncio.run(run_e6(report_cases, run_id, args.seed, config))


if __name__ == "__main__":
    main()
