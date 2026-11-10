"""Typed read-only tools for the conversational scouting agent.

Input: tool name, model-supplied arguments, the active model_run_id, and a
connection factory.
Output: a JSON payload for the model — the capped result, an empty result for
an unknown entity, or a structured {"error": {...}} the model can read and retry.
Responsibility: dispatch to the query executors, map unknown tool names and
execution failures onto typed errors instead of exceptions, and enforce the
per-result JSON bound (LLM_PLAN §10.2). The connection is opened per tool
execution, so a slow model turn never holds a pooled connection. Validation
lives in chat_tool_args and the queries in chat_tool_queries; this module is
the failure-mapping surface.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from delphos_backend.services.chat_conn import ConnectionFactory
from delphos_backend.services.chat_tool_args import MAX_RESULT_CHARS
from delphos_backend.services.chat_tool_queries import TOOL_HANDLERS
from delphos_backend.services.chat_tool_summary import safe_tool_name

logger = logging.getLogger(__name__)

TOOL_NAMES: tuple[str, ...] = tuple(TOOL_HANDLERS)


async def execute_tool(
    conn_factory: ConnectionFactory, model_run_id: str, name: str, arguments: Any
) -> dict[str, Any]:
    """Run one tool; never raises for model-caused problems or tool failures."""
    if name not in TOOL_HANDLERS:
        return {
            "error": {
                "tool": name,
                "message": "herramienta desconocida",
                "available_tools": list(TOOL_NAMES),
            }
        }
    args = arguments if isinstance(arguments, dict) else {}
    try:
        async with conn_factory() as conn:
            payload = await TOOL_HANDLERS[name](conn, model_run_id, args)
    except Exception as exc:
        # The tool name is model-controlled: it is sanitised before it reaches
        # the log, and the failure is reported structurally (type, not text).
        logger.error(
            "Chat tool execution failed",
            extra={
                "chat_tool": safe_tool_name(name),
                "chat_model_run_id": model_run_id,
                "chat_error_type": type(exc).__name__,
            },
            exc_info=True,
        )
        return {"error": {"tool": name, "message": "la herramienta falló al ejecutarse"}}
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) > MAX_RESULT_CHARS:
        # An oversized result is a failure, not a success: the model must narrow
        # the query instead of reasoning over a half-parsed JSON fragment.
        return {
            "error": {
                "tool": name,
                "message": "el resultado es demasiado grande; acota la consulta",
                "truncated": True,
                "preview": text[:MAX_RESULT_CHARS],
            }
        }
    return payload
