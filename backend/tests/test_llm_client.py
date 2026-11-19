"""Unit tests for the OpenAI-compatible llama.cpp inference client."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

import httpx
import pytest
from fastapi import HTTPException

from delphos_backend.core.config import Settings
from delphos_backend.services.llm_client import (
    InferenceError,
    InferenceTimeout,
    chat_completion,
)
from delphos_backend.services.llm_targets import warn_about_fallback_address

FALLBACK_HOST = "10.147.85.4"
"""The peer's address: an IP literal inside the default peer range (ADR-033)."""

PRIMARY_HOST = "llm.test"

MODEL_ID = "qwen/qwen3.5-9b"
MODEL_LIST = {"models": [{"id": MODEL_ID}]}
"""The body a serving endpoint answers its model list with."""

GOOD_COMPLETION = {
    "model": "qwen/qwen3.5-9b",
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "Informe de scouting.",
                "reasoning_content": "Repasando los datos.",
            }
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    "timings": {
        "prompt_n": 100,
        "predicted_n": 50,
        "prompt_per_second": 250.0,
        "predicted_per_second": 48.5,
    },
}


def make_settings(**overrides: object) -> Settings:
    """Settings with every asserted LLM field pinned so the environment cannot shift them."""
    defaults: dict[str, object] = {
        "llm_api_url": "http://llm.test/v1",
        "llm_model_name": "qwen/qwen3.5-9b",
        "llm_timeout_seconds": 5.0,
        "llm_max_tokens": 512,
        "llm_report_max_tokens": 1400,
        "llm_temperature": 0.7,
        "llm_top_p": 0.8,
        "llm_top_k": 20,
        "llm_presence_penalty": 0.0,
        "llm_enable_thinking": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def capture_transport(payload: object) -> tuple[httpx.MockTransport, dict[str, httpx.Request]]:
    """A transport that records the outgoing request and answers with payload."""
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler), captured


@pytest.mark.asyncio
async def test_valid_completion_returns_typed_result() -> None:
    transport, captured = capture_transport(GOOD_COMPLETION)

    result = await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=make_settings(),
        transport=transport,
    )

    assert result.content == "Informe de scouting."
    assert result.reasoning_content == "Repasando los datos."
    assert result.model == "qwen/qwen3.5-9b"
    assert result.usage.prompt_tokens == 100
    assert result.usage.completion_tokens == 50
    assert result.usage.total_tokens == 150
    assert result.timings is not None
    assert result.timings.prompt_n == 100
    assert result.timings.predicted_n == 50
    assert result.timings.prompt_per_second == 250.0
    assert result.timings.predicted_per_second == 48.5
    assert captured["request"].url.path == "/v1/chat/completions"


@pytest.mark.asyncio
async def test_request_body_carries_sampling_template_seed() -> None:
    transport, captured = capture_transport(GOOD_COMPLETION)

    await chat_completion(
        messages=[{"role": "system", "content": "pregunta"}],
        settings=make_settings(),
        max_tokens=1400,
        enable_thinking=True,
        seed=42,
        response_format={"type": "json_schema", "json_schema": {"name": "report", "schema": {}}},
        transport=transport,
    )

    body = json.loads(captured["request"].content)
    assert body["model"] == "qwen/qwen3.5-9b"
    assert body["temperature"] == 0.7
    assert body["top_p"] == 0.8
    assert body["top_k"] == 20
    assert body["presence_penalty"] == 0.0
    assert body["max_tokens"] == 1400
    assert body["stream"] is False
    assert body["chat_template_kwargs"] == {"enable_thinking": True}
    assert body["seed"] == 42
    assert body["response_format"]["type"] == "json_schema"
    assert body["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_request_defaults_omit_seed_and_use_settings_values() -> None:
    transport, captured = capture_transport(GOOD_COMPLETION)

    await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=make_settings(),
        transport=transport,
    )

    body = json.loads(captured["request"].content)
    assert "seed" not in body
    assert body["max_tokens"] == 512
    assert body["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.asyncio
async def test_http_500_raises_domain_exception_not_http_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    with pytest.raises(InferenceError) as excinfo:
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=make_settings(),
            transport=httpx.MockTransport(handler),
        )

    assert not isinstance(excinfo.value, HTTPException)
    assert not isinstance(excinfo.value, InferenceTimeout)


