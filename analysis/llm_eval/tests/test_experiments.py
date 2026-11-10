"""Pure-logic tests for the E1–E9 scripts and the JSONL renderer — no server, no database.

Covers the metric computations (argument exact-match, refusal accuracy, error magnitude,
Jaccard/cross-seed similarity, degeneracy), the E7/E8/E9 grid expansion and arm
definitions, the E2 format check against the known `formatEurM` cases, the blind-pair
preference arithmetic, and `report.py` rendering a fixture JSONL end to end.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import exp_report_quality as erq
import exp_sampling as esamp
import exp_tool_calling as etc_mod
import pytest
import report as report_mod
from cases_chat import CHAT_CASES
from cases_report import ReportCase
from harness import build_request

# --- argument exact-match and error classification (E4/E8) --------------------------------


def test_arguments_match_is_strict_equality() -> None:
    assert etc_mod.arguments_match({"league_id": "L1"}, {"league_id": "L1"})
    assert not etc_mod.arguments_match({"league_id": "L1"}, {"league_id": "ES1"})
    assert not etc_mod.arguments_match({"league_id": "L1"}, {"league_id": "L1", "limit": 5})
    assert not etc_mod.arguments_match({"position": "Attack"}, {})
    assert not etc_mod.arguments_match({"position": "Attack"}, None)


def test_classify_call_error_codes() -> None:
    expected = [{"tool": "search_players", "arguments": {"league_id": "L1"}}]
    assert etc_mod.classify_call_error(expected, expected) == "none"
    assert etc_mod.classify_call_error(expected, []) == "no_call"
    assert (
        etc_mod.classify_call_error(
            expected, [{"tool": "get_cluster_summary", "arguments": {"cluster_id": 1}}]
        )
        == "wrong_tool"
    )
    assert (
        etc_mod.classify_call_error(expected, [{"tool": "search_players", "arguments": {}}])
        == "missing_arg"
    )
    assert (
        etc_mod.classify_call_error(
            expected, [{"tool": "search_players", "arguments": {"league_id": "ES1"}}]
        )
        == "wrong_league_id"
    )
    valuation = [{"tool": "get_player_valuation", "arguments": {"player_id": 418560}}]
    expected_valuation = [{"tool": "get_player_valuation", "arguments": {"player_id": 418561}}]
    assert etc_mod.classify_call_error(expected_valuation, valuation) == "wrong_player_id"
    assert (
        etc_mod.classify_call_error(
            [{"tool": "search_players", "arguments": {"position": "Attack", "league_id": "ES1"}}],
            [{"tool": "search_players", "arguments": {"position": "Attack"}}],
        )
        == "missing_arg"
    )
    assert etc_mod.classify_call_error(expected, expected + expected) == "sequence_mismatch"
    assert etc_mod.classify_call_error([], expected) == "not_applicable"


def test_error_magnitude_orders_the_bugs() -> None:
    scale = etc_mod.ERROR_MAGNITUDE
    assert scale["none"] == 0
    assert scale["missing_arg"] < scale["wrong_cluster_id"] < scale["wrong_league_id"]
    assert scale["wrong_league_id"] < scale["wrong_player_id"] < scale["wrong_tool"]
    assert scale["no_call"] == scale["wrong_tool"]


def test_score_case_and_aggregate_bundle() -> None:
    by_id = {c.case_id: c for c in CHAT_CASES}
    search = etc_mod.ChatOutcome(
        case_id="q01",
        arm="default",
        seed=101,
        calls=[{"tool": "search_players", "arguments": {"position": "Attack"}, "iteration": 0}],
        first_parsed=True,
    )
    refusal = etc_mod.ChatOutcome(
        case_id="q19",
        arm="default",
        seed=101,
        final_answer="No puedo responder a eso: no está en las herramientas disponibles.",
    )
    not_found = etc_mod.ChatOutcome(
        case_id="q20",
        arm="default",
        seed=101,
        final_answer="No encontré a Marco Nobody en los datos disponibles.",
    )
    scores = [
        etc_mod.score_case(by_id["q01"], search),
        etc_mod.score_case(by_id["q19"], refusal),
        etc_mod.score_case(by_id["q20"], not_found),
    ]
    assert scores[0]["args_exact"] is True
    assert scores[0]["tool_selection_ok"] is True
    assert scores[0]["no_call"] is False
    assert scores[1]["refusal_ok"] is True
    assert scores[2]["not_found_ok"] is True

    aggregate = etc_mod.aggregate_scores(scores)
    assert aggregate["argument_exact_match"] == 1.0
    assert aggregate["tool_selection_accuracy"] == 1.0
    assert aggregate["no_call_rate"] == 0.0
    assert aggregate["refusal_accuracy"] == 1.0
    assert aggregate["not_found_accuracy"] == 1.0
    assert aggregate["mean_call_count"] == 1.0
    assert aggregate["loop_exhaustion_rate"] == 0.0


def test_refusal_accuracy_is_zero_for_a_fabricated_answer() -> None:
    by_id = {c.case_id: c for c in CHAT_CASES}
    fabricated = etc_mod.ChatOutcome(
        case_id="q19",
        arm="default",
        seed=101,
        final_answer="Liverpool ganó la final por 2-0 ante el Tottenham.",
    )
    score = etc_mod.score_case(by_id["q19"], fabricated)
    assert score["refusal_ok"] is False
    aggregate = etc_mod.aggregate_scores([score])
    assert aggregate["refusal_accuracy"] == 0.0

    with_call = etc_mod.ChatOutcome(
        case_id="q19",
        arm="default",
        seed=101,
        calls=[{"tool": "search_players", "arguments": {}, "iteration": 0}],
        final_answer="No puedo responder: no está en las herramientas.",
    )
    assert etc_mod.score_case(by_id["q19"], with_call)["refusal_ok"] is False


def test_expected_call_sequences() -> None:
    by_id = {c.case_id: c for c in CHAT_CASES}
    single = etc_mod.expected_calls(by_id["q01"])
    assert single == [{"tool": "search_players", "arguments": {"position": "Attack"}}]
    multi = etc_mod.expected_calls(by_id["q17"])
    assert [c["tool"] for c in multi] == ["search_players", "get_player_valuation"]
    assert multi[0]["arguments"]["league_id"] == "ES1"
    assert multi[1]["arguments"] == {"player_id": None}
    assert etc_mod.expected_calls(by_id["q19"]) == []


def test_refusal_and_not_found_markers() -> None:
    assert etc_mod.is_refusal("No dispongo de esa información en las herramientas.")
    assert etc_mod.is_refusal("Eso está fuera de mi conjunto de datos.")
    assert not etc_mod.is_refusal("Liverpool ganó 2-0 en la final de 2019.")
    assert etc_mod.is_honest_not_found("No encontré a Marco Nobody en los datos.")
    assert etc_mod.is_honest_not_found("Ningún jugador con ese nombre existe.")
    assert not etc_mod.is_honest_not_found("Lionel Messi juega de delantero.")


def test_e5_third_arm_only_with_the_flag() -> None:
    two = etc_mod.e5_arms(False)
    assert [a.name for a in two] == ["t_off", "t_on"]
    assert two[0].enable_thinking is False
    assert two[1].enable_thinking is True
    three = etc_mod.e5_arms(True)
    assert [a.name for a in three] == ["t_off", "t_on", "t_server_reasoning_off"]
    assert three[2].enable_thinking is True  # template on, server flag off isolates it


def test_e6_conversation_scripts() -> None:
    cases = [
        ReportCase(
            case_id=f"c0_{zone}",
            cluster_id=0,
            valuation_zone=zone,
            player_id=100 + i,
            player_name=f"Player {i}",
        )
        for i, zone in enumerate(("undervalued", "fair", "overvalued"))
    ]
    convs = etc_mod.conversations(cases + cases + cases + cases)  # 9 -> first 6 kept
    assert len(convs) == 6
    for conv in convs:
        assert len(conv["turns"]) == 5
        assert conv["retracted"] in conv["turns"][1]
        assert conv["retracted"] in conv["turns"][2]
        assert "Corrijo" in conv["turns"][2]
        assert "gana al año" in conv["turns"][4]  # the unanswerable turn


# --- Jaccard, degeneracy, grids (E7/E8/E9) ------------------------------------------------


def test_jaccard_identical_disjoint_and_partial() -> None:
    assert esamp.jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert esamp.jaccard({"a"}, {"b"}) == 0.0
    assert esamp.jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)
    assert esamp.jaccard(set(), set()) == 1.0
    assert esamp.jaccard(set(), {"a"}) == 0.0


def test_cross_seed_similarity_is_a_mean_and_higher_is_more_repeatable() -> None:
    assert esamp.cross_seed_similarity([{"a", "b"}, {"a", "b"}, {"a", "b"}]) == 1.0
    assert esamp.cross_seed_similarity([{"a"}, {"b"}, {"c"}]) == 0.0
    mixed = esamp.cross_seed_similarity([{"a", "b"}, {"a", "b"}, {"a"}])
    assert mixed == pytest.approx((1.0 + 0.5 + 0.5) / 3)
    assert esamp.cross_seed_similarity([{"a"}]) == 1.0  # fewer than two seeds


def test_degeneracy_metrics() -> None:
    repeated = "el jugador rendió " + " ".join(["alpha"] * 10) + " y " + " ".join(["alpha"] * 10)
    assert esamp.has_repeated_8gram(repeated) is True
    assert (
        esamp.has_repeated_8gram(
            "el jugador rendió bien en la temporada pasada según los datos publicados"
        )
        is False
    )
    assert esamp.repeated_8gram_rate([repeated, "texto normal sin repeticion"]) == 0.5
    assert esamp.repeated_8gram_rate([]) == 0.0
    assert esamp.distinct_ngram_ratio("corto") == 0.0
    ratio = esamp.distinct_ngram_ratio(
        "el jugador fue el mejor el jugador fue el peor según los datos"
    )
    assert 0.0 < ratio < 1.0


def test_e7_e8_e9_grid_sizes() -> None:
    cases9 = list(range(9))
    cases20 = list(range(20))
    e7 = esamp.expand_grid(cases9, esamp.REPORT_ARMS, esamp.E7_SEEDS)
    e8 = esamp.expand_grid(cases20, esamp.CHAT_ARMS, esamp.E8_SEEDS)
    e9 = esamp.expand_grid(cases9, esamp.E9_ARMS, esamp.E9_SEEDS) + esamp.expand_grid(
        cases20, esamp.E9_ARMS, esamp.E9_SEEDS
    )
    assert len(e7) == 9 * 4 * 3 == 108
    assert len(e8) == 20 * 4 * 2 == 160
    assert len(e9) == 9 * 2 * 1 + 20 * 2 * 1 == 58
    assert len(set((id(c), a.name, s) for c, a, s in e7)) == 108


def test_grid_arm_parameters_match_section_17_4() -> None:
    a, b, c, d = esamp.REPORT_ARMS
    assert (a.temperature, a.top_p, a.top_k, a.presence_penalty) == (0.7, 0.8, 20, 0.0)
    assert (b.temperature, b.top_p, b.top_k) == (0.2, 0.8, 20)
    assert (c.temperature, c.top_p, c.top_k) == (0.4, 0.9, 40)
    assert (d.temperature, d.top_p, d.top_k) == (0.1, 0.8, 20)
    assert esamp.CHAT_ARMS == esamp.REPORT_ARMS
    assert esamp.E9_ARMS[0].presence_penalty == 0.0
    assert esamp.E9_ARMS[1].presence_penalty == 1.5
    assert esamp.E7_SEEDS == (101, 202, 303)
    assert esamp.E8_SEEDS == (101, 202)
    assert esamp.E9_SEEDS == (101,)


def test_requests_carry_presence_penalty_and_never_repeat_penalty() -> None:
    arm = esamp.E9_ARMS[1]
    body = build_request(
        [{"role": "user", "content": "x"}],
        seed=101,
        temperature=arm.temperature,
        top_p=arm.top_p,
        top_k=arm.top_k,
        presence_penalty=arm.presence_penalty,
    )
    assert body["presence_penalty"] == 1.5
    assert "repeat_penalty" not in body


# --- E2 formatting against the known formatEurM cases -----------------------------------


def test_format_check_accepts_product_numbers() -> None:
    prose = (
        "Cotiza en €25.0M frente a €540K de ahorro y €250 de coste; convierte el 75% "
        "de las ocasiones, un ratio de 1.8x en 1800 minutos, con +32% de margen y "
        "-12% de descuento. El valor ausente es N/D."
    )
    assert erq.format_violations(prose) == []


def test_format_check_flags_off_format_numbers() -> None:
    prose = (
        "Bare 25.0M sin símbolo, español 25,0 M€, decimales €25.00M, "
        "separador 1,800 y suelto 1.8 no cuadran; el residual 0.34 sí."
    )
    violations = set(erq.format_violations(prose))
    assert "25.0M" in violations
    assert "25,0" in violations
    assert "€25.00M" in violations
    assert "1,800" in violations
    assert "1.8" in violations
    assert "0.34" not in violations  # format_fixed(raw, 2) residuals are product-legal


# --- blind pairs and preference rate (E1) --------------------------------------------------


def test_blind_pair_randomises_and_the_key_maps_back() -> None:
    texts = {"llm": "prosa uno", "deterministic": "prosa dos"}
    blinded, key = erq.blind_pair(random.Random(7), texts)
    assert sorted(blinded.values()) == sorted(texts.values())
    assert len(key) == 2
    for label, source in key.items():
        assert blinded[label] == texts[source]
    assert set(key.values()) == set(texts)


def test_preference_rate_for_the_llm_side() -> None:
    key = {
        "q1": {"A": "llm", "B": "deterministic"},
        "q2": {"A": "deterministic", "B": "llm"},
        "q3": {"A": "llm", "B": "deterministic"},
    }
    rate = erq.preference_rate(key, {"q1": "A", "q2": "A", "q9": "B"})
    assert rate["rated"] == 2
    assert rate["llm_preferred"] == 1
    assert rate["preference_rate"] == 0.5
    assert rate["unrated"] == ["q3"]
    assert rate["unknown_ratings"] == ["q9"]
    assert erq.preference_rate(key, {})["preference_rate"] is None


# --- report.py over a fixture JSONL -------------------------------------------------------


def _fixture_rows() -> list[dict]:
    return [
        {
            "experiment": "e4",
            "kind": "call",
            "case_id": "q01",
            "arm": "default",
            "seed": 101,
            "latency_ms": 120.5,
            "usage": {"prompt_tokens": 400, "completion_tokens": 30, "total_tokens": 430},
            "timings": {
                "prompt_n": 400,
                "predicted_n": 30,
                "prompt_per_second": 250.0,
                "predicted_per_second": 42.0,
            },
        },
        {
            "experiment": "e4",
            "kind": "score",
            "case_id": "q01",
            "arm": "default",
            "ok": True,
            "answerable": True,
            "args_exact": True,
            "call_count": 1,
        },
        {
            "experiment": "e4",
            "kind": "score",
            "case_id": "q03",
            "arm": "default",
            "ok": True,
            "answerable": True,
            "args_exact": False,
            "call_count": 0,
        },
        {
            "experiment": "e4",
            "kind": "summary",
            "arm": "default",
            "argument_exact_match": 0.5,
            "no_call_rate": 0.5,
            "refusal_accuracy": 1.0,
        },
        {
            "experiment": "e3",
            "kind": "score",
            "case_id": "c0_undervalued",
            "prompt_n": 9000,
            "predicted_n": 700,
            "over_prompt_budget": True,
        },
        {
            "experiment": "e3",
            "kind": "score",
            "case_id": "c0_fair",
            "prompt_n": 500,
            "predicted_n": 700,
            "over_prompt_budget": False,
        },
        {
            "experiment": "e3",
            "kind": "summary",
            "max_prompt_n": 9000,
            "prompt_budget": 8000,
            "cases_over_budget": ["c0_undervalued"],
            "budget_ok": False,
        },
    ]


def test_report_renders_a_fixture_jsonl_without_a_server(tmp_path: Path) -> None:
    in_dir = tmp_path / "jsonl"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "e4.jsonl").write_text(
        "\n".join(json.dumps(r) for r in _fixture_rows() if r["experiment"] == "e4")
        + "\nnot-json-at-all\n",
        encoding="utf-8",
    )
    (in_dir / "e3.jsonl").write_text(
        "\n".join(json.dumps(r) for r in _fixture_rows() if r["experiment"] == "e3") + "\n",
        encoding="utf-8",
    )
    summary = report_mod.render(in_dir, out_dir)
    assert summary["experiments"]["e4"]["scores"] == 2
    assert summary["experiments"]["e3"]["scores"] == 2
    for name in (
        "e4_calls.csv",
        "e4_scores.csv",
        "e4_summaries.csv",
        "e3_scores.csv",
        "tables.md",
        "fig_prompt_budget.png",
        "fig_argument_exact_match.png",
    ):
        assert (out_dir / name).is_file(), f"missing {name}"
    tables = (out_dir / "tables.md").read_text(encoding="utf-8")
    assert "argument_exact_match" in tables
    assert "0.5" in tables
    calls_csv = (out_dir / "e4_calls.csv").read_text(encoding="utf-8")
    assert "120.5" in calls_csv


def test_report_fails_cleanly_when_nothing_was_recorded(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SystemExit) as excinfo:
        report_mod.render(empty, tmp_path / "out")
    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "report failed:" in captured.err
    assert "Traceback" not in captured.err
