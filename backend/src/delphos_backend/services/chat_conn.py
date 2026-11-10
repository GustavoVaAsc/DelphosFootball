"""Connection-factory contract for the chat tool layer.

Input: a callable supplied by the API layer.
Output: an async context manager that yields a pooled AsyncConnection.
Responsibility: let the chat tools open a connection per tool execution instead
of holding one for the whole turn, so a multi-minute LLM wait never occupies a
slot of the shared connection pool (the pool has ten slots and the API is
unauthenticated).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from psycopg import AsyncConnection

ConnectionFactory = Callable[[], AbstractAsyncContextManager[AsyncConnection]]