@pytest.mark.asyncio
async def test_timeout_raises_distinguishable_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(InferenceTimeout) as excinfo:
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=make_settings(),
            transport=httpx.MockTransport(handler),
        )

    assert isinstance(excinfo.value, InferenceError)
    assert not isinstance(excinfo.value, HTTPException)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        ({"model": "m", "choices": []}, "no choices"),
        ({"model": "m"}, "no choices"),
        ({"model": "m", "choices": [{"message": {"content": "   "}}]}, "empty completion"),
        ({"model": "m", "choices": [{"message": {}}]}, "empty completion"),
    ],
    ids=["empty-list", "missing-key", "blank-content", "missing-content"],
)
async def test_empty_completion_raises(payload: object, expected_message: str) -> None:
    transport, _ = capture_transport(payload)

    with pytest.raises(InferenceError, match=expected_message):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=make_settings(),
            transport=transport,
        )


@pytest.mark.asyncio
async def test_malformed_json_raises_domain_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>gateway error</html>")

    with pytest.raises(InferenceError, match="malformed JSON"):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=make_settings(),
            transport=httpx.MockTransport(handler),
        )


# --- The fallback endpoint (ADR-033) ------------------------------------------------


def fallback_settings(**overrides: object) -> Settings:
    """Settings with a fallback endpoint configured."""
    defaults: dict[str, object] = {
        "llm_fallback_api_url": f"http://{FALLBACK_HOST}/v1",
        "llm_fallback_model_name": "",
        "llm_fallback_timeout_seconds": 30.0,
        "llm_primary_probe_seconds": 1.0,
    }
    defaults.update(overrides)
    return make_settings(**defaults)


def answering(
    payload: object, status: int = 200, model_id: str = MODEL_ID
) -> Callable[[httpx.Request], httpx.Response]:
    """A handler that answers the probe with a model list and the call with payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"models": [{"id": model_id}]})
        return httpx.Response(status, json=payload)

    return handler


def failing(error: Exception) -> Callable[[httpx.Request], httpx.Response]:
    """A handler that always raises the same transport error."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return handler


def answering_probe_then_failing(
    error: Exception,
) -> Callable[[httpx.Request], httpx.Response]:
    """A handler that answers the reachability probe and then fails the call."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODEL_LIST)
        raise error

    return handler


def routed_transport(
    primary: Callable[[httpx.Request], httpx.Response],
    fallback: Callable[[httpx.Request], httpx.Response],
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    """A transport that routes by host and records every request it served."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == FALLBACK_HOST:
            return fallback(request)
        return primary(request)

    return httpx.MockTransport(handler), calls


def chat_posts(calls: list[httpx.Request]) -> list[httpx.Request]:
    """The chat-completion requests among the recorded ones."""
    return [call for call in calls if call.url.path.endswith("/chat/completions")]


def probes(calls: list[httpx.Request]) -> list[httpx.Request]:
    """The reachability probes among the recorded ones."""
    return [call for call in calls if call.url.path.endswith("/models")]


@pytest.mark.asyncio
async def test_the_fallback_is_never_contacted_when_the_primary_answers() -> None:
    """A healthy primary answers, and the fallback endpoint is not touched."""
    transport, calls = routed_transport(answering(GOOD_COMPLETION), answering(GOOD_COMPLETION))

    result = await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=fallback_settings(),
        transport=transport,
    )

    assert result.endpoint == "primary"
    assert result.requested_model == "qwen/qwen3.5-9b"
    assert len(chat_posts(calls)) == 1  # exactly one completion call
    assert all(call.url.host != FALLBACK_HOST for call in calls)


