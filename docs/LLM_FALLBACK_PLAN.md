# LLM fallback over a remote llama.cpp server (ZeroTier)

Feature-scoped design document. Companion to [LLM_PLAN.md](LLM_PLAN.md), which
describes the report and chat features this builds on. This document is the
working plan; the decisions it produces belong in
[ARCHITECTURE.md](ARCHITECTURE.md) §10 once implemented.

Status: **specification, not implemented.** Written to survive a conversation
compaction, so it is self-contained about the code it builds on.

---

## Contents

1. [Purpose](#1-purpose)
2. [What exists today](#2-what-exists-today)
3. [The problem](#3-the-problem)
4. [Reachability: ZeroTier from a Docker container](#4-reachability-zerotier-from-a-docker-container)
5. [Application change: the fallback](#5-application-change-the-fallback)
6. [Open decisions](#6-open-decisions)
7. [Security](#7-security)
8. [Tests](#8-tests)
9. [Work order](#9-work-order)
10. [See also](#10-see-also)

---

## 1. Purpose

The backend talks to exactly one llama.cpp server today: the `inference-chat`
container in `docker-compose.yml`. If that container is down, or the host has no
GPU, the LLM path is unavailable — reports fall back to the deterministic
renderer (a 200 with `source="deterministic"`) and `/chat` returns 503.

The goal is a **second, remote inference endpoint reached over a ZeroTier
network**, used automatically when the local one is unavailable. ZeroTier gives
the host a virtual interface with its own IP, so a llama.cpp server on another
machine is reachable as if it were on the LAN.

This is a resilience feature. It does not change the report contract (200 with a
report in every case), the chat contract, the tool layer, or the vocabulary.

## 2. What exists today

Read these before implementing. All of it landed on branch
`feat/backend/llm-reports-and-chat`.

### 2.1 The single call site

`backend/src/delphos_backend/services/llm_client.py` owns every inference call.
The public surface:

- `async chat_completion(...)` — POSTs to `f"{cfg.llm_api_url}/chat/completions"`.
  Returns a `CompletionResult` (content, reasoning, `TokenUsage`, `Timings`).
- `InferenceError` — every failure mode maps onto this domain exception. It is
  deliberately **not** `HTTPException`; the caller decides.
- `InferenceTimeout(InferenceError)` — a distinct subclass, because the caller
  treats a timeout differently (fall back without spending a repair attempt).

`services/llm_reports.py` (`generate_report`) and `services/chat_agent.py` both
call `chat_completion`. There is no second HTTP client.

### 2.2 The settings

`backend/src/delphos_backend/core/config.py`, `env_prefix="DELPHOS_"`. The LLM
block is `llm_api_url`, `llm_model_name`, `llm_timeout_seconds`,
`llm_max_tokens`, `llm_report_max_tokens`, `llm_temperature`, `llm_top_p`,
`llm_top_k`, `llm_presence_penalty`, `llm_enable_thinking`, `llm_context_size`,
`llm_max_tool_iterations`, `llm_max_concurrent_llm_calls`,
`llm_chat_history_turns`, `llm_report_prompt_version`. Numeric settings carry
`Field(ge=, le=)` bounds.

### 2.3 The failure semantics already in place

| Path | Both endpoints down |
| --- | --- |
| `POST /reports/generate` | 200, `source="deterministic"`, valid Spanish report |
| `POST /chat` (non-streaming) | 503 problem+json |
| `POST /chat` (streaming) | pre-first-byte failure → 503 problem+json; mid-stream failure → `error` SSE event, turn not persisted |

A fallback therefore has to preserve these. Adding a second endpoint must not
turn a 200 into a 503 or vice versa.

### 2.4 The cache already distinguishes generators

`app.reports` records `source`, `llm_model`, `prompt_version`, and
`get_latest_player_report` keys on all of them (`repositories/reports.py`). A
report generated on the fallback is therefore recorded honestly — including the
model id — and the cache cannot serve one generator's output as another's. This
is the property that makes the fallback cheap to add.

## 3. The problem

Two separate problems, and they are easy to conflate.

**A. Reachability.** A Docker container on the default bridge cannot see host
network interfaces. ZeroTier's interface lives on the host. The container must
be able to open a TCP connection to the ZeroTier IP.

**B. Fallback logic.** The application must try one endpoint, then the other,
without doubling the worst-case latency and without breaking streaming.

A is a deployment question. B is a code change. Only B needs a spec; A needs a
decision and a documented procedure.

## 4. Reachability: ZeroTier from a Docker container

Three options. **Option A is recommended and needs no compose change at all.**

### Option A — use the ZeroTier IP directly (recommended)

The backend container's egress is NAT'd through the host, and the host has the
ZeroTier route. So an outbound connection to the ZeroTier IP works with the
default bridge networking:

```bash
# .env
DELPHOS_LLM_FALLBACK_API_URL=http://172.25.60.1:8080/v1
```

**Preconditions to verify before relying on it:**

1. **No subnet collision.** Check `docker network inspect bridge` and
   `zerotier-cli listnetworks`. Docker's default bridge is `172.17.0.0/16` and
   compose networks commonly land in `172.18-172.31.x.x`; ZeroTier commonly
   assigns `172.25.x.x` or `10.147.x.x`. If the ZeroTier subnet overlaps a Docker
   subnet, the container's route wins and the packet never reaches ZeroTier.
2. **No firewall drop.** The host must not filter forwarded traffic to the
   ZeroTier interface.

Verification: `docker compose exec backend python -c "import httpx; \
print(httpx.get('http://<zt-ip>:8080/health', timeout=5).status_code)"`.

### Option B — `extra_hosts` with a stable name

```yaml
  backend:
    extra_hosts:
      - "llm-remote:172.25.60.1"
```

Then `DELPHOS_LLM_FALLBACK_API_URL=http://llm-remote:8080/v1`. Same routing as
Option A, but the address is named once and the `.env` value survives a ZeroTier
address change in one place rather than several.

### Option C — `network_mode: host` (last resort)

The container shares the host's network stack and sees the ZeroTier interface
directly. It costs port isolation **and** compose DNS: service names
(`inference-chat`, `db`, `migrate`) stop resolving, so every service URL would
have to change to `localhost` or a fixed address. Only take this if Option A
fails and the cause cannot be fixed.

### The remote end

If the remote llama.cpp is itself dockerised, it needs:

- `LLAMA_ARG_HOST: 0.0.0.0` (already the case in this repo's compose).
- A published port, so the remote host's ZeroTier IP forwards to the container.
- **`LLAMA_ARG_ALIAS` reporting the same model id the backend sends.** This is
  the constraint that caused a critical defect in the local path — the backend
  sent `qwen/qwen3.5-9b` while the server reported the file path, so every
  request failed to resolve and reports silently fell back. The local fix
  derives `LLAMA_ARG_ALIAS` and `DELPHOS_LLM_MODEL_NAME` from one compose
  variable (`docker-compose.yml`, ADR-022). Do the same remotely.

## 5. Application change: the fallback

### 5.1 Configuration

Add to `core/config.py` and document in `.env.example` **and**
`docs/ARCHITECTURE.md` §9 (the two must agree — `AGENTS.md` §4):

| Key | Default | Meaning |
| --- | --- | --- |
| `DELPHOS_LLM_FALLBACK_API_URL` | `""` | Empty disables the fallback entirely. |
| `DELPHOS_LLM_FALLBACK_MODEL_NAME` | `""` | Empty means "same as `llm_model_name`". |
| `DELPHOS_LLM_FALLBACK_TIMEOUT_SECONDS` | `60.0` | The remote link is slower; also bounds the retry. |

Two more, in §6's decision list rather than fixed here:
`DELPHOS_LLM_PRIMARY_PROBE_SECONDS` and `DELPHOS_LLM_FALLBACK_ENABLED`.

### 5.2 The retry loop

In `llm_client.chat_completion`:

1. If the fallback is configured, attempt the **primary** with a short timeout
   (see §6 decision 1).
2. On `InferenceTimeout` or `InferenceError`, attempt the **fallback** with
   `llm_fallback_timeout_seconds`.
3. On a second failure, raise as today.

The call site (`generate_report`, `chat_agent`) needs **no change** — it already
handles `InferenceError` and `InferenceTimeout` correctly, and the report path
already degrades to deterministic.

`CompletionResult` should carry which endpoint served the call, so it can be
logged and (see §6 decision 3) recorded.

### 5.3 What the existing design gives for free

- **Provenance.** `ReportResult.llm_model` is already in the cache key. A report
  generated on the fallback records the model that actually produced it, and a
  later report from the primary is a separate cache entry if the ids differ.
- **Deterministic floor.** Both endpoints down is still a 200 with a valid
  report. The fallback changes the *quality* of the degraded path, never the
  *status code*.
- **Concurrency cap.** `chat_concurrency.py`'s semaphore wraps
  `chat_completion`, so a primary-then-fallback attempt holds one slot for both.
  That is the desired behaviour (one logical call), but see §6 decision 1 on the
  latency consequence.

## 6. Open decisions

These need settling before implementation. Each changes the code.

### Decision 1 — timeout budget

If the primary takes its full 120 s and then the fallback takes 120 s, one
request can run 4 minutes while holding a request and (for chat) a semaphore
slot. Three options:

- **(a) Short primary probe** — `llm_primary_probe_seconds = 20` when a fallback
  is configured. The local path is fast when healthy; 20 s is generous. Simple,
  bounded, recommended.
- **(b) Overall deadline** — one budget, the remainder goes to the fallback.
  More precise, more code.
- **(c) No special case** — accept 4 minutes. Only acceptable if the fallback is
  genuinely rare and the load is trivial.

**Recommendation: (a).**

### Decision 2 — streaming

`POST /chat?stream=true` cannot fall back mid-stream: once the 200 headers are
sent the status cannot change. The endpoint must therefore be chosen **before**
the first byte. Options:

- **(a) Preflight probe** before streaming, with a short TTL cache (a few
  seconds) of "primary is healthy" so consecutive turns do not each pay a probe.
- **(b) Try primary, buffer the first token, fall back if none arrives.** Adds
  latency to every turn and complicates the error semantics.
- **(c) No fallback for streaming** — streaming always uses the primary and
  degrades to the `error` SSE event. Simplest; the non-streaming path and the
  report path still get the fallback.

**Recommendation: (a)** if streaming matters, **(c)** if the schedule is tight.

### Decision 3 — what if the remote runs a different model?

- **(a) Same model, different host.** The fallback is transparent; the cache
  treats them as one. Requires the remote to serve the identical GGUF and the
  same `LLAMA_ARG_ALIAS`.
- **(b) Different model or quant.** Reports generated on the fallback are
  genuinely different reports. The cache already separates them, which is
  correct, but you should decide whether that is desirable or whether the
  `source` column should gain a third value (`"llm-fallback"`) so a reviewer can
  tell which endpoint produced what.

**Recommendation:** if the remote is your own machine running the same GGUF,
take (a) — nothing else changes. If it may differ, take (b) with a `source`
extension, and record the endpoint in `app.reports` alongside `llm_model`.

## 7. Security

The security audit of the existing change flagged that `inference-chat` is
unauthenticated on the shared Docker network. A ZeroTier link widens that
surface: a ZeroTier network can have members beyond the two hosts, and every
prompt crosses it (they contain player data).

If the ZeroTier network is not exclusively these two machines:

- Set `LLAMA_ARG_API_KEY` on the remote llama.cpp.
- Send `Authorization: Bearer <key>` from `llm_client.py` for the fallback
  endpoint (and consider it for the primary too).
- Add `DELPHOS_LLM_FALLBACK_API_KEY` to `Settings`, `.env.example` and
  `docs/ARCHITECTURE.md` §9.

If the network is only these two machines, this is optional but cheap.

Also worth pinning: the remote image tag should be pinned by digest the same way
the local one should be, so the served binary cannot change between pulls.

## 8. Tests

Follow `backend/tests/` conventions (see `tests/test_llm_client.py` and
`conftest.py` — fake `httpx`, never make a real network call).

- Primary succeeds → fallback is never contacted (`call_count == 1`).
- Primary raises `InferenceTimeout` → fallback is attempted and its result is
  returned.
- Primary raises `InferenceError` (transport, non-2xx, malformed, empty) → same.
- Both fail → `InferenceError` propagates, and `POST /reports/generate` still
  returns 200 with `source="deterministic"`.
- Fallback disabled (`llm_fallback_api_url == ""`) → the primary is the only
  call and the behaviour is identical to today.
- The `CompletionResult` records which endpoint served.
- Streaming (if decision 2 is (a)): the probe result is cached for the TTL, and
  a probe failure routes the stream to the fallback before the first byte.
- Config: the three new settings have bounds, and the `.env.example` /
  `docs/ARCHITECTURE.md` §9 key sets still agree in both directions.

## 9. Work order

| # | Task | Gate |
| --- | --- | --- |
| 1 | Settle the three decisions in §6 | Everything else depends on them. |
| 2 | Verify reachability (§4 Option A) from the running backend container | If this fails, the code change is moot until the network is fixed. |
| 3 | `core/config.py` + `.env.example` + `docs/ARCHITECTURE.md` §9 key sync | The configuration contract. |
| 4 | The retry loop in `llm_client.py` | The functional change. |
| 5 | Streaming preflight (only if decision 2 is (a)) | Depends on 4. |
| 6 | Tests | Per §8. |
| 7 | ADR in `ARCHITECTURE.md` §10, decision-log rows in `WORK_PLAN.md` | `AGENTS.md` §4 requires the owning documents change in the same change. |

## 10. See also

- [LLM_PLAN.md](LLM_PLAN.md) — the report and chat features this builds on,
  including the fact-reference schema, the deterministic renderer, and the
  experiment suite.
- [ARCHITECTURE.md](ARCHITECTURE.md) §4.6 (LLM inference service), §9
  (configuration), §10 (ADRs; **ADR-022** covers the derived model id).
- [AGENTS.md](../AGENTS.md) §4 — the conventions, including the requirement
  that `.env.example` and `docs/ARCHITECTURE.md` §9 stay in sync.
