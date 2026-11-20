"""Unit tests for the inference endpoint reachability probe."""

from __future__ import annotations

import asyncio
import logging
import threading

import httpx
import pytest

from delphos_backend.services import llm_probe
from delphos_backend.services.llm_probe import (
    ProbeResult,
    clear_probe_cache,
    invalidate_probe,
    probe_endpoint,
)
from delphos_backend.services.llm_probe_cache import ProbeCache

BASE_URL = "http://llm.test/v1"
MODEL_ID = "qwen/qwen3.5-9b"


def counting_transport(
    payload: object, status: int = 200, delay: float = 0.0
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    """A transport that answers one payload and records the requests it served."""
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if delay:
            await asyncio.sleep(delay)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler), calls


@pytest.mark.asyncio
async def test_a_serving_endpoint_is_reported_as_serving() -> None:
    """A 200 with a model list means the endpoint can serve a call."""
    transport, calls = counting_transport({"models": [{"id": MODEL_ID}]})

    result = await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert result.serving is True
    assert result.reported_model == MODEL_ID
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_the_openai_model_list_of_the_shipped_server_is_accepted() -> None:
    """The shipped llama.cpp answers its OpenAI route with a "data" list."""
    transport, _ = counting_transport({"object": "list", "data": [{"id": MODEL_ID}]})

    result = await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert result.serving is True
    assert result.reported_model == MODEL_ID


@pytest.mark.asyncio
async def test_the_real_body_of_the_shipped_server_yields_its_model_id() -> None:
    """The real answer of llama.cpp carries BOTH lists; the id must be found.

    The shipped server answers `/v1/models` with an OpenAI-style `data` array
    (entries carrying `id`) AND a `models` array (entries carrying `name` and
    `model`). A mock that only carries one of the two shapes cannot catch a
    probe that reads the wrong one.
    """
    real_body = {
        "models": [{"name": MODEL_ID, "model": MODEL_ID, "size": "7100518400"}],
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "owned_by": "llamacpp"}],
    }
    transport, _ = counting_transport(real_body)

    result = await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert result.serving is True
    assert result.reported_model == MODEL_ID


@pytest.mark.asyncio
async def test_a_body_with_only_the_models_list_yields_its_model_id() -> None:
    """An answer that carries only llama.cpp's own list still names the model."""
    transport, _ = counting_transport({"models": [{"name": MODEL_ID, "model": MODEL_ID}]})

    result = await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert result.serving is True
    assert result.reported_model == MODEL_ID


@pytest.mark.asyncio
async def test_an_empty_model_list_is_not_serving() -> None:
    """A server with no model loaded answers an empty list: it cannot serve."""
    transport, _ = counting_transport({"models": [], "object": "list", "data": []})

    result = await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert result.serving is False


@pytest.mark.asyncio
async def test_a_server_error_is_not_serving() -> None:
    """A 500 is not an answer, so the endpoint does not serve a call."""
    transport, _ = counting_transport({"error": "server error"}, status=500)

    result = await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert result.serving is False
    assert "500" in result.reason


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_is_not_serving() -> None:
    """An undecodable body is not an answer."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, text="<html>gateway error</html>")

    result = await probe_endpoint(BASE_URL, 1.0, transport=httpx.MockTransport(handler))

    assert result.serving is False
    assert "JSON" in result.reason


@pytest.mark.asyncio
async def test_a_body_without_a_model_list_is_not_serving() -> None:
    """A JSON body that lists no model is not an answer."""
    transport, _ = counting_transport({"object": "list"})

    result = await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert result.serving is False
    assert "model list" in result.reason


@pytest.mark.asyncio
async def test_a_transport_error_is_not_serving() -> None:
    """A refused connection is not an answer."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    result = await probe_endpoint(BASE_URL, 1.0, transport=httpx.MockTransport(handler))

    assert result.serving is False
    assert "connection refused" in result.reason


