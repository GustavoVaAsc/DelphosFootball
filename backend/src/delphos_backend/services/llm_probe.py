"""Reachability probe for an inference endpoint.

Input: an endpoint base URL, a timeout in seconds, the model id that was
requested and an optional httpx transport.
Output: a `ProbeResult`: whether the endpoint is serving, why it is not when it
is not, and the model id the server reported.
Responsibility: answer "can this endpoint serve a call right now?" with one
cheap request, and remember the answer for a few seconds, so a burst of
requests does not re-probe the same endpoint and a dead primary is skipped in
seconds instead of after its own timeout.

An endpoint counts as SERVING only when it answers HTTP 200 with a JSON body
that carries a model list: the shipped llama.cpp answers its OpenAI-compatible
route with `{"object": "list", "data": [...]}`, and a body that reports a
`models` list is accepted as well. A transport error, a non-200, an undecodable
body and a body without a model list all mean "not serving", so the caller
uses the fallback.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from delphos_backend.services.llm_probe_cache import ProbeCache

logger = logging.getLogger(__name__)

_URL_IN_TEXT = re.compile(r"https?://\S+")

PROBE_TTL_SECONDS = 5.0
"""How long a probe verdict is reused before the endpoint is probed again."""


@dataclass(frozen=True)
class ProbeResult:
    """What the probe learned about one endpoint.

    `serving` is the verdict; `reason` says why the endpoint is not serving (a
    transport error, a status, an undecodable body) and `timed_out` marks the
    timeout case, which the caller reports differently. `reported_model` is the
    model id the server named, empty when it named none.
    """

    serving: bool
    reason: str = ""
    reported_model: str = ""
    timed_out: bool = False


_cache: ProbeCache[ProbeResult] = ProbeCache(lambda: PROBE_TTL_SECONDS)


async def probe_endpoint(
    base_url: str,
    timeout: float,
    expected_model: str = "",
    transport: httpx.AsyncBaseTransport | None = None,
) -> ProbeResult:
    """Whether the endpoint is serving, and why it is not when it is not.

    The verdict is reused for PROBE_TTL_SECONDS. Concurrent callers of a cold
    URL share one request: the first one probes, the others await its verdict.
    """
    url = f"{base_url.rstrip('/')}/models"
    return await _cache.verdict(url, lambda: _probe(url, timeout, expected_model, transport))


def invalidate_probe(base_url: str) -> None:
    """Forget the cached verdict of one endpoint, so the next call probes again."""
    _cache.invalidate(f"{base_url.rstrip('/')}/models")


def clear_probe_cache() -> None:
    """Forget every cached verdict; the tests call it between cases."""
    _cache.clear()


async def _probe(
    url: str,
    timeout: float,
    expected_model: str,
    transport: httpx.AsyncBaseTransport | None,
) -> ProbeResult:
    """Ask the endpoint for its model list and judge the answer."""
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            response = await client.get(url)
    except httpx.TimeoutException as exc:
        return ProbeResult(False, f"the probe timed out ({_reason(exc)})", timed_out=True)
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        return ProbeResult(False, f"the endpoint did not answer ({_reason(exc)})")
    if response.status_code != 200:
        return ProbeResult(False, f"the endpoint answered HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        return ProbeResult(False, f"the answer is not JSON ({type(exc).__name__})")
    models = _model_list(body)
    if models is None:
        return ProbeResult(False, "the answer carries no model list")
    reported = _first_model_id(models)
    if reported and expected_model and reported != expected_model:
        logger.warning(
            "The inference endpoint serves model %s, but %s was requested",
            reported,
            expected_model,
        )
    return ProbeResult(True, "", reported)


def _reason(exc: Exception) -> str:
    """The exception's class name and detail, with any URL removed.

    The detail is what makes the reason useful ("connection refused"), but an
    httpx message can embed the request URL, and the endpoint URL must never
    reach a log or an error body.
    """
    text = _URL_IN_TEXT.sub("<url>", str(exc))
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def _model_list(body: object) -> list[object] | None:
    """The model list the answer carries, or None when it carries none.

    The shipped llama.cpp answers `/v1/models` with both an OpenAI-style `data`
    array (whose entries carry `id`) and a `models` array (whose entries carry
    `name` and `model`), so the OpenAI array is read first. A native
    `/models` answer is a top-level list. An EMPTY list means no model is
    loaded, which is not a serving endpoint.
    """
    if isinstance(body, list):
        return body or None
    if not isinstance(body, dict):
        return None
    for key in ("data", "models"):
        value = body.get(key)
        if isinstance(value, list) and value:
            return value
    return None


def _first_model_id(models: list[object]) -> str:
    """The id of the first model the answer names, empty when it names none.

    The identifier is read from `id` first, then `name`, then `model`: the
    OpenAI shape uses `id`, while llama.cpp's own array uses `name`.
    """
    for entry in models:
        if not isinstance(entry, dict):
            continue
        for key in ("id", "name", "model"):
            identifier = entry.get(key)
            if isinstance(identifier, str) and identifier:
                return identifier
    return ""
