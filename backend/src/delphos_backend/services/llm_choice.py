"""Which of the two endpoints serves a call.

Input: the settings, an optional httpx transport and, for a handover, the
endpoint that just failed.
Output: the `InferenceTarget` that serves the next call, and the error of a
request that found no endpoint willing to serve it.
Responsibility: decide which endpoint serves a turn. The decision is made once,
before the answer of that call exists, and it is pinned for the whole turn: a
turn is never composed of two models' output, and the database tool results of
a chat turn never cross to the peer mid-turn (ADR-033).

Both endpoints are probed before they are used, so a dead or wrong address
never receives a prompt: the probe is one cheap `GET {base}/models` that carries
no prompt and no credential.
"""

from __future__ import annotations

import logging

import httpx

from delphos_backend.core.config import Settings
from delphos_backend.services.llm_endpoint import endpoint_label
from delphos_backend.services.llm_probe import ProbeResult
from delphos_backend.services.llm_protocol import (
    FALLBACK_ENDPOINT,
    PRIMARY_ENDPOINT,
    InferenceError,
    InferenceTimeout,
)
from delphos_backend.services.llm_readiness import Readiness, endpoint_ready
from delphos_backend.services.llm_request import InferenceTarget
from delphos_backend.services.llm_targets import fallback_target, primary_target, target_for_kind

logger = logging.getLogger(__name__)


async def decide_target(
    cfg: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> tuple[InferenceTarget, ProbeResult | None]:
    """The endpoint that serves the next turn, and the probe's verdict on the primary.

    Without a fallback the primary always answers, exactly as it did before the
    feature existed: no probe, no extra request. With one, the primary is
    probed and an endpoint that is not serving is skipped without paying its
    timeout. The fallback is probed too, and it is used only when its probe
    says it is serving.
    """
    primary = primary_target(cfg)
    fallback = fallback_target(cfg)
    if fallback is None:
        return primary, None
    readiness = await endpoint_ready(cfg, primary, transport)
    if readiness.ready:
        return primary, readiness.probe
    fallback_readiness = await endpoint_ready(cfg, fallback, transport)
    if not fallback_readiness.ready:
        raise _no_endpoint_serves(readiness, fallback_readiness)
    logger.warning(
        "The primary inference endpoint %s is unreachable (%s); the fallback %s serves the turn",
        endpoint_label(primary.base_url),
        readiness.probe.reason,
        endpoint_label(fallback.base_url),
    )
    return fallback, readiness.probe


async def resolve_target(
    cfg: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> InferenceTarget:
    """The endpoint that serves the next turn."""
    target, _ = await decide_target(cfg, transport)
    return target


async def peer_target(
    cfg: Settings, current: InferenceTarget, transport: httpx.AsyncBaseTransport | None = None
) -> tuple[InferenceTarget | None, InferenceError | None]:
    """The other endpoint when it may serve a call, and why it may not.

    This is the handover of a chain that has produced no prose yet: the peer is
    probed before it is given anything.
    """
    peer_kind = FALLBACK_ENDPOINT if current.kind == PRIMARY_ENDPOINT else PRIMARY_ENDPOINT
    peer = target_for_kind(cfg, peer_kind)
    if peer is None:
        return None, None
    readiness = await endpoint_ready(cfg, peer, transport)
    if readiness.ready:
        return peer, None
    if readiness.probe.timed_out:
        return None, InferenceTimeout(
            f"the {peer_kind} endpoint did not answer the probe: {readiness.reason}"
        )
    return None, InferenceError(f"the {peer_kind} endpoint may not serve ({readiness.reason})")


def _no_endpoint_serves(primary: Readiness, fallback: Readiness) -> InferenceError:
    """The error of a request that found no endpoint willing to serve it."""
    message = (
        "LLM call failed: the primary endpoint is unreachable "
        f"({primary.probe.reason}) and the fallback endpoint may not serve "
        f"({fallback.reason})"
    )
    if primary.probe.timed_out and fallback.probe.timed_out:
        return InferenceTimeout(message)
    return InferenceError(message)