@pytest.mark.asyncio
async def test_a_timed_out_probe_is_not_serving_and_is_marked_as_a_timeout() -> None:
    """The caller needs to know that the endpoint was slow, not that it answered."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    result = await probe_endpoint(BASE_URL, 1.0, transport=httpx.MockTransport(handler))

    assert result.serving is False
    assert result.timed_out is True


@pytest.mark.asyncio
async def test_the_verdict_is_reused_for_the_ttl() -> None:
    """The second call in the window does not probe again."""
    transport, calls = counting_transport({"models": [{"id": MODEL_ID}]})

    first = await probe_endpoint(BASE_URL, 1.0, transport=transport)
    second = await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert first == second
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_concurrent_probes_of_one_url_issue_one_request() -> None:
    """A burst on the report path probes once, not once per request."""
    transport, calls = counting_transport({"models": [{"id": MODEL_ID}]}, delay=0.01)

    results = await asyncio.gather(
        *(probe_endpoint(BASE_URL, 1.0, transport=transport) for _ in range(5))
    )

    assert len(calls) == 1
    assert all(result.serving for result in results)


@pytest.mark.asyncio
async def test_invalidate_probe_forces_the_next_call_to_probe_again() -> None:
    """A caller that knows better than the cached verdict can drop it."""
    transport, calls = counting_transport({"models": [{"id": MODEL_ID}]})

    await probe_endpoint(BASE_URL, 1.0, transport=transport)
    invalidate_probe(BASE_URL)
    await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_writing_the_cache_drops_the_expired_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cache does not grow without bound while one endpoint stays down."""
    monkeypatch.setattr(llm_probe, "PROBE_TTL_SECONDS", 0.0)
    transport, _ = counting_transport({"models": [{"id": MODEL_ID}]})

    await probe_endpoint(BASE_URL, 1.0, transport=transport)
    await probe_endpoint("http://other.test/v1", 1.0, transport=transport)

    assert len(llm_probe._cache) == 1


@pytest.mark.asyncio
async def test_a_different_model_id_is_logged_at_warning(caplog: pytest.LogCaptureFixture) -> None:
    """The server naming another model than the one asked for is worth a warning."""
    transport, _ = counting_transport({"models": [{"id": "other/model"}]})

    with caplog.at_level(logging.WARNING, logger=llm_probe.__name__):
        result = await probe_endpoint(BASE_URL, 1.0, expected_model=MODEL_ID, transport=transport)

    assert result.serving is True
    assert "other/model" in caplog.text
    assert MODEL_ID in caplog.text


@pytest.mark.asyncio
async def test_the_same_model_id_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """The normal case stays quiet: the warning is for a mismatch."""
    transport, _ = counting_transport({"models": [{"id": MODEL_ID}]})

    with caplog.at_level(logging.WARNING, logger=llm_probe.__name__):
        await probe_endpoint(BASE_URL, 1.0, expected_model=MODEL_ID, transport=transport)

    assert caplog.text == ""


@pytest.mark.asyncio
async def test_the_probe_result_carries_no_model_id_when_the_server_names_none() -> None:
    """A model list without an id is still an answer, but it names no model."""
    transport, _ = counting_transport({"models": [{}]})

    result = await probe_endpoint(BASE_URL, 1.0, transport=transport)

    assert result == ProbeResult(serving=True, reported_model="")


def test_clear_probe_cache_forgets_every_verdict() -> None:
    """The tests start from an empty cache."""
    clear_probe_cache()

    assert len(llm_probe._cache) == 0


@pytest.mark.asyncio
async def test_a_probe_pending_on_another_event_loop_is_not_disturbed() -> None:
    """A pending probe of one loop is not overwritten by another loop's probe.

    The callers of the first loop keep sharing its probe, and none of them is
    left hanging: the future of a probe belongs to the loop that started it.
    """
    cache: ProbeCache[str] = ProbeCache(60.0)
    url = "http://peer.test/v1/models"
    started = threading.Event()
    release = threading.Event()
    join_second = threading.Event()
    probes = 0
    outcomes: list[list[str]] = []

    async def blocking_probe() -> str:
        nonlocal probes
        probes += 1
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return "first"

    async def failing_probe() -> str:
        nonlocal probes
        probes += 1
        raise RuntimeError("the probe failed")

    def run_on_another_loop() -> None:
        async def two_callers() -> list[str]:
            first = asyncio.create_task(cache.verdict(url, blocking_probe))
            while not started.is_set():
                await asyncio.sleep(0.01)
            while not join_second.is_set():
                await asyncio.sleep(0.01)
            second = asyncio.create_task(cache.verdict(url, blocking_probe))
            return [await first, await second]

        outcomes.append(asyncio.run(two_callers()))

    thread = threading.Thread(target=run_on_another_loop)
    thread.start()
    assert started.wait(timeout=5)

    # Another loop asks for the same URL while the first loop's probe is pending.
    # Its own probe fails, so no verdict is cached and the first loop's pending
    # probe is still the one the next caller of that loop has to join.
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(cache.verdict(url, failing_probe), timeout=2)

    join_second.set()
    await asyncio.sleep(0.05)
    release.set()
    thread.join(timeout=5)

    assert not thread.is_alive(), "a pending probe of another loop was left hanging"
    assert outcomes == [["first", "first"]]
    assert probes == 2, "the pending probe of the other loop was overwritten"
