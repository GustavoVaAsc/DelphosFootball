"""One report's chain of completions, served wholly by one endpoint.

Input: the endpoint the chain starts on, the settings, an optional transport and
the function that posts one completion.
Output: the `CompletionResult` of each call of the chain.
Responsibility: keep the prose of one report on one endpoint. The chain starts
on the endpoint that was resolved for it, hands its first call over to the peer
when that endpoint fails outright — nothing has been produced yet, so no prose
is composed of two models — and pins every later call to the endpoint that
served the previous one. A draft served by the fallback therefore has its
repair served by the fallback too, and the stored model id describes the whole
text (ADR-033).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from delphos_backend.core.config import Settings
from delphos_backend.services.llm_choice import peer_target
from delphos_backend.services.llm_protocol import CompletionResult, InferenceError
from delphos_backend.services.llm_request import InferenceTarget
from delphos_backend.services.llm_targets import target_for_kind

logger = logging.getLogger(__name__)

CompletionCall = Callable[..., Awaitable[CompletionResult]]
"""Posts one completion to one endpoint."""


class EndpointChain:
    """The chain of completions of one report, served by one endpoint."""

    def __init__(
        self,
        target: InferenceTarget,
        cfg: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
        call: CompletionCall | None = None,
    ) -> None:
        """The chain starts on `target`; `call` posts one completion to one endpoint."""
        self._target = target
        self._cfg = cfg
        self._transport = transport
        self._call = call
        self._served = False

    @property
    def target(self) -> InferenceTarget:
        """The endpoint the next call of the chain goes to."""
        return self._target

    async def complete(self, messages: list[dict[str, Any]], **options: Any) -> CompletionResult:
        """One completion of the chain, on the chain's endpoint.

        The first call may hand over to the peer when the endpoint fails
        outright; a later call may not, because the prose of the report exists
        by then and must come from one endpoint.
        """
        try:
            result = await self._post(messages, self._target, options)
        except InferenceError:
            if self._served:
                raise
            peer, _ = await peer_target(self._cfg, self._target, self._transport)
            if peer is None:
                raise
            logger.warning(
                "The %s inference endpoint failed; the %s endpoint serves the report",
                self._target.kind,
                peer.kind,
            )
            result = await self._post(messages, peer, options)
            self._target = peer
        self._served = True
        pinned = target_for_kind(self._cfg, result.endpoint)
        if pinned is not None:
            self._target = pinned
        return result

    async def _post(
        self, messages: list[dict[str, Any]], target: InferenceTarget, options: dict[str, Any]
    ) -> CompletionResult:
        """Post one completion to one endpoint of the chain."""
        if self._call is None:
            raise InferenceError("the report chain has no completion function")
        return await self._call(
            messages,
            settings=self._cfg,
            transport=self._transport,
            target=target,
            **options,
        )
