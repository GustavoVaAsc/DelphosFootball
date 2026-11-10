"""Shared harness for the LLM experiments: requests, calls, recording, preflight, DB.

Input: chat messages plus sampling options; `DELPHOS_LLM_*` / `DELPHOS_DB_*` environment
variables (defaults mirrored from `backend/src/delphos_backend/core/config.py`); the
llama.cpp OpenAI-compatible API at the configured base URL.
Output: a request body, a parsed `CompletionResult` (content, usage, `timings`, raw JSON),
one JSONL row per call under `<repo root>/analysis/output/llm/<experiment>.jsonl`, a
preflight verdict over `GET /health` and `GET /props`, and the read-only PostgreSQL
access both case sets resolve against.
Responsibility: be the single place an experiment touches the network, the filesystem and
the database, so every call carries an explicit `seed` (LLM_PLAN §17: without it two runs
of the same config differ by sampling noise) and every failure exits with an actionable
message instead of a traceback.

These concerns share one module because they are one concept — the experiment's single
edge to the outside world — and splitting four tightly coupled helpers into files would
obscure that every call goes through here. Experiment scripts (E1–E9) and the case sets
import from this module rather than each other by path (`analysis/llm_eval/` is a package).
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import quote_plus

import httpx
import psycopg

from delphos_ml.config import find_project_root

# Defaults mirror backend/src/delphos_backend/core/config.py (Settings field -> env var
# DELPHOS_<FIELD>): llm_api_url, llm_model_name, llm_timeout_seconds, llm_temperature,
# llm_top_p, llm_top_k, llm_presence_penalty, llm_enable_thinking, llm_max_tokens.
DEFAULT_LLM_API_URL = "http://inference-chat:8080/v1"
DEFAULT_LLM_MODEL_NAME = "qwen/qwen3.5-9b"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.8
DEFAULT_TOP_K = 20
DEFAULT_PRESENCE_PENALTY = 0.0
DEFAULT_ENABLE_THINKING = False
DEFAULT_MAX_TOKENS = 512

PREFLIGHT_TIMEOUT_SECONDS = 5.0
"""Health and props must answer fast; never wait the full generation timeout for them."""


class HarnessError(Exception):
    """A server payload, environment value, or harness precondition is invalid."""


@dataclass(frozen=True)
class HarnessConfig:
    """Resolved harness settings: endpoint plus the shipped sampling defaults."""

    base_url: str
    model: str
    timeout_seconds: float
    temperature: float
    top_p: float
    top_k: int
    presence_penalty: float
    enable_thinking: bool
    max_tokens: int


def fail(reason: str, *, script: str) -> NoReturn:
    """Exit 1 with the pipeline's `<script> failed: <reason>` line on stderr (no traceback)."""
    print(f"{script} failed: {reason}", file=sys.stderr)
    raise SystemExit(1)


def _env_number(name: str, default: float, cast: Callable) -> Any:
    """Read one env var as int/float, raising HarnessError naming the offending value."""
    text = os.environ.get(name)
    if text is None or text == "":
        return cast(default)
    try:
        return cast(text)
    except ValueError as exc:
        raise HarnessError(f"{name}={text!r} is not a valid {cast.__name__}") from exc


