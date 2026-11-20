"""Whether a configured endpoint may serve a call right now.

Input: the settings, an endpoint target and an optional httpx transport.
Output: a `Readiness`: whether the endpoint may serve, the probe's verdict, and
why it may not.
Responsibility: judge one endpoint with its reachability probe and the rules
that go with it. The fallback's served model id must match the configured one,
or the fallback is refused: a peer that silently serves another model would
have the club read prose from a model nobody chose. A fallback that names this
host's own published address is warned about, because it is a second path to
the same process and buys no availability (ADR-033).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from delphos_backend.core.config import Settings
from delphos_backend.services.llm_endpoint import endpoint_label
from delphos_backend.services.llm_probe import ProbeResult, probe_endpoint
from delphos_backend.services.llm_protocol import FALLBACK_ENDPOINT, PRIMARY_ENDPOINT
from delphos_backend.services.llm_request import InferenceTarget

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Readiness:
    """Whether an endpoint may serve a call, and what the probe found."""

    ready: bool
    probe: ProbeResult
    reason: str = ""


async def endpoint_ready(
    cfg: Settings, target: InferenceTarget, transport: httpx.AsyncBaseTransport | None = None
) -> Readiness:
    """Whether the target may serve a call right now.

    The probe is the same cheap `GET {base}/models` for every endpoint, and the
    verdict is cached for a few seconds. The probe never carries a prompt and no
    credential, so an endpoint that cannot answer it never receives either.
    """
    if target.kind == FALLBACK_ENDPOINT:
        warn_on_own_address(cfg, target)
    expected = target.model_id if target.kind == PRIMARY_ENDPOINT else ""
    probe = await probe_endpoint(
        target.base_url,
        cfg.llm_primary_probe_seconds,
        expected_model=expected,
        transport=transport,
    )
    if not probe.serving:
        return Readiness(False, probe, probe.reason)
    if target.kind == FALLBACK_ENDPOINT:
        problem = fallback_model_problem(cfg, probe)
        if problem:
            return Readiness(False, probe, problem)
    return Readiness(True, probe)


def fallback_model_problem(cfg: Settings, probe: ProbeResult) -> str:
    """Why the fallback's served model id is not the configured one, or "".

    The expected id is the configured `llm_fallback_model_name`, or the
    primary's id when that one is empty. The comparison is always strict: a
    peer that serves another model is refused, never warned about, because
    its prose would otherwise be stored as the club's model output. An
    operator who wants a peer with a different model sets the name.
    """
    configured = cfg.llm_fallback_model_name.strip() or cfg.llm_model_name.strip()
    if probe.reported_model == configured:
        return ""
    logger.warning(
        "The fallback endpoint %s serves model %s, but %s is expected; the fallback is refused",
        endpoint_label(cfg.llm_fallback_api_url),
        probe.reported_model or "no model",
        configured,
    )
    return f"the fallback serves model {probe.reported_model or 'none'}, not {configured}"


_WARNED_OWN_ADDRESSES: set[str] = set()
"""The labels already warned about, so the warning is logged once each."""


def warn_on_own_address(cfg: Settings, target: InferenceTarget) -> None:
    """Warn when the fallback is this host's own published inference address.

    The team wants a backend on this box to be able to consume this box's
    server, so the address is allowed; the warning says what it costs. It is
    logged once per address: the start-up warning already says it, and a line
    per request would bury it.
    """
    publish_ip = cfg.inference_publish_ip.strip()
    if not publish_ip:
        return
    host = urlsplit(target.base_url).hostname or ""
    if host != publish_ip:
        return
    label = endpoint_label(target.base_url)
    if label in _WARNED_OWN_ADDRESSES:
        return
    _WARNED_OWN_ADDRESSES.add(label)
    logger.warning(
        "The fallback endpoint %s is this host's own published inference address: it is a "
        "second path to the same process and provides no availability guarantee",
        label,
    )
