"""Unit tests for the OpenAI-compatible llama.cpp inference client."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi import HTTPException

from delphos_backend.core.config import Settings
from delphos_backend.services.llm_client import (
    InferenceError,
    InferenceTimeout,
    chat_completion,
)

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
    return Settings(
        llm_api_url="http://llm.test/v1",
        llm_model_name="qwen/qwen3.5-9b",
        llm_timeout_seconds=5.0,
        llm_max_tokens=512,
        llm_report_max_tokens=1400,
        llm_temperature=0.7,
        llm_top_p=0.8,
        llm_top_k=20,
        llm_presence_penalty=0.0,
        llm_enable_thinking=False,
        **overrides,
    )


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
