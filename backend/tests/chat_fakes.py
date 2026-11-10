"""Shared fakes for the chat tests: connection factories that track their usage."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class TrackingConnectionFactory:
    """A connection factory that records how many connections are open at once.

    The chat tools open one connection per execution, so `active` must be zero
    while the model is thinking: a non-zero value during an LLM wait means a
    pooled connection is being held across the request.
    """

    def __init__(self, conn: Any) -> None:
        self.conn = conn
        self.active = 0
        self.peak = 0

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[Any]:
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            yield self.conn
        finally:
            self.active -= 1

    def __call__(self) -> Any:
        return self._connection()


def simple_factory(conn: Any) -> Any:
    """A connection factory that always yields the same connection."""

    @asynccontextmanager
    async def _connection() -> AsyncIterator[Any]:
        yield conn

    return _connection
