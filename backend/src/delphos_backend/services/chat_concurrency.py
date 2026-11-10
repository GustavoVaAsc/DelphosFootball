"""Concurrency guard for the chat path's LLM calls.

Input: the active Settings (or an explicit limit).
Output: an asyncio.Semaphore bounding the number of in-flight LLM calls.
Responsibility: cap concurrent chat completions at the inference server's
parallel-slot count (LLAMA_ARG_N_PARALLEL, 4 in docker-compose.yml), so a burst
of chat requests queues instead of saturating the GPU. The cap is
`Settings.llm_max_concurrent_llm_calls`, so it is configured like every other
knob (environment variable or .env). The semaphores are cached per event loop
because asyncio primitives bind to the loop that first awaits them, and the API
is served by one loop per process while the tests run one loop per test.
"""

from __future__ import annotations

import asyncio
import weakref

from delphos_backend.core.config import Settings

DEFAULT_MAX_CONCURRENT_LLM_CALLS = 4

_semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[int, asyncio.Semaphore]] = (
    weakref.WeakKeyDictionary()
)


def llm_call_limit(settings: Settings) -> int:
    """The configured concurrency cap, defaulting to the server's slot count.

    The limit comes from `Settings.llm_max_concurrent_llm_calls`, so it is set
    like every other knob (environment variable or .env). The attribute is read
    defensively because the chat tests hand the loop a stand-in settings object.
    """
    raw = getattr(settings, "llm_max_concurrent_llm_calls", None)
    if raw is None:
        return DEFAULT_MAX_CONCURRENT_LLM_CALLS
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_CONCURRENT_LLM_CALLS
    return max(1, limit)


def llm_call_semaphore(settings: Settings) -> asyncio.Semaphore:
    """The semaphore bounding LLM calls for the running loop and the configured limit."""
    limit = llm_call_limit(settings)
    loop = asyncio.get_running_loop()
    per_limit = _semaphores.setdefault(loop, {})
    semaphore = per_limit.get(limit)
    if semaphore is None:
        semaphore = asyncio.Semaphore(limit)
        per_limit[limit] = semaphore
    return semaphore