@pytest.mark.asyncio
async def test_an_unreachable_primary_sends_the_call_straight_to_the_fallback() -> None:
    """A refused connection must not cost the primary's timeout."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")), answering(GOOD_COMPLETION)
    )

    result = await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=fallback_settings(),
        transport=transport,
    )

    assert result.endpoint == "fallback"
    assert result.requested_model == "qwen/qwen3.5-9b"
    assert len(probes(calls)) == 2  # the primary and the fallback were probed, not called
    assert [call.url.host for call in chat_posts(calls)] == [FALLBACK_HOST]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ReadTimeout("timed out"), InferenceTimeout),
        (httpx.ConnectError("connection refused"), InferenceError),
    ],
    ids=["timeout", "transport-error"],
)
async def test_a_failing_primary_call_is_retried_on_the_fallback(
    error: Exception, expected: type[InferenceError]
) -> None:
    """A primary that answers the probe and then fails hands the call over."""
    transport, calls = routed_transport(
        answering_probe_then_failing(error), answering(GOOD_COMPLETION)
    )

    result = await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=fallback_settings(),
        transport=transport,
    )

    assert result.endpoint == "fallback"
    assert [call.url.host for call in chat_posts(calls)] == [PRIMARY_HOST, FALLBACK_HOST]


@pytest.mark.asyncio
async def test_a_failing_primary_http_status_is_retried_on_the_fallback() -> None:
    """A 500 on the primary is an InferenceError, and the fallback serves the call."""

    def primary(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODEL_LIST)
        return httpx.Response(500, json={"error": "server error"})

    transport, calls = routed_transport(primary, answering(GOOD_COMPLETION))

    result = await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=fallback_settings(),
        transport=transport,
    )

    assert result.endpoint == "fallback"
    assert [call.url.host for call in chat_posts(calls)] == [PRIMARY_HOST, FALLBACK_HOST]


@pytest.mark.asyncio
async def test_both_endpoints_failing_raises_one_inference_error() -> None:
    """The two failures are chained, so the log shows both of them."""
    transport, calls = routed_transport(
        answering_probe_then_failing(httpx.ReadTimeout("timed out")),
        answering({"error": "server error"}, status=500),
    )

    with pytest.raises(InferenceError) as excinfo:
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    message = str(excinfo.value)
    assert "both endpoints" in message
    assert "primary" in message and "fallback" in message
    assert "timed out" in message  # the primary failure
    assert isinstance(excinfo.value.__cause__, InferenceError)  # the fallback failure
    assert [call.url.host for call in chat_posts(calls)] == [PRIMARY_HOST, FALLBACK_HOST]


@pytest.mark.asyncio
async def test_without_a_fallback_only_the_primary_is_contacted() -> None:
    """An empty fallback URL changes nothing: one call, no probe, no fallback."""
    transport, calls = routed_transport(answering(GOOD_COMPLETION), answering(GOOD_COMPLETION))

    result = await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=fallback_settings(llm_fallback_api_url=""),
        transport=transport,
    )

    assert result.endpoint == "primary"
    assert len(calls) == 1  # the completion call, and nothing else
    assert len(probes(calls)) == 0
    assert calls[0].url.host == PRIMARY_HOST


@pytest.mark.asyncio
async def test_the_fallback_request_carries_the_fallback_model_id() -> None:
    """The body names the model the endpoint that serves the call actually serves."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")),
        answering(GOOD_COMPLETION, model_id="other/model"),
    )

    await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=fallback_settings(llm_fallback_model_name="other/model"),
        transport=transport,
    )

    body = json.loads(chat_posts(calls)[0].content)
    assert body["model"] == "other/model"


@pytest.mark.asyncio
async def test_an_empty_fallback_model_name_sends_the_primary_model_id() -> None:
    """An empty fallback model name means "the same model as the primary"."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")), answering(GOOD_COMPLETION)
    )

    await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=fallback_settings(),
        transport=transport,
    )

    body = json.loads(chat_posts(calls)[0].content)
    assert body["model"] == "qwen/qwen3.5-9b"


@pytest.mark.asyncio
async def test_the_verdict_of_a_failing_primary_is_cached_for_the_ttl() -> None:
    """A primary the probe judges not serving is probed once per TTL.

    Nothing was attempted on it, so there is no failed attempt to invalidate
    its verdict: the second request reuses it and goes straight to the peer.
    """
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")), answering(GOOD_COMPLETION)
    )

    for _ in range(2):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    assert len(probes(calls)) == 2  # the primary and the fallback, once each
    assert len(chat_posts(calls)) == 2


@pytest.mark.asyncio
async def test_a_primary_that_fails_after_a_serving_probe_is_probed_again_at_once() -> None:
    """The probe said serving and the call failed: the next request probes again.

    A failed attempt contradicts the cached verdict, so it is dropped and the
    next request re-probes the endpoint instead of trusting it.
    """
    transport, calls = routed_transport(
        answering_probe_then_failing(httpx.ConnectError("connection refused")),
        answering(GOOD_COMPLETION),
    )

    for _ in range(2):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    assert len(probes(calls)) == 3  # the primary twice (its call failed), the fallback once
    assert len(chat_posts(calls)) == 4  # each request tried the primary, then the peer


@pytest.mark.asyncio
async def test_an_unreachable_primary_and_a_failing_fallback_raise_one_error() -> None:
    """Neither endpoint served the call, and the error names both of them."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")),
        answering({"error": "server error"}, status=500),
    )

    with pytest.raises(InferenceError) as excinfo:
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    message = str(excinfo.value)
    assert "unreachable" in message
    assert "fallback" in message
    assert [call.url.host for call in chat_posts(calls)] == [FALLBACK_HOST]


