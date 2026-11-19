"""The cache of probe verdicts: one verdict per endpoint URL, reused for a few seconds.

Input: a probed URL and the verdict of a probe.
Output: the cached verdict while it is valid.
Responsibility: hold the verdicts, expire them, and make sure that concurrent
probes of the same URL issue one request instead of one per caller.

The cache is a plain dict keyed by the probed URL: its entries are replaced,
never mutated, and no loop-bound primitive outlives its event loop — the
in-flight futures are dropped when the probe resolves, and they are kept per
event loop, so a probe pending on another loop is never overwritten and never
leaves its awaiters hanging.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

InflightKey = tuple[str, asyncio.AbstractEventLoop]
"""The URL and the event loop a pending probe belongs to."""


@dataclass(frozen=True)
class _Entry[Verdict]:
    """One cached verdict and the moment it stops being valid."""

    verdict: Verdict
    expires_at: float


class ProbeCache[Verdict]:
    """The verdicts of the probed URLs, with their expiry."""

    def __init__(self, ttl_seconds: float | Callable[[], float]) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, _Entry[Verdict]] = {}
        self._inflight: dict[InflightKey, asyncio.Future[Verdict]] = {}

    @property
    def ttl(self) -> float:
        """How long a verdict is reused, in seconds."""
        return self._ttl() if callable(self._ttl) else self._ttl

    def __len__(self) -> int:
        """How many verdicts are cached."""
        return len(self._entries)

    def get(self, url: str) -> Verdict | None:
        """The cached verdict of one URL, or None when there is none or it expired."""
        entry = self._entries.get(url)
        if entry is None or entry.expires_at <= time.monotonic():
            return None
        return entry.verdict

    def store(self, url: str, verdict: Verdict) -> None:
        """Cache one verdict, dropping the entries that expired meanwhile."""
        now = time.monotonic()
        for key in [key for key, entry in self._entries.items() if entry.expires_at <= now]:
            del self._entries[key]
        self._entries[url] = _Entry(verdict, now + self.ttl)

    def invalidate(self, url: str) -> None:
        """Forget the verdict of one URL, so the next call probes it again."""
        self._entries.pop(url, None)

    def clear(self) -> None:
        """Forget every verdict and every probe in flight."""
        self._entries.clear()
        self._inflight.clear()

    async def verdict(self, url: str, probe: Callable[[], Awaitable[Verdict]]) -> Verdict:
        """The verdict of one URL, probing it once for all the concurrent callers.

        The probe in flight is tracked per event loop: a caller on another loop
        starts its own probe instead of awaiting a future it may never be
        allowed to touch, and the pending future of that other loop is never
        overwritten, so its awaiters are never left hanging.
        """
        cached = self.get(url)
        if cached is not None:
            return cached
        loop = asyncio.get_running_loop()
        key = (url, loop)
        pending = self._inflight.get(key)
        if pending is not None and not pending.done():
            return await pending
        future: asyncio.Future[Verdict] = loop.create_future()
        self._prune()
        self._inflight[key] = future
        try:
            verdict = await probe()
        except BaseException as exc:
            self._release_failure(key, future, exc)
            raise
        self.store(url, verdict)
        self._release(key, future, verdict)
        return verdict

    def _prune(self) -> None:
        """Forget the probes that are already resolved."""
        for key in [key for key, future in self._inflight.items() if future.done()]:
            del self._inflight[key]

    def _release(self, key: InflightKey, future: asyncio.Future[Verdict], verdict: Verdict) -> None:
        """Publish a verdict to the callers that waited for it."""
        if not future.done():
            future.set_result(verdict)
        self._drop(key, future)

    def _release_failure(
        self, key: InflightKey, future: asyncio.Future[Verdict], failure: BaseException
    ) -> None:
        """Publish a failed probe to the callers that waited for it."""
        if not future.done():
            future.set_exception(failure)
            future.exception()  # retrieved here, so an unwatched future stays quiet
        self._drop(key, future)

    def _drop(self, key: InflightKey, future: asyncio.Future[Verdict]) -> None:
        """Stop tracking the probe of one URL."""
        if self._inflight.get(key) is future:
            self._inflight.pop(key, None)