def load_config() -> HarnessConfig:
    """Resolve the harness settings from `DELPHOS_LLM_*` env vars (backend defaults)."""
    return HarnessConfig(
        base_url=os.environ.get("DELPHOS_LLM_API_URL", DEFAULT_LLM_API_URL).rstrip("/"),
        model=os.environ.get("DELPHOS_LLM_MODEL_NAME", DEFAULT_LLM_MODEL_NAME),
        timeout_seconds=_env_number("DELPHOS_LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, float),
        temperature=_env_number("DELPHOS_LLM_TEMPERATURE", DEFAULT_TEMPERATURE, float),
        top_p=_env_number("DELPHOS_LLM_TOP_P", DEFAULT_TOP_P, float),
        top_k=_env_number("DELPHOS_LLM_TOP_K", DEFAULT_TOP_K, int),
        presence_penalty=_env_number(
            "DELPHOS_LLM_PRESENCE_PENALTY", DEFAULT_PRESENCE_PENALTY, float
        ),
        enable_thinking=_env_enable_thinking(),
        max_tokens=_env_number("DELPHOS_LLM_MAX_TOKENS", DEFAULT_MAX_TOKENS, int),
    )


def _env_enable_thinking() -> bool:
    """Parse `DELPHOS_LLM_ENABLE_THINKING` the way pydantic-settings parses booleans."""
    text = os.environ.get("DELPHOS_LLM_ENABLE_THINKING")
    if text is None or text == "":
        return DEFAULT_ENABLE_THINKING
    lowered = text.strip().lower()
    if lowered in ("true", "1", "yes", "on"):
        return True
    if lowered in ("false", "0", "no", "off"):
        return False
    raise HarnessError(f"DELPHOS_LLM_ENABLE_THINKING={text!r} is not a boolean")


def build_request(
    messages: list[dict[str, Any]],
    *,
    seed: int,
    config: HarnessConfig | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    presence_penalty: float | None = None,
    enable_thinking: bool | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one llama.cpp `/chat/completions` body.

    `seed` is mandatory (keyword-only): a request without an explicit seed makes every
    comparison in LLM_PLAN §17 a sampling-noise confound, so there is no default to omit.
    Any of the sampling knobs defaults to `config` (env-backed); `tools` and
    `response_format` are added only when supplied.
    """
    if not messages:
        raise HarnessError("build_request needs at least one message")
    cfg = config or load_config()
    body: dict[str, Any] = {
        "model": model if model is not None else cfg.model,
        "messages": messages,
        "max_tokens": max_tokens if max_tokens is not None else cfg.max_tokens,
        "temperature": temperature if temperature is not None else cfg.temperature,
        "top_p": top_p if top_p is not None else cfg.top_p,
        "top_k": top_k if top_k is not None else cfg.top_k,  # llama.cpp extension
        "presence_penalty": (
            presence_penalty if presence_penalty is not None else cfg.presence_penalty
        ),
        "stream": False,
        "seed": seed,
        "chat_template_kwargs": {
            "enable_thinking": (
                enable_thinking if enable_thinking is not None else cfg.enable_thinking
            )
        },
    }
    if tools is not None:
        body["tools"] = tools
    if response_format is not None:
        body["response_format"] = response_format
    return body


@dataclass(frozen=True)
class CompletionResult:
    """One parsed completion: what the model said, plus the server's accounting."""

    content: str
    reasoning: str | None
    model: str
    usage: dict[str, Any]
    timings: dict[str, Any]
    raw: dict[str, Any]


def parse_completion(data: Any, *, default_model: str = "") -> CompletionResult:
    """Turn a decoded response body into a CompletionResult; raise HarnessError if malformed."""
    if not isinstance(data, dict):
        raise HarnessError(f"unexpected completion payload type: {type(data).__name__}")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HarnessError("completion payload has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise HarnessError("completion payload has a malformed choice")
    message = first.get("message")
    if not isinstance(message, dict):
        raise HarnessError("completion choice has no message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HarnessError("completion returned empty content")
    reasoning = message.get("reasoning_content")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    timings = data.get("timings") if isinstance(data.get("timings"), dict) else {}
    for field_name, value in (("usage", usage), ("timings", timings)):
        if value and not isinstance(value, dict):
            raise HarnessError(f"completion payload has a malformed {field_name}")
    return CompletionResult(
        content=content,
        reasoning=reasoning if isinstance(reasoning, str) else None,
        model=str(data.get("model") or default_model),
        usage=usage,
        timings=timings,
        raw=data,
    )


def call_server(
    request: dict[str, Any],
    *,
    config: HarnessConfig | None = None,
    transport: httpx.BaseTransport | None = None,
) -> CompletionResult:
    """POST one non-streaming chat completion; raise HarnessError on any failure.

    `transport` exists for tests (httpx.MockTransport); experiments call the real server.
    """
    cfg = config or load_config()
    endpoint = f"{cfg.base_url}/chat/completions"
    try:
        with httpx.Client(timeout=cfg.timeout_seconds, transport=transport) as client:
            response = client.post(endpoint, json=request)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise HarnessError(
            f"inference server timed out after {cfg.timeout_seconds:g}s at {endpoint}"
        ) from exc
    except httpx.HTTPError as exc:
        raise HarnessError(f"inference server call failed at {endpoint}: {exc}") from exc
    except ValueError as exc:  # httpx raises JSONDecodeError (a ValueError) on bad JSON
        raise HarnessError(
            f"inference server returned malformed JSON at {endpoint}: {exc}"
        ) from exc
    return parse_completion(data, default_model=cfg.model)


def server_root(base_url: str) -> str:
    """The llama.cpp server root for a base URL: `/health` and `/props` live outside `/v1`."""
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        trimmed = trimmed[: -len("/v1")]
    return trimmed


def preflight(base_url: str | None = None) -> dict[str, Any]:
    """Verify the inference server is reachable and the model is loaded; exit if not.

    Checks `GET /health` (200 = model loaded; 503 = server up but not loaded) and
    `GET /props` (reports the loaded model). On any failure: one actionable line on
    stderr and `SystemExit(1)` — never a traceback, never a partial experiment run.
    Returns the decoded `/props` payload so callers can record it.
    """
    cfg_url = base_url if base_url is not None else load_config().base_url
    root = server_root(cfg_url)
    try:
        with httpx.Client(timeout=PREFLIGHT_TIMEOUT_SECONDS) as client:
            health = client.get(f"{root}/health")
            if health.status_code != 200:
                fail(
                    f"{root}/health returned HTTP {health.status_code}: the server is "
                    "reachable but the model is not loaded — check LLAMA_ARG_MODEL points "
                    "at an existing GGUF (LLM_PLAN §6.1). No requests were sent.",
                    script="preflight",
                )
            props_response = client.get(f"{root}/props")
            if props_response.status_code != 200:
                fail(
                    f"{root}/props returned HTTP {props_response.status_code} after a healthy "
                    "/health. Inspect the llama-server log. No requests were sent.",
                    script="preflight",
                )
            try:
                props = props_response.json()
            except ValueError as exc:
                fail(
                    f"{root}/props returned malformed JSON ({exc}): the server is not a "
                    "healthy llama.cpp instance. No requests were sent.",
                    script="preflight",
                )
    except httpx.HTTPError as exc:
        fail(
            f"inference server unreachable at {root} "
            f"({type(exc).__name__}: {exc}). Start it with `docker compose up inference-chat` "
            "(LLM_PLAN §6.1) or point DELPHOS_LLM_API_URL at a running llama.cpp server. "
            "No requests were sent.",
            script="preflight",
        )
    if not isinstance(props, dict) or not (
        props.get("model_info") or props.get("default_generation_settings")
    ):
        fail(
            f"{root}/props answered without model_info: the server is listening but no model "
            "is loaded (LLM_PLAN §6.3). No requests were sent.",
            script="preflight",
        )
    return props


def output_dir() -> Path:
    """`<repo root>/analysis/output/llm/` (gitignored via the analysis/output rule)."""
    return repo_root() / "analysis" / "output" / "llm"


def repo_root() -> Path:
    """The repository root: the parent of the uv project (`ml/`) holding `uv.lock`."""
    project_root = find_project_root()
    return project_root.parent if project_root is not None else Path.cwd()


def backend_import(module: str, script: str) -> Any:
    """Import a `delphos_backend.*` module from source; backend/ is its own uv project.

    The experiments measure the shipped configuration: prompts, the draft schema, the
    renderers, the numeric verifier and the tool executors are imported from
    `backend/src` rather than copied into analysis/. On failure the run exits with
    `<script> failed: ...` — never an ImportError traceback mid-run.
    """
    backend_src = repo_root() / "backend" / "src"
    if not (backend_src / "delphos_backend").is_dir():
        fail(f"backend sources not found at {backend_src}", script=script)
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        fail(f"cannot import {module} from {backend_src}: {exc}", script=script)


def record(experiment: str, row: dict[str, Any]) -> Path:
    """Append one JSONL row to `<output dir>/<experiment>.jsonl`; return the file path."""
    if not experiment or "/" in experiment or "\\" in experiment:
        raise HarnessError(f"experiment name must be a plain identifier, got {experiment!r}")
    target = output_dir() / f"{experiment}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return target


def build_row(
    request: dict[str, Any],
    result: CompletionResult,
    *,
    experiment: str,
    case_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the JSONL row for one call: seed, params, usage, timings, and the raw JSON."""
    row: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "experiment": experiment,
        "case_id": case_id,
        "seed": request.get("seed"),
        "params": {
            "model": request.get("model"),
            "temperature": request.get("temperature"),
            "top_p": request.get("top_p"),
            "top_k": request.get("top_k"),
            "presence_penalty": request.get("presence_penalty"),
            "max_tokens": request.get("max_tokens"),
            "enable_thinking": (request.get("chat_template_kwargs") or {}).get("enable_thinking"),
        },
        "usage": result.usage,
        "timings": result.timings,
        "response": {"content": result.content, "model": result.model},
        "raw": result.raw,
    }
    if extra:
        row.update(extra)
    return row


# --- Read-only database access shared by both case sets -----------------------------


def database_url() -> str:
    """PostgreSQL URL for the app role (reads `analytics`), from env or backend defaults.

    `DELPHOS_APP_DATABASE_URL` wins when set (its `postgresql+psycopg://` scheme prefix is
    stripped, as the backend does); otherwise the URL is composed from `DELPHOS_DB_HOST`,
    `DELPHOS_DB_PORT`, `DELPHOS_DB_NAME`, `DELPHOS_APP_DB_USER` and `DELPHOS_APP_DB_PASSWORD`
    — the same env names `core/config.py` reads.
    """
    explicit = os.environ.get("DELPHOS_APP_DATABASE_URL")
    if explicit:
        return explicit.replace("postgresql+psycopg://", "postgresql://")
    host = os.environ.get("DELPHOS_DB_HOST", "localhost")
    port = os.environ.get("DELPHOS_DB_PORT", "5432")
    name = os.environ.get("DELPHOS_DB_NAME", "delphos")
    user = quote_plus(os.environ.get("DELPHOS_APP_DB_USER", "delphos_app_user"))
    password = quote_plus(os.environ.get("DELPHOS_APP_DB_PASSWORD", "delphos_app_user_secret"))
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def connect_readonly(script: str) -> psycopg.Connection:
    """Open a session that refuses writes; exit with `<script> failed: ...` if unreachable."""
    try:
        conn = psycopg.connect(database_url(), options="-c default_transaction_read_only=on")
    except psycopg.Error as exc:
        fail(
            f"database unreachable ({type(exc).__name__}: {exc}). Start PostgreSQL "
            "`docker compose up db` and publish a model run (`delphos-pipeline publish`), "
            "or set DELPHOS_APP_DATABASE_URL. Nothing was queried.",
            script=script,
        )
    return conn


async def connect_readonly_async(script: str) -> psycopg.AsyncConnection:
    """Async twin of `connect_readonly` for the shipped repositories and tool executors."""
    try:
        return await psycopg.AsyncConnection.connect(
            database_url(), options="-c default_transaction_read_only=on"
        )
    except psycopg.Error as exc:
        fail(
            f"database unreachable ({type(exc).__name__}: {exc}). Start PostgreSQL "
            "`docker compose up db` and publish a model run (`delphos-pipeline publish`), "
            "or set DELPHOS_APP_DATABASE_URL. Nothing was queried.",
            script=script,
        )


def active_run_id(conn: psycopg.Connection, script: str) -> str:
    """Return the active model_run_id; exit with `<script> failed: ...` when none is active."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT model_run_id FROM analytics.model_runs
            WHERE status = 'active'
            ORDER BY activated_at DESC NULLS LAST
            LIMIT 1;
            """
        )
        row = cur.fetchone()
    if row is None:
        fail(
            "no active model run in analytics.model_runs — run `delphos-pipeline publish` "
            "before resolving cases.",
            script=script,
        )
    return str(row[0])