@pytest.mark.asyncio
async def test_a_successful_primary_call_keeps_the_cached_verdict() -> None:
    """The primary answered: its verdict stands, so the next call does not re-probe."""
    transport, calls = routed_transport(answering(GOOD_COMPLETION), answering(GOOD_COMPLETION))

    for _ in range(2):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    assert len(probes(calls)) == 1  # the verdict of a serving primary is reused
    assert len(chat_posts(calls)) == 2
    assert [call.url.host for call in chat_posts(calls)] == [PRIMARY_HOST, PRIMARY_HOST]


@pytest.mark.asyncio
async def test_both_endpoints_timing_out_raises_a_timeout() -> None:
    """Two timeouts are a timeout, so the report path spends no repair attempt on them."""
    transport, calls = routed_transport(
        answering_probe_then_failing(httpx.ReadTimeout("timed out")),
        failing(httpx.ReadTimeout("timed out")),
    )

    with pytest.raises(InferenceTimeout) as excinfo:
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    assert isinstance(excinfo.value, InferenceError)
    assert "primary" in str(excinfo.value) and "fallback" in str(excinfo.value)
    # The fallback's own probe timed out, so it was never given a prompt.
    assert [call.url.host for call in chat_posts(calls)] == [PRIMARY_HOST]


@pytest.mark.asyncio
async def test_a_timed_out_probe_and_a_timed_out_fallback_raise_a_timeout() -> None:
    """The probe's timeout counts as the primary's failure, so two timeouts are a timeout."""
    transport, calls = routed_transport(
        failing(httpx.ReadTimeout("probe timed out")),
        failing(httpx.ReadTimeout("timed out")),
    )

    with pytest.raises(InferenceTimeout):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    # The fallback's own probe failed, so it was never given a prompt.
    assert [call.url.host for call in chat_posts(calls)] == []


@pytest.mark.asyncio
async def test_a_malformed_fallback_url_raises_an_inference_error() -> None:
    """httpx.InvalidURL is not an HTTPError, so it must not escape the client."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")), answering(GOOD_COMPLETION)
    )
    settings = fallback_settings(llm_fallback_api_url=f"http://{FALLBACK_HOST}:80x/v1")

    with pytest.raises(InferenceError) as excinfo:
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=settings,
            transport=transport,
        )

    assert not isinstance(excinfo.value, HTTPException)
    assert "fallback" in str(excinfo.value)


@pytest.mark.asyncio
async def test_the_unreachable_primary_reason_is_named_in_the_error() -> None:
    """The probe's reason is not discarded: the error says why the primary was skipped."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")),
        answering({"error": "server error"}, status=500),
    )

    with pytest.raises(InferenceError) as excinfo:
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    assert "connection refused" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, InferenceError)


@pytest.mark.asyncio
async def test_the_fallback_is_named_in_a_warning_without_its_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The logs name the endpoint as scheme://host:port, never the full URL."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")), answering(GOOD_COMPLETION)
    )
    settings = fallback_settings(llm_fallback_api_url=f"http://{FALLBACK_HOST}:8081/v1")

    with caplog.at_level(logging.WARNING):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=settings,
            transport=transport,
        )

    warnings = [
        record.getMessage() for record in caplog.records if record.levelno == logging.WARNING
    ]
    assert any(f"http://{FALLBACK_HOST}:8081" in message for message in warnings)
    assert not any("/v1" in message for message in warnings)


# --- The fallback is probed before it is given a prompt (ADR-033) ----------------


