"""Scouting-report pipeline tests: LLM path, deterministic fallback, repair, cache.

The DB is the conftest `mock_db` cursor and the LLM is a patched
`report_drafting.chat_completion`, so no test opens a socket. Cache discrimination
lives in SQL, which a mocked cursor cannot evaluate: those tests assert the WHERE
clause's three key predicates and the parameter tuple the route passes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from scouting_fixtures import valuation

from delphos_backend.core.config import Settings, get_settings
from delphos_backend.repositories.players import SEASON_METRICS_KEYS
from delphos_backend.repositories.report_cache import get_cached_player_report
from delphos_backend.services.llm_client import (
    CompletionResult,
    InferenceError,
    InferenceTimeout,
    TokenUsage,
)
from delphos_backend.services.llm_reports import _complete_draft, generate_report
from delphos_backend.services.report_drafting import draft_report_text
from delphos_backend.services.report_facts import build_fact_card
from delphos_backend.services.report_prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_prompt_version,
)
from delphos_backend.services.report_render import render_deterministic_report

_ACTIVE_RUN = {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None}
_MODEL = "qwen/qwen3.5-9b"
_LLM_PATCH = "delphos_backend.services.llm_reports.chat_completion"

# Flat rows as the SQL returns them (test_reports.py shape): get_player_profile
# turns the flat season columns into active_season, get_player_replacements joins
# the fetchall candidate rows under "replacements".
_PROFILE_ROW: dict = {
    "model_run_id": "run_test_001",
    "player_id": 100,
    "name": "Lionel Messi",
    "first_name": "Lionel",
    "last_name": "Messi",
    "player_code": "lionel-messi",
    "country_of_citizenship": "Argentina",
    "date_of_birth": "1987-06-24",
    "position": "Attack",
    "sub_position": "Right Winger",
    "foot": "left",
    "height_in_cm": 170,
    "club_id": 1,
    "club_name": "Inter Miami",
    "image_url": "http://img.png",
    "url": "http://tm.de/messi",
    "cluster_id": 0,
    "season": 2025,
    "as_of_date": "2025-06-01",
    "league_id": "ES1",
    "minutes": 1800.0,
    "apps": 20.0,
    "starts": 20.0,
    "goals": 15.0,
    "assists": 12.0,
    "yellow_cards": 1.0,
    "red_cards": 0.0,
    "starter_ratio": 1.0,
    "win_rate": 0.75,
    "clean_sheet_rate": 0.3,
    "goals_conceded_per_match": 1.0,
    "league_position": 1.0,
    "age": 37.0,
}
_TARGET_ROW: dict = {
    "target_player_id": 100,
    "target_name": "Lionel Messi",
    "model_run_id": "run_test_001",
    "season": 2025,
    "is_elite_asset": False,
    "target_market_value_eur": 25_000_000.0,
    "qualifying_count": 2,
    "shortfall_reason": None,
}
_CANDIDATE_ROWS: list[dict] = [
    {
        "rank": 1,
        "candidate_player_id": 200,
        "candidate_name": "Jonathan David",
        "candidate_club_name": "LOSC Lille",
        "similarity_score": 0.87,
        "candidate_market_value_eur": 21_000_000.0,
        "cost_savings_eur": 4_000_000.0,
        "cost_ratio": 0.84,
        "candidate_valuation_status": "undervalued",
    },
    {
        "rank": 2,
        "candidate_player_id": 201,
        "candidate_name": "Serhou Guirassy",
        "candidate_club_name": "Borussia Dortmund",
        "similarity_score": 0.81,
        "candidate_market_value_eur": 18_000_000.0,
        "cost_savings_eur": 3_500_000.0,
        "cost_ratio": 0.78,
        "candidate_valuation_status": "fair",
    },
]

CLEAN_DRAFT: dict = {
    "dictamen_financiero": {
        "headline": "Margen favorable sobre el valor justo.",
        "body": "Cotiza {market_value_eur} frente a un Valor Justo de {fair_value_eur}.",
    },
    "rendimiento": {
        "headline": "Temporada de alta producción.",
        "body": "Autor de {goals} goles en {minutes} minutos.",
    },
    "alternativas": {
        "headline": "Dos alternativas cualificadas en el mercado.",
        "body": "Perfil {cluster_id} con {qualifying_count} pares.",
        "candidatos": [
            {
                "nombre": "Jonathan David",
                "valoracion": "Ahorra {cost_savings_eur} y {cost_ratio} del valor del objetivo.",
            }
        ],
    },
}


def completion(content: str, model: str = _MODEL) -> CompletionResult:
    """One fake completion as llm_client would return it."""
    return CompletionResult(
        content=content, reasoning_content=None, usage=TokenUsage(), timings=None, model=model
    )


def draft_json(**overrides: object) -> str:
    """The clean draft as JSON, optionally with top-level sections replaced."""
    return json.dumps({**CLEAN_DRAFT, **overrides}, ensure_ascii=False)


def saved_row(source: str, llm_model: str | None, prompt_version: str | None) -> dict:
    """Canned INSERT ... RETURNING row carrying the provenance under test."""
    return {
        "id": 8,
        "player_id": 100,
        "player_name": "Lionel Messi",
        "model_run_id": "run_test_001",
        "report_type": "scouting",
        "content": "stored report text",
        "created_at": datetime(2026, 11, 7, 12, 5, tzinfo=UTC),
        "source": source,
        "llm_model": llm_model,
        "prompt_version": prompt_version,
    }


def wire_route_rows(cur: AsyncMock, saved: dict, cached: dict | None = None) -> None:
    """Queue the route's lookups, the INSERT RETURNING, and the candidate rows.

    The route reads the active run, the cache row, the profile, the valuation and
    the replacement payload before it inserts.
    """
    cur.fetchone.side_effect = [
        _ACTIVE_RUN,
        cached,
        _PROFILE_ROW,
        valuation(),
        _TARGET_ROW,
        saved,
    ]
    cur.fetchall.return_value = list(_CANDIDATE_ROWS)


def received_profile() -> dict:
    """The profile get_player_profile returns for the wired fixture row."""
    return {
        **_PROFILE_ROW,
        "active_season": {key: _PROFILE_ROW[key] for key in SEASON_METRICS_KEYS},
    }


def received_replacements() -> dict:
    """The payload get_player_replacements returns for the wired fixture rows."""
    return {**_TARGET_ROW, "replacements": list(_CANDIDATE_ROWS)}


def expected_deterministic() -> str:
    """What the deterministic renderer produces for the wired fixture rows."""
    return render_deterministic_report(
        build_fact_card(received_profile(), valuation(), received_replacements())
    )


def execute_call(cur: AsyncMock, needle: str) -> object:
    """The single cursor.execute call whose SQL contains `needle`."""
    matches = [call for call in cur.execute.call_args_list if needle in call.args[0]]
    assert len(matches) == 1, f"expected one execute call containing {needle!r}"
    return matches[0]


def cache_call(cur: AsyncMock) -> object:
    """The single cache query the route issues."""
    matches = [
        call for call in cur.execute.call_args_list if "IS NOT DISTINCT FROM" in call.args[0]
    ]
    assert len(matches) == 1, "expected one cache query"
    return matches[0]


def assert_deterministic_stored(cur: AsyncMock, response: object) -> None:
    """200 with source='deterministic', NULL provenance, deterministic-renderer text."""
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "deterministic"
    assert body["llm_model"] is None
    assert body["prompt_version"] is None
    params = execute_call(cur, "INSERT INTO app.reports").args[1]
    assert params == (
        100,
        "run_test_001",
        "scouting",
        expected_deterministic(),
        "deterministic",
        None,
        None,
    )


@pytest.mark.asyncio
async def test_happy_path_llm_report_records_provenance(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    wire_route_rows(cur, saved_row("llm", _MODEL, PROMPT_VERSION))
    settings = get_settings()

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [completion(json.dumps(CLEAN_DRAFT, ensure_ascii=False))]
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "llm"
    assert body["llm_model"] == _MODEL
    assert body["prompt_version"] == PROMPT_VERSION

    params = execute_call(cur, "INSERT INTO app.reports").args[1]
    assert params[4:7] == ("llm", _MODEL, PROMPT_VERSION)
    stored = params[3]
    assert "<strong>Dictamen Financiero:</strong>" in stored
    assert "€45.0M" in stored and "€25.0M" in stored  # substituted {fair}/{market}
    assert "€4.0M" in stored  # candidate-scoped {cost_savings_eur}
    assert "{" not in stored  # no leftover placeholders

    assert chat.call_count == 1
    kwargs = chat.call_args.kwargs
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["max_tokens"] == settings.llm_report_max_tokens
    assert kwargs["enable_thinking"] == settings.llm_enable_thinking
    messages = kwargs["messages"] if "messages" in kwargs else chat.call_args.args[0]
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    sent_card = json.loads(messages[1]["content"])
    assert sent_card["facts"]["market_value_eur"]["display"] == "€25.0M"
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_stored_model_is_the_requested_one_not_the_server_reported_one(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    """The cache key is built from the requested id, so that is what is stored."""
    cur = mock_db.cursor.return_value.__aenter__.return_value
    wire_route_rows(cur, saved_row("llm", get_settings().llm_model_name, PROMPT_VERSION))

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [
            completion(json.dumps(CLEAN_DRAFT, ensure_ascii=False), model="server-reported-id")
        ]
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    assert response.json()["llm_model"] == get_settings().llm_model_name
    params = execute_call(cur, "INSERT INTO app.reports").args[1]
    assert params[5] == get_settings().llm_model_name
    assert params[5] != "server-reported-id"


@pytest.mark.asyncio
async def test_seed_and_prompt_version_follow_the_given_settings() -> None:
    settings = Settings(llm_api_url="http://llm.test/v1", llm_model_name=_MODEL)

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [completion(json.dumps(CLEAN_DRAFT, ensure_ascii=False))]
        result = await generate_report(
            received_profile(), valuation(), received_replacements(), settings=settings, seed=7
        )

    assert chat.call_args.kwargs["seed"] == 7
    assert result.source == "llm"
    assert result.llm_model == _MODEL
    assert result.prompt_version is not None and "-t" in result.prompt_version


@pytest.mark.asyncio
async def test_llm_timeout_falls_back_to_deterministic(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    wire_route_rows(cur, saved_row("deterministic", None, None))

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = InferenceTimeout("timed out after 120s")
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert_deterministic_stored(cur, response)
    assert chat.call_count == 1


@pytest.mark.asyncio
async def test_http_error_falls_back_to_deterministic(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    wire_route_rows(cur, saved_row("deterministic", None, None))

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = InferenceError("LLM call failed: connection refused")
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert_deterministic_stored(cur, response)
    assert chat.call_count == 1


@pytest.mark.asyncio
async def test_empty_completion_falls_back_to_deterministic(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    wire_route_rows(cur, saved_row("deterministic", None, None))

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [completion("")]
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert_deterministic_stored(cur, response)
    assert chat.call_count == 1


@pytest.mark.asyncio
async def test_schema_validation_failure_is_repaired_once(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    """A draft with a hand-written number earns one repair, naming the field."""
    cur = mock_db.cursor.return_value.__aenter__.return_value
    wire_route_rows(cur, saved_row("llm", _MODEL, PROMPT_VERSION))
    draft_with_digits = draft_json(
        dictamen_financiero={"headline": "Cuesta 99 millones.", "body": "Sin cifras."}
    )

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [
            completion(draft_with_digits),
            completion(json.dumps(CLEAN_DRAFT, ensure_ascii=False)),
        ]
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    assert response.json()["source"] == "llm"
    assert chat.call_count == 2  # one generation + exactly one repair
    repair_calls = [
        call for call in chat.call_args_list if "no era válido" in call.args[0][-1]["content"]
    ]
    assert len(repair_calls) == 1  # the repair happened once, not twice
    assert "«dictamen_financiero.headline»" in repair_calls[0].args[0][-1]["content"]
    stored = execute_call(cur, "INSERT INTO app.reports").args[1][3]
    assert "99 millones" not in stored


@pytest.mark.asyncio
async def test_second_schema_rejection_falls_back_after_one_repair(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    wire_route_rows(cur, saved_row("deterministic", None, None))
    draft_with_digits = draft_json(
        dictamen_financiero={"headline": "Cuesta 99 millones.", "body": "Sin cifras."}
    )

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [completion(draft_with_digits), completion(draft_with_digits)]
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert_deterministic_stored(cur, response)
    repair_calls = [
        call for call in chat.call_args_list if "no era válido" in call.args[0][-1]["content"]
    ]
    assert len(repair_calls) == 1  # exactly one repair attempt...
    assert chat.call_count == 2  # ...and never a third call


@pytest.mark.asyncio
async def test_a_name_with_an_apostrophe_is_published_and_not_flagged(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    """The escaped apostrophe in a name must not flag the report as ungrounded."""
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        _ACTIVE_RUN,
        None,
        {**_PROFILE_ROW, "name": "Kouadio N'Golo"},
        valuation(),
        _TARGET_ROW,
        saved_row("llm", _MODEL, PROMPT_VERSION),
    ]
    cur.fetchall.return_value = list(_CANDIDATE_ROWS)
    draft = draft_json(
        dictamen_financiero={
            "headline": "Margen favorable.",
            "body": "{player_name} cotiza {market_value_eur}.",
        }
    )

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [completion(draft)]
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    assert response.json()["source"] == "llm"  # not downgraded to the fallback
    assert chat.call_count == 1  # no repair was spent on the entity
    stored = execute_call(cur, "INSERT INTO app.reports").args[1][3]
    assert "Kouadio N&#x27;Golo" in stored


@pytest.mark.asyncio
async def test_the_cache_key_and_the_stored_provenance_come_from_one_settings(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    """The lookup key and the stored provenance are computed from one Settings."""
    cur = mock_db.cursor.return_value.__aenter__.return_value
    wire_route_rows(cur, saved_row("llm", _MODEL, PROMPT_VERSION))
    cfg = Settings(llm_model_name=_MODEL, llm_temperature=0.5)
    expected = build_prompt_version(cfg)

    with (
        patch("delphos_backend.api.reports.get_settings", return_value=cfg),
        patch(_LLM_PATCH) as chat,
    ):
        chat.side_effect = [completion(json.dumps(CLEAN_DRAFT, ensure_ascii=False))]
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    assert expected != PROMPT_VERSION  # the settings really are a different one
    assert cache_call(cur).args[1][4] == expected
    params = execute_call(cur, "INSERT INTO app.reports").args[1]
    assert params[6] == expected


@pytest.mark.asyncio
async def test_unknown_placeholder_falls_back_without_broken_sentence(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    wire_route_rows(cur, saved_row("deterministic", None, None))
    draft_with_unknown = draft_json(
        rendimiento={"headline": "Sin datos.", "body": "Cuesta {unknown_fact} hoy."}
    )

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [completion(draft_with_unknown)]
        response = await client.post("/reports/generate", json={"player_id": 100})

    # Full deterministic text — not an empty-string substitution of the unknown key.
    assert_deterministic_stored(cur, response)
    assert "{unknown_fact}" not in execute_call(cur, "INSERT INTO app.reports").args[1][3]


@pytest.mark.asyncio
async def test_ungrounded_prose_is_repaired_once_and_never_twice() -> None:
    """The numeric repair spends the single attempt when the prose is ungrounded."""
    card = build_fact_card(received_profile(), valuation(), received_replacements())
    messages = [{"role": "system", "content": "instrucciones"}]

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [
            completion(json.dumps(CLEAN_DRAFT, ensure_ascii=False)),
            completion(json.dumps(CLEAN_DRAFT, ensure_ascii=False)),
        ]

        async def complete(request):
            return await _complete_draft(request, get_settings(), None)

        # An empty allowed set leaves every number of the rendered text ungrounded.
        result = await draft_report_text(messages, complete, card, set())

    assert result is None  # no grounded draft: the caller falls back
    assert chat.call_count == 2  # one generation + exactly one repair
    assert "números que no figuran" in chat.call_args_list[1].args[0][-1]["content"]


@pytest.mark.asyncio
async def test_cache_lookup_reaches_both_provenance_keys(
    mock_db: AsyncMock,
) -> None:
    """The cache query covers the LLM key and the fresh deterministic key."""
    cur = mock_db.cursor.return_value.__aenter__.return_value
    row = saved_row("llm", _MODEL, PROMPT_VERSION)
    cur.fetchone.return_value = row

    found = await get_cached_player_report(
        mock_db,
        100,
        "run_test_001",
        "scouting",
        llm_model=_MODEL,
        prompt_version=PROMPT_VERSION,
    )

    assert found == row
    call = cache_call(cur)
    assert "r.source = 'llm'" in call.args[0]
    assert "r.source = 'deterministic'" in call.args[0]
    assert "r.llm_model IS NOT DISTINCT FROM %s" in call.args[0]
    assert "r.prompt_version IS NOT DISTINCT FROM %s" in call.args[0]
    assert call.args[1] == (100, "run_test_001", "scouting", _MODEL, PROMPT_VERSION)


@pytest.mark.asyncio
async def test_cache_lookup_deterministic_and_llm_keys_do_not_collide(
    mock_db: AsyncMock,
) -> None:
    """Both directions: NULL provenance finds a deterministic row, and the LLM
    key for the same player does not return that row.

    With a mocked cursor the row selection mirrors PostgreSQL applying the WHERE
    clause asserted below: the two branches name their source, and
    `IS NOT DISTINCT FROM` matches NULLs only to NULLs — so even a pre-0004 LLM
    row (source 'llm', NULL model and prompt) can never satisfy the deterministic
    key, and vice versa.
    """
    cur = mock_db.cursor.return_value.__aenter__.return_value
    deterministic_row = saved_row("deterministic", None, None)
    cur.fetchone.side_effect = [deterministic_row, None]

    found_deterministic = await get_cached_player_report(
        mock_db,
        100,
        "run_test_001",
        "scouting",
        llm_model=None,
        prompt_version=None,
    )
    found_llm = await get_cached_player_report(
        mock_db,
        100,
        "run_test_001",
        "scouting",
        llm_model=_MODEL,
        prompt_version=PROMPT_VERSION,
    )

    assert found_deterministic == deterministic_row  # direction 1: both NULLs hit
    assert found_llm is None  # direction 2: the deterministic row is not an LLM hit

    calls = [call for call in cur.execute.call_args_list if "IS NOT DISTINCT" in call.args[0]]
    assert len(calls) == 2
    assert calls[0].args[1] == (100, "run_test_001", "scouting", None, None)
    assert calls[1].args[1] == (100, "run_test_001", "scouting", _MODEL, PROMPT_VERSION)
    for call in calls:
        assert "r.source = 'llm'" in call.args[0]
        assert "r.source = 'deterministic'" in call.args[0]
        assert "r.llm_model IS NOT DISTINCT FROM %s" in call.args[0]
        assert "r.prompt_version IS NOT DISTINCT FROM %s" in call.args[0]


@pytest.mark.asyncio
async def test_route_queries_cache_with_current_configuration(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cached = saved_row("llm", _MODEL, PROMPT_VERSION)
    wire_route_rows(cur, saved_row("llm", _MODEL, PROMPT_VERSION), cached=cached)

    response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    assert response.json()["id"] == 8  # cached row served
    call = cache_call(cur)
    assert call.args[1] == (
        100,
        "run_test_001",
        "scouting",
        get_settings().llm_model_name,
        PROMPT_VERSION,
    )


@pytest.mark.asyncio
async def test_second_request_after_a_fallback_does_not_call_the_llm_again(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    """With the LLM down, the fallback row answers the next request."""
    cur = mock_db.cursor.return_value.__aenter__.return_value
    fallback = saved_row("deterministic", None, None)
    fallback["created_at"] = datetime.now(UTC)
    cur.fetchone.side_effect = [
        _ACTIVE_RUN,
        None,
        _PROFILE_ROW,
        valuation(),
        _TARGET_ROW,
        fallback,
        _ACTIVE_RUN,
        fallback,
    ]
    cur.fetchall.return_value = list(_CANDIDATE_ROWS)

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = InferenceTimeout("timed out after 120s")
        first = await client.post("/reports/generate", json={"player_id": 100})
        second = await client.post("/reports/generate", json={"player_id": 100})

    assert first.status_code == 200
    assert first.json()["source"] == "deterministic"
    assert second.status_code == 200
    assert second.json()["source"] == "deterministic"
    assert chat.call_count == 1  # the second request never called the LLM


@pytest.mark.asyncio
async def test_stale_deterministic_row_does_not_answer_the_request(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    """A fallback older than the cache window is regenerated, not served."""
    cur = mock_db.cursor.return_value.__aenter__.return_value
    stale = saved_row("deterministic", None, None)
    stale["created_at"] = datetime(2020, 1, 1, tzinfo=UTC)
    wire_route_rows(cur, saved_row("llm", _MODEL, PROMPT_VERSION), cached=stale)

    with patch(_LLM_PATCH) as chat:
        chat.side_effect = [completion(json.dumps(CLEAN_DRAFT, ensure_ascii=False))]
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    assert response.json()["source"] == "llm"
    assert chat.call_count == 1


@pytest.mark.asyncio
async def test_report_type_outside_scouting_rejected_with_422(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    response = await client.post(
        "/reports/generate", json={"player_id": 100, "report_type": "replacement"}
    )

    assert response.status_code == 422
    cur = mock_db.cursor.return_value.__aenter__.return_value
    assert not cur.execute.called  # rejected before any DB work