@pytest.mark.asyncio
async def test_a_fallback_that_fails_its_probe_is_never_given_a_prompt() -> None:
    """A dead or wrong address must not receive the club's prompt."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")),
        failing(httpx.ConnectError("connection refused")),
    )

    with pytest.raises(InferenceError):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    assert [call.url.host for call in chat_posts(calls)] == []
    assert len(probes(calls)) == 2  # both endpoints were probed, and neither was called


@pytest.mark.asyncio
async def test_a_fallback_whose_probe_answers_is_used() -> None:
    """The fallback is used when its own probe says it is serving."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")), answering(GOOD_COMPLETION)
    )

    result = await chat_completion(
        messages=[{"role": "user", "content": "hola"}],
        settings=fallback_settings(),
        transport=transport,
    )

    assert result.endpoint == "fallback"
    assert [call.url.host for call in chat_posts(calls)] == [FALLBACK_HOST]


@pytest.mark.asyncio
async def test_a_fallback_serving_another_model_is_refused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A peer that serves another model is refused: the club reads no prose from it."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")),
        answering(GOOD_COMPLETION, model_id="other/model"),
    )

    with caplog.at_level(logging.WARNING), pytest.raises(InferenceError):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(llm_fallback_model_name=MODEL_ID),
            transport=transport,
        )

    assert [call.url.host for call in chat_posts(calls)] == []
    warnings = [
        record.getMessage() for record in caplog.records if record.levelno == logging.WARNING
    ]
    assert any("other/model" in message and MODEL_ID in message for message in warnings)


@pytest.mark.asyncio
async def test_a_fallback_serving_another_model_is_refused_when_no_id_is_configured() -> None:
    """With no configured fallback id the primary's id is expected, and it is strict.

    The peer's prose would otherwise be stored as the club's model output, so
    the peer is refused rather than warned about.
    """
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")),
        answering(GOOD_COMPLETION, model_id="other/model"),
    )

    with pytest.raises(InferenceError) as excinfo:
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    assert "other/model" in str(excinfo.value)
    assert not chat_posts(calls)


@pytest.mark.asyncio
async def test_a_fallback_on_this_hosts_own_address_is_allowed_and_warned_about(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The team wants a backend on this box to consume this box's server."""
    transport, calls = routed_transport(
        failing(httpx.ConnectError("connection refused")), answering(GOOD_COMPLETION)
    )
    settings = fallback_settings(
        llm_fallback_api_url=f"http://{FALLBACK_HOST}:8081/v1",
        inference_publish_ip=FALLBACK_HOST,
    )

    with caplog.at_level(logging.WARNING):
        result = await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=settings,
            transport=transport,
        )

    assert result.endpoint == "fallback"
    warnings = [
        record.getMessage() for record in caplog.records if record.levelno == logging.WARNING
    ]
    assert any(
        f"http://{FALLBACK_HOST}:8081" in message and "own published inference address" in message
        for message in warnings
    )


@pytest.mark.asyncio
async def test_a_failed_primary_call_invalidates_the_cached_verdict() -> None:
    """The next request re-probes instead of trusting a verdict about a failed endpoint."""
    transport, calls = routed_transport(
        answering_probe_then_failing(httpx.ConnectError("connection refused")),
        answering(GOOD_COMPLETION),
    )

    for _ in range(2):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=fallback_settings(),
            transport=transport,
        )

    primary_probes = [call for call in probes(calls) if call.url.host == PRIMARY_HOST]
    assert len(primary_probes) == 2  # the verdict of a failed primary is not reused


@pytest.mark.asyncio
async def test_the_logs_name_the_endpoint_and_the_exception_class(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`httpx.HTTPStatusError` renders the full URL; the log must not carry it."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=MODEL_LIST)
        return httpx.Response(500, json={"error": "server error"})

    settings = fallback_settings(llm_api_url="http://llm.test:8081/v1?api_key=secret")

    with caplog.at_level(logging.WARNING), pytest.raises(InferenceError):
        await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            settings=settings,
            transport=httpx.MockTransport(handler),
        )

    assert "HTTPStatusError" in caplog.text
    assert "http://llm.test:8081" in caplog.text
    assert "api_key" not in caplog.text
    assert "secret" not in caplog.text


def test_the_start_up_check_warns_about_this_hosts_own_address(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The backend says so at start-up, before any request is served."""
    settings = fallback_settings(
        llm_fallback_api_url=f"http://{FALLBACK_HOST}:8081/v1",
        inference_publish_ip=FALLBACK_HOST,
    )

    with caplog.at_level(logging.WARNING):
        warn_about_fallback_address(settings)

    warnings = [
        record.getMessage() for record in caplog.records if record.levelno == logging.WARNING
    ]
    assert any(
        f"http://{FALLBACK_HOST}:8081" in message and "own published inference address" in message
        for message in warnings
    )
