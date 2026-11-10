# LLM feature plan: scouting report generation and conversational querying

## Contents

1. [Purpose](#1-purpose)
2. [Scope and non-goals](#2-scope-and-non-goals)
3. [Current state](#3-current-state)
4. [Decisions carried into this plan](#4-decisions-carried-into-this-plan)
5. [Model and quant selection](#5-model-and-quant-selection)
6. [Inference service configuration](#6-inference-service-configuration)
7. [Report generation pipeline](#7-report-generation-pipeline)
8. [Fact grounding and numeric verification](#8-fact-grounding-and-numeric-verification)
9. [Vocabulary ownership](#9-vocabulary-ownership)
10. [Chat feature](#10-chat-feature)
11. [Hallucination detection: what we build and what we do not](#11-hallucination-detection-what-we-build-and-what-we-do-not)
12. [Data model changes](#12-data-model-changes)
13. [Configuration keys](#13-configuration-keys)
14. [Module layout](#14-module-layout)
15. [API surface](#15-api-surface)
16. [Tests](#16-tests)
17. [Experiments](#17-experiments)
18. [Work order and cut order](#18-work-order-and-cut-order)
19. [Risks and open items](#19-risks-and-open-items)
20. [See also](#20-see-also)

---

## 1. Purpose

This plan covers delivery priority 4 of [ADR-007](ARCHITECTURE.md#adr-007-delivery-priority-under-the-course-deadline): the LLM features served by the `inference-chat` service in `docker-compose.yml`. Two features:

- **Scouting report generation** — `POST /reports/generate` produces an executive-prose scouting report for a player, grounded on the published analytics rows for the active model run. The endpoint exists and is tested today; this plan hardens it.
- **Conversational querying** — `POST /chat` answers natural-language questions about the dataset by calling typed read-only tools over the `analytics` schema. The endpoint does not exist; the `app.chat_sessions` and `app.chat_messages` tables already do.

This document is a working plan, not a decision record. Each decision it leads to is recorded in its owning document when it is made: architecture decisions in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §10 (ADRs) and §4.6/§5.3/§6/§9, ML decisions in [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.18, schedule and variances in [docs/WORK_PLAN.md](WORK_PLAN.md), and methodological limitations for the final report in [docs/REPORT_NOTES.md](REPORT_NOTES.md) (Spanish).

The plan is written against the repository state of 2026-11-08: the ML pipeline is complete end to end, `publish` is shipped, the FastAPI backend has read endpoints plus a working `POST /reports/generate`, and `docker-compose.yml` carries a `backend` service and an `inference-chat` service that has no model bound to it.

## 2. Scope and non-goals

**In scope.**

- Model and quant selection for the 16 GB RTX 5060 Ti host, and the llama.cpp serving configuration.
- The report generation pipeline: grounded context assembly, a schema-constrained generation call, numeric verification, deterministic rendering, and the degraded path.
- The chat feature: typed tool set over `analytics`, the tool loop, session persistence, and the API contract.
- The data-model, configuration, and compose changes the two features require.

**Out of scope.**

- A Flutter chat screen. The frontend is a static HTML design preview today (`frontend/design-preview/index.html`) with no chat surface; the Flutter client does not exist yet. Chat ships as a backend capability first (§18).
- Migrating the `POST /players/what-if` endpoint (delivery priority 3) into the backend. That endpoint is still unimplemented and is not required by either feature here.
- Text-to-SQL. The model never emits SQL. See §11.
- MCP. The tool layer is in-process in the backend. The rationale is in ADR-015 (to be written); the short version is in §10.
- Publishing the Empirical Bayes per-90 rates to the database. Decided against in §9.3.
- Any hosted or third-party LLM. ADR-004 holds: a local llama.cpp process is the only LLM provider, and no data leaves the host.

## 3. Current state

### 3.1 What exists

| Component | State | Location |
| --- | --- | --- |
| Report generation endpoint | Implemented, 4 unit tests | `backend/src/delphos_backend/api/reports.py` |
| Grounded context assembly | Implemented | `backend/src/delphos_backend/services/llm_reports.py` |
| LLM HTTP client | Implemented (httpx, non-streaming) | `backend/src/delphos_backend/services/llm_reports.py:93-125` |
| Report persistence | Implemented, `app.reports` | `backend/src/delphos_backend/repositories/reports.py` |
| Chat tables | Migrated, unused | `migrations/versions/0003_app_tables.py:45-72` |
| Chat endpoint and tool layer | Absent | — |
| `inference-chat` service | Declared, **no model bound** | `docker-compose.yml:92-101` |
| Model weights | Not provisioned; `llms/` absent | `.gitignore` lists `/llms/models/` |
| Spanish vocabulary | Frontend-only JS constants | `frontend/design-preview/index.html:1494-1539` |

### 3.2 The three defects this plan resolves

**D1 — the report path cannot reach the model.** The `inference-chat` service sets only `LLAMA_ARG_HOST` and `LLAMA_ARG_PORT` and mounts `./llms/models:/models:ro`, but never binds a model: there is no `LLAMA_ARG_MODEL`, no `LLAMA_ARG_MODELS_DIR`, and no `LLAMA_ARG_MODELS_PRESET`. llama.cpp therefore starts in router mode, where a request is routed by the `"model"` field of the request body against the models the router knows. The backend sends `"model": cfg.llm_model_name`, whose default is the literal string `"local-gguf"` (`backend/src/delphos_backend/core/config.py:45`). That name matches no model, so the request cannot resolve.

**D2 — the report is ungrounded and unverified.** The context is assembled into a JSON blob, dumped into a user message, and free prose comes back (`llm_reports.py:96-106`). Nothing constrains the model to the facts and nothing checks its output. The system prompt is a placeholder carrying a TODO: `DEFAULT_SYSTEM_PROMPT = "You are a football scouting analyst for DelphosFootball."` (`llm_reports.py:20-21`). `llm_max_tokens` is 512, which truncates a three-section report mid-sentence.

**D3 — the report has no ground truth to be wrong against.** `frontend/design-preview/index.html:1622-1648` already contains a deterministic narrative generator, `buildExecutiveNarrativeHtml(player)`, which produces the complete three-section Spanish executive summary ("Dictamen Financiero", "Rendimiento Deportivo", "Alternativas de Mercado") from the same fact fields the backend assembles, formatting every currency value through `formatEurM` (`index.html:1553-1563`). The design preview is not a mock of the report; it is a reference implementation of a report that cannot be wrong. The backend currently has no equivalent.

### 3.3 The decisive discovery

The report's structure is fully determined by the facts, and a correct implementation of it already exists in the repository in JavaScript. That reframes the whole feature:

- The LLM's job is **not** to compute or to write numbers. It is to add editorial voice to a set of already-correct facts.
- A report can be produced with **zero** LLM involvement. That is the floor, and it is the fallback.
- Numeric hallucination is therefore not a detection problem to be solved with a judge. It is a **representational** problem to be solved by construction: the model never writes a number.

## 4. Decisions carried into this plan

Taken by the team on 2026-11-08 and binding on this plan.

| # | Decision | Consequence for this plan |
| --- | --- | --- |
| C1 | The 2026-11-04 model decision in [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.18 and [docs/REPORT_NOTES.md](REPORT_NOTES.md) H-20 is **superseded**. Qwen3.5-9B serves both features. | Both documents are rewritten together. The 3B choice is retained in ADR-004 terms as the CPU-only variant (§5.3). |
| C2 | The report and the chat both ship. | Chat is scoped to a backend capability; the Flutter chat screen is a follow-on (§18). |
| C3 | The tool layer is **in-process function calling** in the backend. | No MCP server, no new compose service. Recorded as ADR-015. |
| C4 | **PydanticAI** is the agent framework. | `pydantic-ai-slim[openai]`; `OpenAICompatibleProvider` against the llama.cpp base URL. Recorded as ADR-016. |
| C5 | The deterministic fallback **is persisted and served** in place of the 503. | `app.reports` records the source. Changes the "LLM unavailable" behaviour documented in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §9. |
| C6 | The EB per-90 rates are **not** published. | The report is scoped to published facts only. See §9.3 for the consequence. |
| C7 | `delphos_ml` owns the Spanish vocabulary. | See §9 — this adds a `backend` → `delphos_ml` dependency that does not exist today. |
| C8 | Reports are **non-streaming**; streaming is chat-only. | [docs/ARCHITECTURE.md](ARCHITECTURE.md) §5.3 and §9 are amended to match (§6.4). |
| C9 | The report and the chat answers are in **Spanish**; the currency format stays international (`€25.0M`). | See §7.6. The product's register is Spanish; the currency format follows `DESIGN.md` §3 and the design preview, so the report and the UI cannot disagree. |

## 5. Model and quant selection

### 5.1 The binding constraint

The host is an RTX 5060 Ti **16 GB** (Blackwell, sm_120, 448 GB/s GDDR7). The 8 GB variant of the same card has identical bandwidth and half the memory; it is not the target of this plan, and the 3B model that ADR-007's original deadline context assumed is retained only as the CPU/no-GPU variant.

### 5.2 Selected model

**Qwen3.5-9B** (Apache-2.0, 9B dense, hybrid Gated DeltaNet), served as GGUF.

| Property | Value | Why it matters here |
| --- | --- | --- |
| Published tool-calling scores | BFCL-V4 **66.1**, TAU2 **79.1** | The only candidate in the ≤9B band with BFCL > 60 and TAU2 ≈ 80. Decisive for the chat tool loop. |
| Instruction following | IFEval **91.5**, IFBench **64.5** | The report must obey a genre and a format. |
| Long-context retention | AA-LCR **63.0**, LongBench v2 **55.2** | A report quotes ~32 facts; they must survive into the prose. |
| KV footprint | **16,384 B/token** | 24 Gated DeltaNet layers + 8 full-attention layers, 4 KV heads × 256 dim, q8_0. **512 MiB at 32K context** — 10× cheaper than Granite 4.2-8B's 163,840 B/token. This is what allows many concurrent slots on one card. |
| llama.cpp tool parsing | Native | `common/chat.cpp:1412` — "Qwen3-Coder XML tool calls, also used by Nemotron Nano 3, **Qwen3.5** and StepFun-3.5-Flash". Not the generic fallback. |
| Speculative decoding | **No MTP heads** | `--spec-type draft-mtp` measured at ~1.7× on sm_120 under Linux (llama.cpp #28196), but this model's `config.json` has no `num_nextn_predict_layers` and its repository ships no MTP tensor file. The flag is therefore **left unset** (§6.2). |

Prose quality was checked against the alternative: Qwen3.5-9B leads gpt-oss-20b on MMLU-Pro (82.5 vs 74.8), IFEval (91.5 vs 88.2) and AA-LCR (63.0 vs 30.7). For a report that must be faithful to a fact bundle, that is the decisive axis.

### 5.3 Variants

| Role | Model | Quant | Size | When |
| --- | --- | --- | --- | --- |
| **Primary** | Qwen3.5-9B | `Q5_K_M` | 6.58 GB | 16 GB host. Default. |
| **Memory-constrained** | Qwen3.5-9B | `Q4_K_M` | 5.68 GB | 8 GB host, or more slots on 16 GB. |
| **CPU-only** | Qwen3.5-4B | `Q4_K_M` | 2.74 GB | No GPU. Replaces the superseded 3B choice. |
| **Independent fallback** | Granite 4.2-8B | `Q4_K_M` / `Q5_K_M` | 5.54 / 6.41 GB | If a Qwen3.5 llama.cpp parser bug blocks delivery. Documents a non-thinking mode (`enable_thinking=false`) that Qwen3.5's toggle does not reliably provide (§6.2). |

**Not selected, with reasons.**

- **Gemma 4 E4B** — best memory profile (16 KB/token, 128K context in 4.7 GB) and native llama.cpp support, but Tau2 **42.2** is roughly half of Qwen3.5-9B's 79.1, and llama.cpp #26674 documents a Blackwell-specific Gemma-4 decode pathology on this exact card (gemma4 31B Q6_K → 0.62 t/s against qwen35moe 35B → 5.49 t/s, GPU idling, CPU at 95-100%). It is the option if VRAM, not quality, becomes binding.
- **gpt-oss-20b** — 21B total / 3.6B active, the best raw agentic behaviour of the set, but 11.62 GB of weights leave ~2-3 GB for KV on a 16 GB card, 128K context does not fit (128K × 49,152 B = 6 GB of KV alongside 11.6 GB of weights), it cannot run on 8 GB, and its Harmony channel format is an integration cost. It remains a documented over-budget option, not a default.
- **Qwen2.5-3B-Instruct / Llama-3.2-3B-Instruct** — the superseded choice. Both are September 2024 models, well before the agentic-training era; neither is credible for the chat tool loop.

### 5.4 Quantization rules

- **Tool calling: `Q5_K_M`, `Q4_K_M` as the floor.** Argument-level fidelity — identifiers, numbers, dates — breaks first, and the tool-call path is unforgiving.
- **Report generation: `Q5_K_M`–`Q6_K`.** Long-form prose is where quantization artifacts show as repetition and broken clauses.
- **Never `IQ3_S`.** llama.cpp #28581: garbage output on RTX 5060 Ti (Blackwell). `IQ4_XS` (5.17 GB) and `IQ4_NL` (5.37 GB) are the safe "smaller than `Q4_K_M`" options.
- **Never `Q3_K_M` or `Q2_K` for the report.** They measurably degrade instruction following and long-form coherence.
- **No vision projector.** Qwen3.5-9B's `mmproj` is 0.92 GB and the features are text-only. Do not load it; on an 8 GB card that is decisive.
- **KV cache: `q8_0`/`q8_0`, never 4-bit.** llama.cpp #27109 measured a 4-bit K cache collapsing hybrid prefill from 991-1276 t/s to **34-106 t/s** (~20×) on a qwen35 model. llama.cpp's own function-calling documentation warns that extreme KV quantization "can substantially degrade the model's tool calling performance". Issue #31213 adds that CUDA flash-attention has no compiled kernel for `q8_0-q4_0`, so a mixed cache silently falls back to f16.

## 6. Inference service configuration

### 6.1 Model binding (resolves D1)

Two mutually exclusive serving modes. This plan pins **single-model mode**, because the router's model-name routing (§3.1 D1) is one failure mode we do not need.

```yaml
  inference-chat:
    image: ghcr.io/ggml-org/llama.cpp:server-cuda
    container_name: delphos-inference-chat
    environment:
      LLAMA_ARG_HOST: 0.0.0.0
      LLAMA_ARG_PORT: 8080
      LLAMA_ARG_MODEL: /models/Qwen3.5-9B-Q5_K_M.gguf
      LLAMA_ARG_CTX_SIZE: 32768
      LLAMA_ARG_N_PARALLEL: 4
      LLAMA_ARG_KV_UNIFIED: "on"
      LLAMA_ARG_N_GPU_LAYERS: 99
      LLAMA_ARG_FLASH_ATTN: on
      LLAMA_ARG_JINJA: on
      LLAMA_ARG_REASONING: auto
      LLAMA_ARG_CACHE_TYPE_K: q8_0
      LLAMA_ARG_CACHE_TYPE_V: q8_0
    volumes:
      - ./llms/models:/models:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 60s
    networks:
      - delphos-network
```

Required changes against the current file: the image moves from `server` (CPU build, 5 layers) to `server-cuda` (13 layers, CUDA runtime); `LLAMA_ARG_MODEL` binds the file; the serving flags are set; a healthcheck is added.

**`LLAMA_ARG_KV_UNIFIED: "on"` is load-bearing, not decoration.** Without it, setting `LLAMA_ARG_N_PARALLEL: 4` explicitly divides the 32K context into four 8K slots and the §10.4 chat budget does not fit. See §6.2 for the source-level explanation.

**`LLAMA_ARG_SPEC_TYPE` is deliberately absent.** Speculative decoding via `draft-mtp` is a *performance experiment* on this model, not a required flag — Qwen3.5-9B ships no MTP heads, so the flag may abort the server at startup. See §6.2.

`LLAMA_ARG_MODEL` points at a file inside the mounted directory, so the model is provisioned by the engineer before the stack starts and the running system never fetches weights at runtime — the assumption [docs/ARCHITECTURE.md](ARCHITECTURE.md) §2 already makes.

**The image tag and the host GPU must agree.** `server-cuda` requires the NVIDIA container runtime and a host driver that supports sm_120. On a host without a GPU, `server` is the CPU variant and the 4B variant of §5.3 is the model. The compose file's `LLAMA_ARG_MODEL` is therefore environment-overridable so the same file serves both.

### 6.2 Flags that are not optional

| Flag | Value | Reason |
| --- | --- | --- |
| `LLAMA_ARG_JINJA` | `on` | Tool calling requires it. llama.cpp's server throws "tools param requires --jinja flag" otherwise (`tools/server/server-common.cpp:1362-1369`). |
| `LLAMA_ARG_REASONING` | `auto` | llama.cpp #20837: Qwen3.5 emits tool calls *inside* the thinking block, where the grammar stops generation and the call is never parsed as a tool call. The server default is `auto` (detect from the template), which leaves the decision to the **per-request** `chat_template_kwargs` (§13's `DELPHOS_LLM_ENABLE_THINKING`). **E5 (§17.3) measures whether thinking is right for each feature**; the server stays on `auto` so the two features can differ. |
| `LLAMA_ARG_CHAT_TEMPLATE_KWARGS` | *unset* | Deliberately **not** set at the server level. `chat_template_kwargs` is a **per-request** parameter (`tools/server/README.md:1449`), so the backend sends `{"enable_thinking": false}` (or `true`) with each request and the two features can differ. Setting it globally would force one choice on both, and E5 may find that one feature wants thinking and the other does not. The template honours it: the model's own `chat_template.jinja` reads `enable_thinking` and emits an empty `<think>\n\n</think>` block when it is `false`. **Verify empirically that the toggle takes effect in the shipped build** — issues #20409, #20182, #20789 and #20516 are a family of "enable_thinking=false is ignored" bugs. If it is ignored, fall back to Granite 4.2-8B (§5.3), whose non-thinking mode is a first-class part of its template. |
| `LLAMA_ARG_CACHE_TYPE_K` / `_V` | `q8_0` | §5.4. Never 4-bit. |
| `LLAMA_ARG_CTX_SIZE` | `32768` | The chat history budget (§10.4). Also caps llama.cpp #29172, where a qwen35 hybrid on this exact card collapses at deep KV position (pp512 464.8 → 21.9 t/s, tg32 44.7 → 8.1 t/s at depth ~155K). Irrelevant at 32K, but the cap is the reason it is irrelevant. **This is the *total* pool across all slots, not a per-slot limit** — see the `n_parallel` row. |
| `LLAMA_ARG_N_PARALLEL` | `4` | Concurrent chat sessions. **Setting this explicitly disables the unified KV cache**, which is the single most important detail in this table — see "The KV cache trap" below. |
| `LLAMA_ARG_KV_UNIFIED` | `on` | **Required** to make `n_parallel=4` share one 32K pool instead of splitting it four ways. See "The KV cache trap" below. |
| `LLAMA_ARG_SPEC_TYPE` | `draft-mtp` | ~1.7× on sm_120 under Linux (#28196). **Linux only.** **But see the MTP caveat below — this flag may be inert for this model.** |

**The KV cache trap — the most consequential correction in this plan.**

`--ctx-size` is the **total** KV pool, and it is divided across the slots. In llama.cpp's `src/llama-context.cpp:426-440`:

```cpp
if (cparams.kv_unified) {
    cparams.n_ctx_seq = cparams.n_ctx;
} else {
    cparams.n_ctx_seq = cparams.n_ctx / cparams.n_seq_max;   // 32768 / 4 = 8192
```

`n_seq_max` is `n_parallel` (`common/common.cpp:1729`). The unified cache is enabled **only when the slot count is left on auto**: `tools/server/server.cpp:126-131` sets `params.kv_unified = true` inside the `if (params.n_parallel < 0)` branch. The server's own default is `n_parallel = -1` (`common/arg.cpp:1373`), so the default path gets a unified 32K pool with four slots.

**The spec's configuration sets `LLAMA_ARG_N_PARALLEL: 4` explicitly, which takes the `n_parallel >= 0` path and leaves `kv_unified` at its default of `false`** (`common/common.h:582`). The consequence is silent and severe:

| Configuration | `n_ctx_seq` per slot | Chat budget that fits |
| --- | --- | --- |
| `n_parallel: 4`, no `kv_unified` (as first written) | **8192** | The §10.4 budget of 16K **does not fit** — a long chat is silently truncated or rejected. |
| `n_parallel: 4` + `kv_unified: on` | **32768** | The 16K budget fits with headroom. |

The failure is quiet: the server starts, accepts requests, and truncates. Nothing in the logs says "your context was divided". This would have surfaced as "the chat forgets the conversation halfway through", which is exactly the symptom that is hardest to debug late in the schedule.

Two ways to fix it, and the plan uses **both**:

1. **`LLAMA_ARG_KV_UNIFIED: on`** — `n_ctx_seq` becomes the full `n_ctx` (32768) for every slot, and the slots share one pool. This is what the server does by default.
2. **`LLAMA_ARG_KV_UNIFIED_PER_SLOT: 8192`** — the explicit per-slot cap for the *non*-unified layout. This is **not** what this plan wants, and it is recorded here only because the flag exists and is easy to reach for: with `kv_unified` off, setting it to 8192 makes the intent explicit rather than accidental.

`LLAMA_ARG_KV_UNIFIED` accepts `on`/`enabled`/`true`/`1` and `off`/`disabled`/`false`/`0` (`common/arg.cpp:1304-1310`). The same parser handles `LLAMA_ARG_JINJA` and `LLAMA_ARG_FLASH_ATTN`.

**On the memory arithmetic.** The spec's original claim — "at `Q5_K_M` with 32K context the per-slot KV is ~1.0 GiB, so 4 slots fit in the ~9 GB left" — was written for the *divided* layout and is wrong twice over. With `kv_unified: on` there is **one** 32K pool shared by four slots, not four 32K pools.

Qwen3.5-9B is a hybrid: 32 layers, of which **8 are `full_attention`** and 24 are `linear_attention` (from the model's `config.json`, `layer_types`), and only the full-attention layers carry a KV cache. At `q8_0` (1 byte per element) with 4 KV heads × 256 head dim, over 8 full-attention layers, K and V together:

```
8 layers × 2 (K and V) × 4 KV heads × 256 head_dim × 1 byte = 16 KiB per token
```

So a 32K pool is **~512 MiB**, and the *divided* 8K-per-slot layout would be ~128 MiB per slot. Either way the pool is cheap: the 6.58 GB of `Q5_K_M` weights dominate, and `n_parallel=4` costs almost nothing in VRAM once the cache is unified. The original "~1.0 GiB per slot" figure was roughly double the correct value and described a layout the configuration does not produce.

`GGML_CUDA_DISABLE_GRAPHS=1` is the documented workaround if the Blackwell CUDA-graph hang appears (llama.cpp #27330: watchdog reset / Xid 8 on sm_120). It is not set by default.

**The MTP caveat — speculative decoding may be inert for this model.** `draft-mtp` requires the model to carry **MTP (multi-token prediction) heads**. Qwen3.5-9B's `config.json` has **no `num_nextn_predict_layers`**, and the Hugging Face repository ships **no `nextn` or `mtp` tensor file** (its 16 files are the four `model.safetensors` shards plus config, tokenizer and template files).

In llama.cpp's `common/speculative.cpp:2823-2834`, when `draft-mtp` is requested and no separate draft model is given, the server builds an MTP draft context against the target model itself and reads `llama_model_n_layer_nextn(model)` — which is 0 for a model without MTP heads. The `GGML_ASSERT` in `common_speculative_impl_draft_mtp` (`common/speculative.cpp:1572`) then risks aborting the server, or the draft simply produces nothing usable.

So `LLAMA_ARG_SPEC_TYPE: draft-mtp` is **not** safe to ship blind. It is listed here as a **performance experiment, not a required flag**: try it, confirm the server starts and that `/props` reports an active spec type, and drop it if it does not. The report and chat features do not need it — it buys throughput, not correctness. A crash-on-start from an optional optimisation would cost more schedule than it returns.

The safe default is to leave `LLAMA_ARG_SPEC_TYPE` unset (`none`) and add it only after it is verified on the actual GGUF.

### 6.3 Health check

[docs/ARCHITECTURE.md](ARCHITECTURE.md) §8 states that the `inference-chat` healthcheck "verifies that the model is actually loaded (a server-side model check), not merely that the process is listening". There is no healthcheck today. The spec for it:

- Poll `GET /health` on the llama.cpp server. A loaded model returns 200; an unloaded or failed model returns 503.
- `start_period: 60s` — the model load from a cold page cache dominates startup.
- The backend must **not** depend on `inference-chat` (ADR-007 and [docs/ARCHITECTURE.md](ARCHITECTURE.md) §8: "The backend deliberately does not depend on `inference-chat`"). An LLM outage degrades `/reports/*` and `/chat`; every other route serves normally.

**The healthcheck command must use `curl`, not `python3`.** The `server` image target of llama.cpp's `cuda.Dockerfile` is built `FROM base`, which installs only `libgomp1 curl ffmpeg` — **Python is not in it** (Python is added in the separate `full` target). A `python3 -c "..."` healthcheck fails with "executable file not found", and the container is then permanently unhealthy, which blocks any `depends_on: service_healthy`.

The image already ships its own `HEALTHCHECK CMD [ "curl", "-f", "http://localhost:8080/health" ]`, so the compose healthcheck can simply use `curl` too:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 60s
```

`GET /health` is public and returns the server's health state without an API key; `/v1/health` also works (llama.cpp `tools/server/README.md:481-483`).

**The image tag.** The published tags are `server`, `server-cuda`, `server-cuda12` and `server-cuda13` (the workflow names each variant `<target>-<backend>`), so `ghcr.io/ggml-org/llama.cpp:server-cuda` is the correct CUDA tag and `ghcr.io/ggml-org/llama.cpp:server` is the CPU one. The current compose file already uses `:server`.

### 6.4 Streaming

Reports are **non-streaming** (C8). Chat **may** stream; see §10.5.

[docs/ARCHITECTURE.md](ARCHITECTURE.md) §5.3 currently says the response is "returned or streamed" and §9 lists "mid-stream failure (streamed report/chat responses, after the 200 headers were already sent)" as an expected problem type. Both are amended: reports return a complete body; chat streams when the client requests it, and the mid-stream failure semantics of §10.5 apply to chat only.

## 7. Report generation pipeline

### 7.1 Target flow

```
analytics rows (active model run)
  → assemble facts (PlayerFacts)              [existing, extended]
  → render fact cards (values + fact_ref keys) [new]
  → llama-server, response_format json_schema  [replaces the free-prose call]
  → validate schema + numeric fidelity         [new]
  → render executive prose (Spanish)           [new; deterministic]
  → persist app.reports (source, llm_model)    [extended]
  → respond
```

Two exits from the middle of the flow:

- **LLM unavailable, times out, or returns invalid output** → the deterministic renderer (§7.5) produces the report, persisted with `source = 'deterministic'`.
- **LLM output fails numeric verification** → one repair attempt (§8.2), then the deterministic renderer.

The endpoint therefore returns 200 with a correct report in every case where the facts exist. It stops returning 503 for an LLM outage (C5), which amends the "LLM unavailable" problem type in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §9 to apply to the chat path and to the report path only when the deterministic renderer itself fails.

### 7.2 The generation call

`response_format` with a JSON schema, which llama.cpp converts to a GBNF grammar and enforces at the token level (`tools/server/server-common.cpp:1392-1394` accepts `{"type": "json_schema", "json_schema": {"name": ..., "schema": ...}}`; `common/chat.cpp:1671` runs `json_schema_to_grammar`). The token stream is therefore *forced* to be valid JSON matching the schema — the guarantee an 8B-class model does not otherwise have.

The schema separates the model's editorial contribution from the facts:

```python
class ReportSection(BaseModel):
    """One executive section of the scouting report."""

    section_id: str
    headline: str
    """The section's one-line verdict, in prose. No numbers."""
    body: str
    """The section's prose. May contain {fact_ref} placeholders only."""


class ScoutingReportDraft(BaseModel):
    """The model's editorial contribution to a scouting report."""

    title: str
    sections: list[ReportSection]
```

The model emits **no numbers**. Every numeric claim in the rendered prose is substituted by the backend from the fact bundle (§8.1). Numeric hallucination is unrepresentable rather than detected.

PydanticAI expresses this as `NativeOutput(ScoutingReportDraft)`. Two profile requirements, both of which the Qwen3.5 profile in `pydantic_ai/profiles/qwen.py` already sets:

- `supports_json_schema_output=True` — otherwise `NativeOutput` raises `UserError('Native structured output is not supported by this model.')` (`pydantic_ai/models/__init__.py:1727-1728`).
- `json_schema_transformer=InlineDefsJsonSchemaTransformer` — llama.cpp's schema converter resolves `$ref` **only into the same document** (`common/json-schema.cpp:117`: "unsupported $ref, only references into the same document are supported"). Inlining the definitions avoids the whole class of problem.

**The model-name trap.** The Qwen3.5 profile is selected by the regex `qwen-?3[\.\-]5` in `pydantic_ai/profiles/qwen.py`, which is **case-sensitive** and matches `qwen3.5-9b` but not `Qwen3.5-9B`. The profile is only consulted for a `qwen/`-prefixed model name under `OpenAICompatibleProvider`. The model is therefore named **`qwen/qwen3.5-9b`** (lowercase), or the profile is passed explicitly. This is recorded in the spec because it is invisible until `NativeOutput` raises.

Verified against `pydantic-ai-slim==2.66.0`: `qwen/qwen3.5-9b` resolves to a profile with `supports_json_schema_output=True`, while `Qwen/Qwen3.5-9B` (uppercase vendor) does **not** — the vendor prefix `qwen` is matched case-sensitively by `_vendor_prefixed_model_profile` (`pydantic_ai/providers/openai_compatible.py:60-80`), so an uppercase vendor silently falls back to the generic OpenAI-compatible profile. Both spellings resolve the profile, but only the lowercase one resolves it *deliberately*.

**The prefix trap.** The bare `openai:` prefix selects the **Responses** API (`pydantic_ai/models/__init__.py:2993-2996`), which llama.cpp does not serve. The provider is constructed explicitly as `OpenAICompatibleProvider('delphos', base_url=..., api_key='not-needed')` with `OpenAIChatModel`.

**The import path.** `OpenAICompatibleProvider` lives in **`pydantic_ai.providers.openai_compatible`**, not `pydantic_ai.providers.openai`. Importing it from `providers.openai` raises `ImportError: cannot import name 'OpenAICompatibleProvider' from 'pydantic_ai.providers.openai'` (verified on 2.66.0). The two modules are easy to confuse: `providers.openai` holds `OpenAIProvider` for the real OpenAI API, and `providers.openai_compatible` holds the one for llama.cpp.

### 7.3 The prompt

`DEFAULT_SYSTEM_PROMPT` is replaced by a real scouting-report genre prompt, **in Spanish** — the product is Spanish ([DESIGN.md](../DESIGN.md): "Dirección Deportiva" register, natural football terminology, no SQL identifiers), and the report reaches that audience directly.

The prompt states:

- the three sections the product expects, matching `buildExecutiveNarrativeHtml`: `dictamen_financiero`, `rendimiento`, `alternativas`;
- the register: executive Spanish, football terminology, no column names, no API routes, no debug output;
- that the model may only assert claims about **this** player from **this** fact bundle, and that a section whose facts are absent says so rather than estimating;
- the prohibitions: no injury, contract, salary, agent, or disciplinary claims (none are in the data — the model will otherwise invent them); no population comparisons ("better than 80% of strikers"), which the fact bundle cannot support; no transfer recommendation beyond the computed replacement candidates;
- that the body may contain only `{fact_ref}` placeholders for numbers, and that `{fact_ref}` keys must come from the supplied card list;
- that the output language is Spanish, and that the canonical Spanish football vocabulary from the fact cards must be used verbatim rather than substituted (§7.6).

The prompt is **written in Spanish** and instructs Spanish output. It is not an English instruction with a Spanish-output clause: the section names, the vocabulary, and the register are Spanish, and an English instruction would leave the model to translate its own instructions before translating the facts. The prompt's own token cost is negligible (§7.6) — a 179-character instruction is 35 tokens.

The prompt lives in a dedicated module (`backend/src/delphos_backend/services/report_prompt.py`), versioned by a `PROMPT_VERSION` constant that is recorded with each report (§12), so a prompt change invalidates the cache rather than silently serving stale prose.

### 7.4 Number formatting

`formatEurM` (`frontend/design-preview/index.html:1553-1563`) is the product's currency format: `€25.0M` at ≥1e6, `€540K` at ≥1e3, `€250` below, `N/D` for null. It is reimplemented in the backend so the report, the API payload, and the UI agree — the format is part of the product contract, not a frontend detail.

This is the **international** convention (dot decimal, symbol before), not the Spanish one (`25,0 M€`). It is kept because `DESIGN.md` §3 and the design preview already specify it, and a report that formatted its numbers differently from the table beside it would look broken. See §7.6.

The fact card builder pre-formats every numeric fact into its display string (`"€25.0M"`, `"75%"`, `"1.8x"`). The model receives the **formatted** values, so it copies them rather than re-deriving them — which is also what prevents a decimal-separator mismatch from ever reaching the prose.

### 7.5 The deterministic renderer

`buildExecutiveNarrativeHtml` is the reference implementation. It is ported to Python as `render_deterministic_report(facts)`, producing the same three sections with the same bold labels, the same `formatEurM` formatting, and the same conditional logic (the financial verdict branches on the sign of `fair_value_eur - market_value_eur`).

This renderer is the **fallback** for every failure path, and it is also the **baseline**: the LLM's value is measured against it. If the LLM version is not better than the deterministic version for a given player, the deterministic one is served.

### 7.6 Language: Spanish

The product is Spanish. `DESIGN.md` sets the register ("Dirección Deportiva", natural football terminology, no SQL identifiers), and the design preview's report section is titled *"Informe para Dirección Deportiva"* with Spanish section labels. The report is user-facing prose for a Spanish-speaking sporting director, so **the report is written in Spanish**, and the chat answers in the language the question is asked.

**Qwen3.5-9B handles Spanish adequately, and the evidence is specific:**

| Benchmark | Scope | Qwen3.5-9B | Reference points |
| --- | --- | --- | --- |
| MMMLU | MMLU professionally translated into 14 languages, **Spanish included** | **81.2** | Qwen3.5-4B 76.1; gpt-oss-20b 69.7 |
| MMLU-ProX | 29 languages | **76.3** | Qwen3.5-4B 71.5; gpt-oss-20b 67.3 |
| WMT24++ | 55 languages, XCOMET-XXL | **72.6** | Qwen3.5-4B 66.6; gpt-oss-20b 67.8 |
| INCLUDE | Multilingual knowledge | **75.6** | Qwen3.5-4B 71.0 |
| NOVA-63 | Multilingual | **55.9** | Qwen3.5-4B 54.3 |

Qwen3.5-9B leads the 4B on every multilingual row of the Qwen card — by 4.6 to 6.0 points on MMMLU, MMLU-ProX, WMT24++ and INCLUDE, and by 1.6 on NOVA-63 — and it beats gpt-oss-20b on MMMLU by 11.5 points. The model card claims "expanded support to 201 languages and dialects". Spanish is a high-resource language for the Qwen family and is explicitly a scored language in MMMLU, so it is well covered.

**Token cost, measured on the actual Qwen3.5 tokenizer** (`Qwen/Qwen3.5-9B` `tokenizer.json`, tokenizers 0.23.3):

| Text | Tokens | Tokens/char |
| --- | --- | --- |
| Spanish report body (3 paragraphs, 595 chars) | 184 | 0.309 |
| English equivalent (576 chars) | 166 | 0.288 |
| Fact card JSON (218 chars) | 95 | 0.436 |

**Spanish costs about 11% more tokens than English** for equivalent content. Three consequences:

1. `DELPHOS_LLM_REPORT_MAX_TOKENS` (1400, §13) is set for Spanish prose, not English. The three-paragraph report measured above is 184 tokens; 1400 leaves ample headroom for a longer verdict and the replacement list while staying inside a single response.
2. The chat history budget (§10.4) is stated in tokens, not exchanges, precisely because a Spanish turn is longer than an English one. The cap stays at 8 exchanges / ≤16K tokens.
3. The fact-card JSON is the **most token-dense** element at 0.436 tokens/char, because every key is spelled out. The card builder therefore emits only the facts a section needs, and the keys are short (`fair_value_eur`, not `valuation.fair_value_eur`) — the difference is 6 versus 8 tokens per placeholder, and a placeholder-heavy body compounds it.

**The language decision is cheap because the numbers are not the model's job.** Under the fact-reference design (§7.2) the model writes no numerals, so the two places Spanish could go wrong are narrow:

- **Currency and decimal separators.** Spanish convention writes `25,0 M€` (comma decimal, symbol after); the product's existing `formatEurM` writes `€25.0M` (dot decimal, symbol before) — the international/English convention. The design preview and `DESIGN.md` both use the latter (`€60.0M`, `€156.0M`, `Ahorra €35.0M · -32%`), so **the product's format is kept**. This is a deliberate product decision, not an accident: `DESIGN.md` §3 specifies the currency format, and changing it would contradict the UI the design preview already specifies. The formatter is shared, so the report, the API payload, and the UI cannot disagree. The model copies the formatted strings, so it cannot introduce a separator mismatch.
- **Terminology.** The model must not invent football terms ("mediapunta de área" for a centre-back). The vocabulary (§9) is supplied in the fact cards as canonical Spanish labels, and the prompt forbids substituting them. The deterministic renderer uses the same vocabulary, so the two paths cannot diverge.

**What is *not* a concern.** GBNF grammar literals with non-ASCII characters are safe: llama.cpp's `format_literal` (`common/json-schema-to-grammar.cpp:302-308`) escapes only `\r`, `\n`, `"` and `\`, leaving accented characters (`á`, `í`, `ñ`, `ü`) intact, and the grammar parser decodes UTF-8 explicitly (`src/llama-grammar.cpp:183`, `decode_utf8`). A Spanish enum value such as `"Creador Ofensivo"` or `"Süper Lig"` constrains correctly.

**One residual risk, stated plainly.** The measured evidence is for *Spanish reasoning and knowledge*, not for *Spanish executive prose in a scouting register*. MMMLU and MMLU-ProX test question answering; they do not test whether the model writes like a sporting director. Two mitigations, both already in this plan:

- The deterministic renderer (§7.5) sets the register, and it is the baseline the LLM is measured against. If the LLM's Spanish prose is not clearly better, the deterministic version is served. The fallback therefore caps the downside of weak Spanish prose at "no better than the template".
- §16's manual verification includes reading a sample of generated reports for register and terminology, alongside the tool-call eval.

The chat path carries the same exposure with less protection: there is no deterministic fallback for a free-form answer, only the "I could not find that in the available data" refusal. The chat system prompt (§10.3) therefore states the answer language explicitly and instructs the model to answer in the question's language.

## 8. Fact grounding and numeric verification

### 8.1 Fact cards

The existing `assemble_player_scouting_context` (`llm_reports.py:25-90`) is kept and extended. It already produces a clean, grounded, JSON-serializable bundle: `model_run_id`, `season`, `player`, `performance_2025`, `valuation`, `replacement_analysis`.

Two changes:

1. **Fact keys.** Every numeric fact gets a stable key and a pre-formatted display value. Keys are **flat and short** — `fair_value_eur`, `goals`, `cost_savings_eur` — not paths like `valuation.fair_value_eur`, because a placeholder is re-emitted in every generated paragraph and each path segment costs tokens (§7.6). The section a fact belongs to is already implied by which card it appears in, so the path is redundant.
2. **Spanish labels.** `position`, `sub_position`, `league_id` and `valuation_status` are currently raw English or codes (`"Attack"`, `"Right Winger"`, `"ES1"`, `"undervalued"`). They are resolved to Spanish (§9) before the bundle reaches the model, so the report speaks the same language as the UI.

The bundle is ~32 numeric assertions for a full report (17 scalars + up to 15 across three replacement candidates). That is the entire surface the model must get right — and, after §7.2, the entire surface it cannot get wrong.

### 8.2 Verification

Three layers, cheapest first.

**L1 — structural (free).** The model emits no numbers (§7.2), so numeric fabrication cannot occur. This layer is the primary defence.

**L2 — numeric extraction (deterministic, ~60 lines).** A final check over the rendered Spanish prose regardless: extract every numeric token, build the allowed set from the fact bundle plus its derived values and their formatted variants, and treat any unmatched number as a violation. This catches what L1 cannot: a number introduced by the renderer itself, a formatting bug, or a stale template. On violation, one repair call re-issues the request with the offending token named; a second violation falls through to the deterministic renderer.

**L3 — offline judge (measurement, not a gate).** See §11.3.

### 8.3 What is *not* verified

The report makes interpretive claims — "dominant in the final third", "the market is underpricing his work rate" — that no checker can validate, because they are judgements, not facts. The control is **authoring scope**, not verification: the schema permits only claims about this player from this bundle, and the prompt forbids the categories that the bundle cannot support (§7.3). A verifier cannot police "the market is underpricing him"; a schema and a prompt can keep the report from saying it.

## 9. Vocabulary ownership

### 9.1 The problem

The product is Spanish. The vocabulary that names it lives in **frontend JavaScript only**: `POS_LABELS` (3), `SUBPOS_LABELS` (13), `LEAGUE_NAMES` (14), `VALUATION_LABELS` (3), `CLUSTER_SHORT_LABELS` (3) at `frontend/design-preview/index.html:1494-1539`. The backend has English cluster names (`backend/src/delphos_backend/repositories/clusters.py:11-15`: `"Attacking Creators & Scorers"`) and raw codes everywhere else.

There is no source of truth in the database: `analytics.fct_clusters` (`migrations/versions/0002_analytics_tables.py:166-181`) has no name or description columns at all — only `cluster_id` and `centroid_distance`. The Spanish archetype descriptions exist only in the preview's JS constant.

Consequence: the report and the UI would name the same archetype differently, in two languages, in two files.

### 9.2 Decision and its cost (C7)

`delphos_ml` owns the vocabulary. It is the right owner: the names are a product artifact of the ML work (the cluster taxonomy comes from `ml/src/delphos_ml/models/_kmeans.py`, whose ordering by `goals_per90 + assists_per90` determines what cluster 0 *is*), and the backend already depends on `delphos_ml` for the artifact contract in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §4.3.

**Today the backend does not depend on `delphos_ml` at all** — `grep delphos_ml backend/` returns nothing, and `backend/pyproject.toml` does not list it. This decision therefore adds the dependency, and it is not free:

- `delphos_ml` declares `scikit-learn`, `pandas`, `numpy`, `pyarrow`, `joblib`, `cloudpickle`, `kagglehub`, `sqlalchemy`, `typer` and others (`ml/pyproject.toml:7-23`). A backend install inherits all of them, and the backend image grows accordingly.
- ADR-013 requires the two lockfiles to agree manually on the seven joblib-relevant versions. That discipline already exists for the `what-if` endpoint; adding the dependency does not create it, but it does make it load-bearing sooner.

**Mitigation that keeps the cost contained.** The vocabulary moves into its own **dependency-free distribution** — `delphos_domain` — that both `delphos_ml` and the backend depend on. It declares no dependencies at all, so the backend's install stays small and its import stays clean. The heavy `delphos_ml` tree is needed by the `what-if` endpoint that [docs/ARCHITECTURE.md](ARCHITECTURE.md) §4.3 already schedules, so this plan front-loads an existing obligation rather than creating a new one. The alternative — the backend keeping its own copy — is rejected: two copies of a taxonomy that must agree is the drift this decision exists to prevent.

**Why not a submodule of `delphos_ml`?** The obvious placement — `ml/src/delphos_ml/domain/labels.py`, pure Python, no pandas, no sklearn — **does not work**, and the reason is not obvious. Importing *any* submodule of a package executes that package's `__init__.py`. `ml/src/delphos_ml/__init__.py` does `from delphos_ml.artifacts import load_model`, and `delphos_ml/artifacts/loaded_artifacts.py` does `from sklearn.base import BaseEstimator` — so `import delphos_ml.domain.labels` pulls sklearn, pandas, numpy, scipy, pyarrow and joblib into the backend's process. Verified on the real package:

```
$ uv run python -c "import delphos_ml.config; print('sklearn' in sys.modules)"
True
```

A submodule isolates the *file*, not the *import*.

Two fixes were considered. Making `delphos_ml/__init__.py` lazy (moving the `load_model` re-export behind a PEP 562 module-level `__getattr__`) fixes the import but **not the install**: the heavy wheels are still resolved and downloaded, because `delphos_ml`'s own `pyproject.toml` declares them. It also edits a facade every existing consumer depends on.

A separate leaf distribution fixes both, and it makes the ownership explicit: the vocabulary is a **shared contract**, not a submodule of a package that happens to be shared.

**The backend image must be able to install it.** Today `backend/Dockerfile` copies only `backend/pyproject.toml`, `backend/README.md` and `backend/src`, so `ml/` is not in the image at all. The compose build context is the **repository root** (`docker-compose.yml:48-50`), which makes the fix easy: the Dockerfile adds

```dockerfile
COPY ml/pyproject.toml ml/README.md ./ml/
COPY ml/src/delphos_domain ./ml/src/delphos_domain
```

and `backend/pyproject.toml` declares the dependency with `uv`'s `[tool.uv.sources]` pointing at the relative path. The build context is already the root, so no compose change is needed.

This also makes the `what-if` endpoint's `delphos_ml` dependency ([docs/ARCHITECTURE.md](ARCHITECTURE.md) §4.3) installable at the same time — the same `COPY` pattern serves both. The backend image will therefore grow by the `delphos_ml` dependency tree whenever that endpoint lands, which is a known and already-scheduled cost.

`delphos_domain` is a third uv project, which ADR-013's per-component-projects rule accommodates: as a leaf with no dependencies it adds no version-alignment burden, and ADR-013's seven joblib-relevant versions are untouched by it.

The backend serves the vocabulary from `GET /clusters` (which already returns cluster names) and from the player payloads, so the frontend stops hard-coding it and the report draws from the same source.

### 9.3 Per-90 rates are not published (C6)

The canonical regressor consumes Empirical Bayes per-90 rates: `ml/src/delphos_ml/features/feature_sets/presets.py:58` sets `rates=("goals", "assists", "yellow_cards", "red_cards")`, transformed by `empirical_bayes_rates.py` into `goals_per90` and friends with `m=5` and positional priors.

**Those rates are not published.** `ml/data/transform/player_seasons.parquet` has 36 columns and no `per90` column; `analytics.fct_player_seasons` publishes raw counts only. The rates are computed at fit time and never reach the database.

C6 settles it: the report is scoped to **published facts only**. Two consequences, stated plainly because they belong in the final report's limitations:

1. **The report cannot quote the model's actual drivers.** It may say "1,800 minutos, 15 goles, 12 asistencias" — all published — but not "0.75 goles por 90 (EB, m=5, prior posicional)". The report explains the valuation in terms of the published diagnostics, not the model's internal feature basis.
2. **A naive per-90 computed in the backend would be a different number from the model's**, because it lacks the shrinkage and the positional prior. Publishing it would misrepresent the model. The report therefore quotes no per-90 figure at all.

This is recorded as a methodological limitation in [docs/REPORT_NOTES.md](REPORT_NOTES.md).

## 10. Chat feature

### 10.1 Shape

One agent, one job: answer a natural-language question about the dataset. It differs from the report agent in kind, not degree:

| | Report agent | Chat agent |
| --- | --- | --- |
| Input | A `player_id` | A natural-language question |
| Facts | One player's bundle, pre-assembled | Unknown at request time; discovered by tool calls |
| Tool calls | None | 5 typed tools over `analytics` |
| Output | A fixed three-section document | A conversational answer |
| Failure mode | A wrong number | A wrong or missing tool call |

Two separate code paths, two separate prompts, two separate context budgets and timeouts. They share the LLM client and the verification helpers, and nothing else.

### 10.2 Tool set

Five typed tools over the `analytics` schema, executed in-process with the API role's read-only access. Each tool maps to an existing repository function, so no new SQL is written.

| Tool | Arguments | Reads |
| --- | --- | --- |
| `search_players` | `position?`, `valuation_status?`, `cluster_id?`, `limit?` | `list_players` (`repositories/players.py:46`) |
| `get_player_profile` | `player_id` | `get_player_profile` (`repositories/players.py:116`) |
| `get_player_valuation` | `player_id` | `get_player_valuation` (`repositories/valuations.py:12`) |
| `get_player_replacements` | `player_id` | `get_player_replacements` (`repositories/replacements.py:12`) |
| `get_cluster_summary` | `cluster_id?` | `get_clusters_summary` (`repositories/clusters.py:18`) |

Rules:

- **No free-form SQL.** The model selects tools and fills typed arguments; it never writes a query. A grammar constrains syntax, not semantics — an 8B model joining nine tables produces wrong-but-valid SQL, which is more dangerous than a hallucinated number because it looks authoritative.
- **Every tool is read-only** and every query is parameterised, against the `analytics` schema, through the API role.
- **Arguments are validated** against the tool's schema before execution; a failure returns a typed error the model can read and retry.
- **Tool results are capped** — a fixed `limit` on every list tool, and a bounded JSON payload per result. This bounds both the token cost and the context growth per turn.

### 10.3 Loop

Implemented with PydanticAI (C4). The loop is the framework's; the guards are ours:

- **Max 4 tool iterations** per request. A confused model loops forever without a cap.
- **Unknown tool name** → a typed error returned to the model, never an exception to the client.
- **Argument validation failure** → a typed error naming the offending argument.
- **No tool call** where one was needed → the model answers from its own knowledge, which is wrong. The system prompt forbids it: *"Responde solo con datos de las herramientas. Si las herramientas no contienen la respuesta, dilo explícitamente."*
- **Unknown model / hallucinated entity** → the tool returns an empty result, not an error, and the model says it found nothing.

### 10.4 Context budget

| Component | Budget |
| --- | --- |
| System prompt | ~400 tokens |
| Tool schemas (5) | ~700-1200 tokens, re-sent every turn |
| Chat history | Capped at 8 exchanges (~4000 tokens) |
| Tool results | ≤ 1500 tokens per turn, trimmed oldest-first |
| **Total** | **≤ 16K tokens**, inside the 32K server context |

The budget is stated in **tokens, not exchanges**, because a Spanish turn is longer than an English one: §7.6 measures Spanish prose at ~11% more tokens per character on the Qwen3.5 tokenizer. A fixed exchange count would have made the effective context language-dependent.

Tool schemas are re-sent on every turn and every iteration — the cost that makes tool count a design parameter, not an afterthought. Five tools is chosen for that reason.

### 10.5 Persistence and streaming

`app.chat_sessions` and `app.chat_messages` already exist (`migrations/versions/0003_app_tables.py:45-72`). Their `role` CHECK constraint is `('user', 'assistant', 'system')` — **no `'tool'` role**, so tool turns are not persisted; only the user question and the assistant answer are. `model_run_id` is already a column on `chat_messages`.

Streaming is chat-only (C8). When the client requests it, the response is `text/event-stream`. **Mid-stream failure semantics** — the thing §9 of [docs/ARCHITECTURE.md](ARCHITECTURE.md) already lists as an expected problem type:

- Once the 200 headers are sent, the status cannot change. A failure terminates the stream with an `error` event; the client renders the partial text and the failure marker.
- A failed chat turn is **not** persisted. `app.chat_messages` holds complete exchanges only, so a replay never contains a half-answer.
- A failure *before* the first byte is an ordinary RFC 9457 problem response.

## 11. Hallucination detection: what we build and what we do not

### 11.1 The question

Should a hallucination-detection phase use an LLM as judge?

**No, not in the request path.** The judgement is grounded in the concrete use case rather than in general principle.

### 11.2 Why the judge is the wrong instrument here

**It cannot be more reliable than the arithmetic it approximates.** The dominant failure mode is a number — "€12.4M" where the database says "€9.1M". Checking that is a lookup. A judge asked to perform it must itself read the fact bundle and compare, which is a deterministic operation performed by a stochastic process, using a model of the same class as the generator and sharing its blind spots.

**The literature points the same way.** Three papers from the last three weeks bear directly on it:

- *Counterfactual Pairwise Augmentation Improves Small Pointwise LLM Judges* (arXiv 2610.41149): a small LM serving as a pointwise judge "must locate the criterion's decision boundary", and pointwise labels under-determine it — the paper's contribution is **fine-tuning data** for small judges. A zero-shot 9B judge is precisely the under-determined case.
- *AGORA: Reliability-Aware Aggregation of LLM Judges via Item-Response Theory* (arXiv 2611.05556): even a pool of frontier judges needs reliability-weighted aggregation, because "per-item mean weights weak judges as heavily as strong ones". A single local 9B judge is the degenerate case of that.
- *To Jev or Not to Jev: When Can System-1 Decision Models Replace LLM Judges?* (arXiv 2611.00505): the trend is toward **decision models replacing generative judges** for cheap verification — away from LLM judges for exactly this kind of check.

**It costs the feature its latency.** A second pass over the report and its facts is another 10-15 seconds on a 5060 Ti at 40-60 t/s, in the week the Flutter client also has to land.

**And it misses the failures that matter.** Classifying the actual hallucination surface of this report — ~32 numeric assertions plus interpretive claims:

| Class | Example | A judge catches it? | The right instrument |
| --- | --- | --- | --- |
| Literal number | "€12.4M" vs "€9.1M" | Worse than code | **Structural** (§7.2) + extraction (§8.2 L2) |
| Derived value | Ratio inverted: 25/45 = 0.55 | Worse than code | **Deterministic** — the backend computes it |
| Unsupported qualitative | "líder nato en el campo" | No — it is opinion, absent from the data | **Prompt + schema scope** (§7.3) |
| Population claim | "mejor valor que el 80% de los delanteros" | **No** — a judge given only the fact bundle cannot detect it either | **Schema scope** — the claim is not permitted |

The judge would spend 15 seconds detecting what 60 lines of code detects exactly, while missing the two classes it cannot reach.

### 11.3 Where a judge is still the right tool: measurement

One use survives, and it is not a runtime gate. An **offline, sampled, non-blocking** judge over a set of generated reports produces a *measured* faithfulness rate for [docs/REPORT_NOTES.md](REPORT_NOTES.md) — "N reports generated, M claims judged unsupported" — turning the judge from runtime infrastructure into a **methodology result**, which is worth more in a data-mining course than a runtime gate would be.

Even there, the deterministic checker produces the **headline** number: it is exact, reproducible, and free. The judge covers the semantic residue — does the prose contradict the facts in ways extraction misses — and its result is reported as a secondary, lower-confidence measurement, with its agreement against the deterministic count stated. Two instruments, one exact, is a stronger methodology section than either alone.

This is a week-8 task (§18) and it does not block the feature.

## 12. Data model changes

One migration, `0004`, on the `app` branch.

**`app.reports`** — three columns added:

| Column | Type | Purpose |
| --- | --- | --- |
| `source` | `VARCHAR(16) NOT NULL DEFAULT 'llm'` | `llm` or `deterministic` (C5) |
| `llm_model` | `VARCHAR(128) NULL` | The model id that produced the text; `NULL` for the deterministic source |
| `prompt_version` | `VARCHAR(32) NULL` | The prompt version **and the sampling configuration**; a change to either invalidates the cache |

`llm_model` and `prompt_version` are the provenance [docs/ARCHITECTURE.md](ARCHITECTURE.md) §9 already promises ("reports record the model version used") and the schema does not deliver. They are also **required for cache correctness**: `get_latest_player_report` keys on `(player_id, model_run_id, report_type)` with no model in the key, so the C1 model swap would otherwise serve stale 3B-written reports indefinitely. The key becomes `(player_id, model_run_id, report_type, llm_model, prompt_version)`.

**`prompt_version` encodes the sampling configuration, not only the prompt text.** The report path is non-deterministic, and E7 (§17.4) will select `temperature`, `top_p` and `top_k` from a measured grid. Two reports generated from the same fact bundle at different temperatures differ in wording, so a temperature change is a change in output as real as a prompt change. The version string therefore covers both: `PROMPT_VERSION = "v1-t0.7-p0.8-k20"`, incremented whenever either the prompt text or the sampling parameters change. A separate `sampling_config` column would be cleaner but is more than the provenance the architecture promises; folding it into the version keeps the cache key honest at no schema cost.

**`app.reports.report_type`** — the CHECK constraint is added over **`('scouting')`**, and the column is left as `VARCHAR(64)`.

The vocabulary is narrowed from the spec's earlier `('scouting', 'replacement', 'cluster')` because the evidence says only one report kind exists:

- The endpoint has exactly one generator. `generate_report` (`api/reports.py:74-87`) builds one context and calls `generate_llm_report_text` regardless of `report_type`.
- The design preview has exactly one report surface — *"Informe para Dirección Deportiva"* (`frontend/design-preview/index.html:1989`), the player scouting report.
- No caller anywhere passes a non-default `report_type`; the frontend preview never sets one, and every backend test uses `"scouting"`.

**There is a live bug behind this.** `report_type` is used *only* as a cache key; the generator ignores it. So today a request with `report_type='replacement'` generates a **scouting** report and stores it under the key `'replacement'` — a silently wrong record, and the exact typo-duplication the CHECK was meant to prevent. Narrowing the CHECK to the one type that has a generator closes both the typo hole and the silent-mismatch hole. The API layer also rejects any other value with a 422 rather than generating the wrong content.

Widening the vocabulary later is a one-line migration change, and it should happen when a second generator exists — not before, because a CHECK that admits `'replacement'` and `'cluster'` today invites exactly the silent mismatch described above.

**`app.chat_sessions`** — no change. The existing columns (`id`, `title`, `created_at`, `updated_at`) suffice.

**The migration file.** `0004` continues the `app` branch: `down_revision = "0003"`, and `branch_labels = None`.

**The branch label is inherited, not re-declared.** Alembic enforces **global uniqueness** of branch labels: `_map_branch_labels` (`alembic/script/revision.py:314-334`) raises `RevisionError: Branch name 'app' in revision 0004 already used by revision 0003` if two revisions declare the same label. So `0004` must **not** re-declare `("app",)` — that breaks every alembic command, including the compose `migrate` service. With `branch_labels = None` the label is inherited from the parent (`_add_branches`, same file, lines 336-354, propagates a parent's label to its descendants), and the result is verified:

```
$ alembic heads
0002 (analytics) (head)
0004 (app) (head)

$ alembic history
0001 -> 0002 (analytics) (head), ...
0003 -> 0004 (app) (head), ...
0001 -> 0003 (app), ...
```

This matters because `0002` (analytics) and `0003` (app) are **two separate heads** off `0001` (`migrations/versions/0002_analytics_tables.py:15-16`, `0003_app_tables.py:13-16`). The compose migrate service runs `alembic upgrade heads` — plural — which upgrades every head (`docker-compose.yml:44`), so a `0004` on the `app` branch is applied alongside `0002` and does not disturb it.

**`app.chat_messages`** — no change. The existing `role` CHECK `('user', 'assistant', 'system')` already covers what is persisted (§10.5).

## 13. Configuration keys

[docs/ARCHITECTURE.md](ARCHITECTURE.md) §9 and [.env.example](../.env.example) are the contract for configuration keys, and both must be updated in the same change (AGENTS.md §4). The current state is broken in three ways: `.env.example` documents only `DELPHOS_LLM_API_URL`; `docker-compose.yml` passes only that one key; and `core/config.py` defines five LLM keys, three of which are undocumented.

| Key | Default | Meaning |
| --- | --- | --- |
| `DELPHOS_LLM_API_URL` | `http://inference-chat:8080/v1` | llama.cpp base URL. **Already exists.** |
| `DELPHOS_LLM_MODEL_NAME` | `qwen/qwen3.5-9b` | Model id sent in the request. Must match the served model (§6.1) and must be lowercase for the PydanticAI Qwen3.5 profile to apply (§7.2). **New.** |
| `DELPHOS_LLM_TIMEOUT_SECONDS` | `120.0` | Per-request timeout. Raised from 45.0: a 1200-token report at 40-60 t/s takes 20-30 s, plus prefill. **New.** |
| `DELPHOS_LLM_MAX_TOKENS` | `512` | Chat completion cap. Kept for chat. **New.** |
| `DELPHOS_LLM_REPORT_MAX_TOKENS` | `1400` | Report completion cap. Replaces the 512 default, which truncates a three-section report. Sized for **Spanish** prose, which costs ~11% more tokens than English (§7.6). **New.** |
| `DELPHOS_LLM_TEMPERATURE` | `0.7` | Per the Qwen3.5 card's non-thinking sampling (`temperature=0.7, top_p=0.8, top_k=20, presence_penalty=1.5`). Replaces 0.2. **Provisional — E7/E8 (§17.4) measure this and set the shipped value.** **New.** |
| `DELPHOS_LLM_TOP_P` | `0.8` | As above. Provisional pending E7/E8. **New.** |
| `DELPHOS_LLM_TOP_K` | `20` | As above. Provisional pending E7/E8. **New.** |
| `DELPHOS_LLM_PRESENCE_PENALTY` | `0.0` | The card recommends `1.5` for non-thinking general tasks, but a repetition penalty penalises re-using a token, and a grounded report must re-use tokens like `€` and the player's name. **Left off pending E9 (§17.4), which measures whether it costs faithfulness.** **New.** |
| `DELPHOS_LLM_CONTEXT_SIZE` | `32768` | Server context, mirrored in compose for the backend's budget arithmetic. **New.** |
| `DELPHOS_LLM_MAX_TOOL_ITERATIONS` | `4` | Chat tool-loop cap (§10.3). **New.** |
| `DELPHOS_LLM_CHAT_HISTORY_TURNS` | `8` | Chat history cap (§10.4). Stated in tokens, not exchanges, because a Spanish turn is longer (§7.6). **New.** |
| `DELPHOS_LLM_ENABLE_THINKING` | `false` | Whether the model reasons before answering. Sent **per request** as `chat_template_kwargs: {"enable_thinking": <bool>}`, which llama.cpp accepts on `/v1/chat/completions` (`tools/server/README.md:1449`). **Provisional — E5 (§17.3) measures it separately for the report and the chat, and the answer may differ.** **New.** |

`DELPHOS_LLM_MAX_TOKENS` currently means "the report's cap" and is used as such in `llm_reports.py:104`. It is **repurposed** for chat and the report gets its own key, so the two features can be tuned independently.

**The sampling defaults are a starting point, not a decision.** The Qwen3.5 card's `temperature=0.7, top_p=0.8, top_k=20` is tuned for *general* chat, and the two features here are narrower: the report is a grounded structured generation, and a chat tool argument is a discrete value that sampling can corrupt. E7 and E8 (§17.4) measure both against their own criteria and set the shipped values; whatever they select is recorded in `PROMPT_VERSION` (§12) so the cache stays correct.

## 14. Module layout

The backend's own guide ([backend/AGENTS.md](../backend/AGENTS.md)) caps modules at roughly 130 lines. `llm_reports.py` is already 127 lines, so it must be split rather than extended.

```
backend/src/delphos_backend/
  core/
    config.py                 # extended: the LLM keys of §13
  services/
    llm_client.py             # NEW. OpenAI-compatible httpx client shared by both features.
                               #   Owns: base URL, model name, timeouts, sampling, error mapping.
    report_facts.py           # NEW. Fact-card assembly: facts + fact_ref keys + formatted values.
    report_prompt.py          # NEW. The Spanish system prompt + PROMPT_VERSION.
    report_schema.py          # NEW. ScoutingReportDraft / ReportSection Pydantic models.
    report_render.py          # NEW. Deterministic renderer (the §7.5 port).
    report_verify.py          # NEW. Numeric extraction check + repair prompt (§8.2).
    llm_reports.py            # REWRITTEN. Orchestrates the report pipeline (§7.1).
                               #   Keeps: assemble_player_scouting_context -> moves to report_facts.
    chat_tools.py             # NEW. The five typed tools (§10.2).
    chat_agent.py             # NEW. The tool loop (§10.3).
  api/
    reports.py                # EXTENDED. source, llm_model, prompt_version on the response.
    chat.py                   # NEW. POST /chat, GET /chat/sessions, GET /chat/sessions/{id}.
  schemas/
    reports.py                # EXTENDED. ReportResponse gains source/llm_model/prompt_version.
    chat.py                   # NEW. ChatRequest / ChatResponse.
  repositories/
    chat.py                   # NEW. Session and message persistence.

ml/src/delphos_domain/
  __init__.py                 # NEW. Package facade (ADR-013: its own uv project, no deps).
  labels.py                   # NEW. Dependency-free Spanish vocabulary (§9.2).
```

`report_render.py` and `report_facts.py` are the two modules worth testing hardest: the renderer is the correctness floor and the fact builder is what makes verification possible.

**Note the vocabulary package is `ml/src/delphos_domain/`, not `ml/src/delphos_ml/domain/`.** §9.2 explains why: a submodule of `delphos_ml` still executes `delphos_ml/__init__.py`, which imports sklearn, pandas, numpy, scipy and pyarrow, so it isolates the file but not the import. A separate leaf distribution isolates both, and it keeps the backend's install small.

`delphos_domain` is its own uv project with **no dependencies at all**, so it adds no version-alignment burden under ADR-013 — the seven joblib-relevant versions are untouched by it. The backend's `pyproject.toml` adds it as a path dependency, and `backend/Dockerfile` copies `ml/src/delphos_domain` alongside `backend/src`.

## 15. API surface

The OpenAPI spec FastAPI generates is the contract of record ([docs/ARCHITECTURE.md](ARCHITECTURE.md) §4.1).

| Method | Endpoint | Status | Description |
| --- | --- | --- | --- |
| `POST` | `/reports/generate` | **Extended** | Unchanged contract. Gains `source`, `llm_model`, `prompt_version` in the response. No longer 503s on an LLM outage. |
| `GET` | `/reports` | Unchanged | |
| `GET` | `/reports/{id}` | Unchanged | |
| `POST` | `/chat` | **New** | Natural-language question → answer. Streams when requested. |
| `GET` | `/chat/sessions` | **New** | List the user's sessions, newest first. |
| `GET` | `/chat/sessions/{id}` | **New** | A session's exchanges, for the frontend to restore a conversation. |

**`GET /chat/sessions` is included.** The open item was whether sessions are listed or only fetched by id. The evidence settles it: `app.chat_sessions` already has `title`, `created_at` and `updated_at` (`migrations/versions/0003_app_tables.py:47-53`) — columns that exist to *display a list*, not to fetch one by id. A `title` on a row you can only retrieve by opaque UUID is unused surface. The endpoint is also the natural counterpart to `POST /chat`, which returns a `session_id` the client must then be able to enumerate.

It is a small read-only query against an existing table, and it is the difference between a chat feature that can be *used* (open "last conversation") and one that cannot.

**`GET /chat/sessions/{id}`** returns the session's messages in order, and the response carries the session `title` and `updated_at` so a list view can render without a second call.

`POST /chat`:

```json
// Request
{ "message": "¿Qué delanteros infravalorados hay en la Premier League?", "session_id": null, "stream": false }

// Response
{
  "session_id": "0f3c...",
  "message": "En la temporada 2025 la Premier League registra 34 delanteros infravalorados...",
  "model_run_id": "20261103_143012",
  "tools_called": ["search_players"],
  "created_at": "2026-11-20T10:15:00Z"
}
```

## 16. Tests

The backend suite is 18 tests today; the LLM work adds to it.

**Report pipeline.**

- Fact-card assembly: every fact has a key and a formatted value; nulls render `N/D`.
- The deterministic renderer: golden output for a fixture player, covering the positive and negative financial-verdict branches, and a player with zero qualifying replacements (`shortfall_reason` path).
- Numeric extraction: a prose string with an injected number is rejected; a clean one passes.
- The generation call: the request carries `response_format` with the schema; a malformed response is rejected and the deterministic path is taken.
- The fallback path: an LLM timeout, an HTTP 500, and an empty completion all yield a 200 with `source='deterministic'`.
- Cache correctness: a report generated by a different `llm_model` or `prompt_version` is not served from the cache.

**Chat.**

- Each tool's argument validation, including the out-of-range and unknown-value cases.
- The loop cap: a model that keeps calling tools is stopped at 4 iterations.
- An unknown tool name and a failing tool return a typed error, not a 500.
- Context budget: a long session is trimmed to the configured history cap.

**Not in v1 scope**, per the project's testing convention: contract tests, OpenAPI drift checks, CI, and a golden batch-vs-live equivalence check.

**Manual verification, before the feature is called done.**

1. `llama-server` starts, loads Qwen3.5-9B, and `/props` shows a tool-aware template.
2. **The startup log reports `n_ctx_slot = 32768`, not 8192.** This is the check that the `kv_unified` fix took effect (§6.2). The server prints `initializing, n_slots = %d, n_ctx_slot = %d` at startup; if it says 8192, the context is still being divided and the chat will truncate.
3. A tool call is emitted **outside** the reasoning block (llama.cpp #20837).
4. `enable_thinking=false` actually takes effect in the shipped build (#20409 family).
5. `llama-bench` on the target card, to replace the derived throughput figures with measured ones.
6. A 20-case tool-call eval, to compare Qwen3.5-9B against Granite 4.2-8B before the fallback is needed.
7. A sample of generated reports read for **Spanish register and terminology** (§7.6): football terms match the vocabulary, no English leaks, currency and decimal separators match the UI, and the prose is better than the deterministic renderer's. The last clause is the one that decides whether the LLM path ships at all.
8. If `draft-mtp` is to be enabled at all: the server starts cleanly with it, and `/props` reports an active spec type (§6.2).

## 17. Experiments

The experiments answer the questions that decide whether each part of this plan ships. They are **measurements, not tests**: each one has a hypothesis, a controlled variable, an instrument, and a threshold that turns it into a decision. A measurement without a threshold is a curiosity.

Three rules govern all of them.

**Fix the seed.** Every request carries an explicit `seed` (llama.cpp accepts it per-request on `/v1/chat/completions`). Without it, two runs of the "same" configuration differ by sampling noise, and every comparison below is confounded. Each experiment states its seed set.

**Change one variable at a time.** The experiments are ordered so that the cheap, decisive ones run first and the expensive grid runs last, against settings already chosen by the earlier ones.

**Every experiment has a fallback decision.** The outcome is not a report; it is a configuration change or a cut. An experiment that cannot change what ships was not worth running.

**Harness.** The experiments live in the top-level `analysis/` directory and run from `ml/` through the `analysis` dependency group ([ADR-014](ARCHITECTURE.md)), exactly as the existing ML analysis scripts do — `uv run python ../analysis/llm_eval/exp_report_quality.py` from `ml/`. They write to `analysis/output/llm/` (gitignored, regenerable) and touch nothing in the deployed stack. They talk to the inference service over its OpenAI-compatible HTTP API and to the backend over REST, so they measure the *shipped* configuration, not a reimplementation of it.

New files:

| File | Purpose |
| --- | --- |
| `analysis/llm_eval/harness.py` | Shared: build a request, call the server, record the response, seed, timings, and the raw JSON. Writes one JSONL row per call. |
| `analysis/llm_eval/cases_report.py` | The report case set: players spanning the 3 clusters × 3 valuation zones. |
| `analysis/llm_eval/cases_chat.py` | The chat case set: 20 questions, each with the tool it should call and the facts it should surface. |
| `analysis/llm_eval/exp_report_quality.py` | E1–E3 (§17.2). |
| `analysis/llm_eval/exp_tool_calling.py` | E4–E6 (§17.3). |
| `analysis/llm_eval/exp_sampling.py` | E7–E9 (§17.4). |
| `analysis/llm_eval/report.py` | Renders every JSONL into the tables and figures for [docs/REPORT_NOTES.md](REPORT_NOTES.md). |

The `analysis` dependency group in `ml/pyproject.toml` gains `httpx` (for the HTTP calls; it is already a backend dependency) and `pandas` (already a `delphos_ml` runtime dependency, so it needs no new declaration). `analysis/llm_eval/` is a package directory with an `__init__.py`, so the scripts import `harness` rather than each other by path. The DB access uses `psycopg`, already a `delphos_ml` runtime dependency.

**One note on ADR-009's rule** that analysis scripts "import `delphos_ml` and read `ml/data/<stage>/`". The LLM experiments read the *published database*, not the local Parquet, because the case sets need `valuation_status` and `cluster_id` — and those exist only after `train` and `publish`: `ml/data/transform/player_seasons.parquet` has 36 columns and carries neither. `valuation_status` is written to `analytics.fct_player_predictions` (`migrations/versions/0002_analytics_tables.py:149`) and `cluster_id` to `analytics.fct_clusters` (line 171). The experiments therefore query the `analytics` schema through the same read-only path the backend uses, so the cases are the *published* players the product actually serves. This is worth stating in [docs/ARCHITECTURE.md](ARCHITECTURE.md) §10 as a scope note on ADR-014 rather than leaving the convention quietly stretched.

### 17.1 The instruments

Four instruments, chosen so that the strongest claims rest on the deterministic ones.

| Instrument | What it measures | Why it is trusted |
| --- | --- | --- |
| **D1 — numeric verification** | Whether every number in the prose appears in the fact bundle | Exact and free (§8.2 L2). Reproducible. |
| **D2 — schema conformance** | Whether the structured output matches `ScoutingReportDraft` | Exact. The grammar makes it structurally impossible to violate. |
| **D3 — tool-call conformance** | Whether the emitted call names a real tool and parses into the tool's schema | Exact. Argument types are known. |
| **J1 — LLM judge** | Faithfulness, register, and report-vs-report quality | Impressionistic. Used only where the others cannot reach, and always reported next to a deterministic count. |

**D1 and D2 are the headline numbers.** A report that passes both is *provably* free of fabricated numbers and structural errors. J1 then covers what neither can see: does the prose contradict a fact without introducing a number, and does it read like a scouting director wrote it.

**The judge must be blind to which system produced the text.** A judge that sees "system A" and "system B" has known position and verbosity biases. Every J1 comparison is therefore **pairwise and anonymised**: the two texts are presented in a randomised order under neutral labels, and the judge states a preference with a reason. This matters more than it sounds — it is the difference between a usable measurement and a number that reproduces the judge's prior.

**Human rating is the tiebreaker.** The team is two people. A blind pairwise read of LLM-versus-deterministic reports, scored independently, is the instrument that decides the question the judge cannot: *is the LLM report actually better than the template?* On E1's 9 cases that is about 20 minutes of reading, and it settles §7.5's cut rule.

### 17.2 Report quality (E1–E3)

**E1 — Does the LLM report beat the deterministic renderer?**

*Hypothesis:* the LLM prose is preferable to the template for a human reader.

*Cases:* 9 players — one per (cluster × valuation zone) cell, where the zone is `undervalued` / `fair` / `overvalued`. The three zones matter because the financial verdict branches on the sign of `fair_value - market_value`, so the template's hardest case is the one the LLM is most likely to get wrong. The cluster dimension matters because the three archetypes have different vocabulary (§9).

*Design:* for each player, generate the LLM report and render the deterministic one, then compare blind: J1 pairwise preference (randomised order) plus human pairwise reading.

*Metrics:*
- Preference rate for the LLM report, with the pairwise order randomised.
- D1 violations per report (must be 0).
- Human preference rate.

*Decision rule:* the LLM path ships if the blind human preference rate for it exceeds 50% **and** D1 violations are zero. If it ties or loses, the deterministic renderer ships for every report and the LLM work stops at that point — the feature still exists, and it is still correct. This is the experiment most likely to end the project early, and that is the point of running it first.

*On the sample size, stated honestly:* 9 cases cannot establish a small quality difference. A 5-of-9 preference is indistinguishable from a coin flip, and a 9-of-9 is overwhelming. The experiment therefore resolves a **large** effect — "the LLM report is clearly better" or "it is not" — and not a marginal one. If the human rating lands at 6 or 7 of 9, the result is *inconclusive*, and the honest response is to report it as such and let the J1 preference rate break the tie; it is not a licence to call a 6-3 win. If the schedule allows, the case set grows to 18 (two players per cell) and the reading is repeated, which is the only way a marginal result becomes decidable. The decision rule above is written for the clear-effect case, which is the one that matters for a shipping decision.

*Cost:* 9 LLM generations (about 4 minutes at 40 t/s) plus reading time.

**E2 — Does the Spanish register hold?**

*Hypothesis:* the report reads as executive Spanish football prose, with no English leakage and no invented terminology.

*Cases:* the same 9 players.

*Instrument:* J1 scores each report on three axes — **terminology** (does it use the §9 vocabulary, and no invented football terms?), **register** (is it executive Spanish rather than English or machine prose?), and **formatting** (does every number use the product's `€25.0M` format, with no bare `25.0M` and no Spanish `25,0 M€`?).

*Metrics:* per-axis pass rate out of 9, and the count of formatting violations (checked deterministically, since D1 already extracts every numeric token — the *format* of each is a regex check against `formatEurM`).

*Decision rule:* if the terminology or formatting pass rate is below 8/9, the failures are inspected and either the prompt (§7.3) or the fact-card labels (§8.1) are corrected, then the 9 cases are re-run. If the register pass rate is below 8/9 after one correction round, the LLM report is not shipped and the deterministic renderer is used — Spanish executive prose is the whole point of the feature, and a report that reads in English is not a small defect.

*Why formatting is deterministic:* it would be sloppy to let a judge adjudicate `€25.0M` versus `25,0 M€`. D1 already extracts the numeric tokens; a format regex over them is exact and free.

**E3 — Do the fact cards stay within the token budget?**

*Hypothesis:* the fact card plus the prompt fits the context with room for the response.

*Cases:* the 9 players.

*Metrics:* prompt tokens (from the server's reported `prompt_n`), completion tokens, and the total against the 32K context.

*Decision rule:* if prompt tokens exceed 8000 for any case, the card builder is pruned (§8.1) before anything else ships. This is cheap to run and it prevents the failure from appearing as a truncation bug in production.

### 17.3 Tool calling and conversation (E4–E6)

**E4 — Does the model call the right tool with the right arguments?**

*Hypothesis:* on a natural-language question, the model selects the intended tool and fills its arguments correctly.

*Cases:* 20 questions, hand-written to span the five tools and the natural failure modes. Each case records the expected tool and the expected arguments, plus the facts the answer must contain.

| # | Shape | Expected |
| --- | --- | --- |
| 1–4 | `search_players` — by position, league, valuation zone, and a compound filter | the right filters, including the league as a `league_id` |
| 5–8 | `get_player_profile` / `get_player_valuation` — "how much is X worth", "who is X" | the right player, resolved from the name |
| 9–12 | `get_player_replacements` — "who could replace X", "cheaper alternatives" | the right player |
| 13–16 | `get_cluster_summary` — "what is a Box-to-Box", "tell me about creative creators" | the right cluster |
| 17–18 | **multi-step** — "find me a cheap striker under 10M in La Liga" | `search_players`, then `get_player_valuation` on the best hit |
| 19 | **out-of-scope** — "who won the 2019 Champions League final?" | **no tool**; a refusal, not a fabricated answer |
| 20 | **non-existent entity** — "escribe un informe sobre Marco Nobody" | the empty-result path, and an honest "not found" |

Cases 19 and 20 are the ones that catch the dangerous failure: a plausible-sounding answer with no data behind it. Case 19 is the *unanswerable* case and it must produce a refusal.

**The fictional name must genuinely not exist.** The first draft of this case used "João Silva" — which turns out to be a **real player** in the dataset (2 of 42,612 names match). A case built on a real player tests name resolution, not the empty-result path, and would pass for the wrong reason. The case set is therefore checked against `ml/data/clean/players.parquet` when it is written: every non-existent entity in a case must have zero matches. "Marco Nobody" is the current choice, verified absent.

**Every real player named in a case must be present in the published data, and named exactly as the dataset spells them.** The same check applies in the other direction, and the dataset's spellings are not the obvious ones: "Kylian Mbappe" is **absent** while "Lionel Messi", "Erling Haaland", "Neymar", "Lamine Yamal" and "Vinicius Junior" are present. A case naming a real player who is not in the data tests the empty-result path by accident, and a case naming one with the wrong spelling does the same. Every player named in a case is therefore resolved against `players.parquet` **and** against `analytics.fct_player_predictions` for the active run, and the case set records the resolved `player_id` — so the expected tool argument is a fact, not a guess.

*Metrics (all deterministic, D3):*
- **Tool selection accuracy** — the fraction of cases where the first call is the expected tool.
- **Argument exact-match accuracy** — the fraction where every argument equals the expected value. This is stricter than "the tool was right" and it is the metric that predicts a working feature: a right tool with a wrong `league_id` returns the wrong rows.
- **No-call rate on answerable cases** — the fraction where the model answered without calling a tool. Every one is a hallucinated answer.
- **Refusal accuracy on case 19** — must be 1.0.
- **Loop exhaustion** — the fraction hitting the 4-iteration cap (§10.3).
- **Call count** — the mean, against the expected 1.0 for single-tool and 2.0 for multi-step cases.

*Decision rule:* the chat feature ships if argument exact-match ≥ 0.80, no-call rate on answerable cases = 0, and refusal accuracy = 1.0. Argument exact-match below 0.80 means the tools are too hard for this model, and the cut order (§18) drops the chat feature rather than shipping an unreliable one.

**E5 — Does thinking off cost accuracy?**

This is the experiment that decides the `DELPHOS_LLM_ENABLE_THINKING` setting (§13), and it is asked twice because the answer may differ per feature.

*Hypothesis:* reasoning improves tool-argument accuracy, but the tool call lands inside the reasoning block where the grammar cannot parse it (llama.cpp #20837) — so reasoning **on** is unusable for tool calling regardless of its accuracy, and is merely optional for the report.

*Design:* for each of the 20 cases, run the same request under three conditions.

| Condition | How | What it isolates |
| --- | --- | --- |
| **T-off** | `chat_template_kwargs: {"enable_thinking": false}` | The shipped configuration. |
| **T-on** | `chat_template_kwargs: {"enable_thinking": true}` | The accuracy ceiling, if parsing worked. |
| **T-on-reasoning-off** | server started with `--reasoning off` | Whether the *server* flag and the *template* flag are the same switch. |

The third arm exists because they are **different mechanisms**. `enable_thinking` is a Jinja template variable (the model's own `chat_template.jinja` reads it at line 149 and emits an empty `<think>\n\n</think>` block); `--reasoning off` is a llama.cpp server-level switch. The #20409 family of issues reports the template toggle being ignored in some builds. Running all three distinguishes "thinking is off" from "the toggle works" from "the toggle is ignored".

*Metrics:* per condition — argument exact-match, no-call rate, **tool-call parse rate** (did the call appear as a structured tool call at all, or as prose inside the reasoning block?), mean completion tokens, and wall-clock latency.

*Decision rule:*
- If T-on's parse rate is materially below T-off's, thinking off is **required** for chat, and the accuracy comparison is reported as the cost of that requirement — a number for [docs/REPORT_NOTES.md](REPORT_NOTES.md), not a reason to ship a broken path.
- If T-on parses correctly and its argument exact-match is clearly higher, the report should use thinking on and the chat should use thinking off, and the server is run with `--reasoning auto` so the choice is per-request.
- If T-on-reasoning-off behaves like T-off, the server flag is authoritative and the compose setting is correct as written.

**How the arms are run.** T-off and T-on are per-request `chat_template_kwargs` and need no server restart. The third arm requires the server to be started with `--reasoning off`, so it is a **separate server run** — which is why it is listed last: it is the most expensive arm and the least likely to change the decision. If the schedule is tight, run T-off and T-on first; the third arm only matters if they disagree.

The report path gets the same three-arm treatment on the 9 report cases (E1's cases), scoring prose quality (J1), D1 violations, and latency. The hypothesis there is weaker — reasoning may improve prose — but the *cost* is known: thinking multiplies completion tokens, and at 40 t/s a 1400-token report with 2000 tokens of reasoning costs 85 s against 35 s, which is the difference between fitting the 120 s timeout (§13) and not.

**E6 — Does the chat hold a conversation?**

*Hypothesis:* the model uses earlier turns, stays consistent, and does not drift off the data.

*Design:* 6 scripted multi-turn conversations, each 5 turns, on one player. The transcripts deliberately include a **correction** (turn 3 contradicts turn 2) and an **unanswerable** turn.

*Metrics:*
- **Context use** — does turn 4's answer use a fact established in turn 1 without being restated?
- **Correction handling** — after turn 3's correction, does turn 4 follow the corrected value?
- **Consistency** — no contradiction between turns.
- **Drift** — no turn answers from outside the published facts.
- **Latency per turn** and **context growth** per turn, against the §10.4 budget.

*Instrument:* J1 for the semantic judgements (context use, correction handling), with D1 applied to every numeric claim in every turn, so "did it state a wrong number" is deterministic even though "did it use turn 1" is not.

*Decision rule:* the chat feature ships with streaming only if the no-drift rate is 1.0 across all turns — a chat that invents a plausible fact is worse than no chat. The correction and context metrics are reported as quality numbers.

### 17.4 Sampling parameters (E7–E9)

The Qwen3.5-9B card recommends `temperature=0.7, top_p=0.8, top_k=20, presence_penalty=1.5` for non-thinking mode on general tasks (§13 already ships the first three). The card's recommendation is for *general* chat; a grounded scouting report is a narrower task with a different optimum, and the plan should measure rather than assume.

**The decisive constraint:** the report path is **non-deterministic by nature** and the spec's §12 cache key includes `prompt_version` but not the sampling parameters. Two reports generated from the same fact bundle at different temperatures differ. This is acceptable — but it means the *chosen* parameters must be recorded in `app.reports`, or the provenance is incomplete. §12's `prompt_version` is extended to cover the sampling configuration.

**E7 — Sampling sweep on the report path.**

*Hypothesis:* a lower temperature produces a more faithful and more repeatable report without losing prose quality.

*Design:* the 9 report cases × a parameter grid, 3 seeds each. The grid is small and ordered:

| Arm | temperature | top_p | top_k | Rationale |
| --- | --- | --- | --- | --- |
| A (shipped default) | 0.7 | 0.8 | 20 | The card's non-thinking general-task recommendation (§13). |
| B | 0.2 | 0.8 | 20 | The backend's current default (`llm_temperature = 0.2`, `core/config.py:46`). |
| C | 0.4 | 0.9 | 40 | The midpoint; llama.cpp's own defaults are `top_k=40, top_p=0.95`. |
| D | 0.1 | 0.8 | 20 | Near-greedy, to locate the faithfulness ceiling. |

*Metrics per arm:*
- **D1 violation rate** — the faithfulness signal.
- **Cross-seed similarity** — the Jaccard similarity of the set of fact references across the 3 seeds of one case, averaged. Higher means *more* repeatable. This is what a scouting director experiences when they regenerate a report, and it is the metric that separates "the report is consistently about this player" from "each regeneration says something different". (Named similarity, not variance, because higher is better — the opposite of variance, and the confusion would be costly here.)
- **Prose quality** (J1) against arm A, blind and paired.
- **Degeneracy** — the fraction of outputs with a repeated 8-gram, and the fraction that are lexically identical across seeds. Quantization artifacts show up here as repetition (llama.cpp #28581's `IQ3_S` garbage is the extreme case).
- **Latency** — mean completion tokens and t/s, since a lower temperature does not change throughput but a shorter completion does.

*Decision rule:* pick the arm with **zero D1 violations** and the **highest cross-seed similarity** among those, unless a lower-temperature arm loses on prose quality by more than one J1 preference point, in which case prose wins. Record the chosen parameters in `app.reports` alongside `prompt_version`.

If every arm has a nonzero violation rate, the fault is in the prompt or the schema, not the temperature — and that is a more valuable finding than a winning arm.

**E8 — Sampling sweep on the chat path.**

Same grid, on the 20 tool-call cases from E4, scoring argument exact-match and no-call rate instead of prose.

*Hypothesis:* tool-argument accuracy is sensitive to temperature, and lower is better, because an argument is a discrete value that sampling can corrupt — `ES1` versus `ES2`, `2025` versus `2024`, a `player_id` off by one.

*Metric:* argument exact-match per arm, plus the **error magnitude** on failures (a wrong league versus a wrong player are different bugs).

*Seeds:* **2 seeds per arm**, not 1. A single-seed measurement of 20 cases has a standard error of roughly 9 percentage points at 80% accuracy — wide enough that two arms differing by one or two cases would be indistinguishable, which is exactly the difference this experiment is looking for. Two seeds halve that variance for about 40 extra runs, and if the two arms still tie, the honest conclusion is that temperature does not matter for tool arguments, which is itself worth knowing.

*Decision rule:* the chat arm with the highest argument exact-match wins, tie-broken toward the lower temperature. Unlike the report path, chat has no prose-quality constraint to trade against, so this decision is one-dimensional.

**E9 — The repetition-penalty knob.**

*Hypothesis:* `presence_penalty` (the card's 1.5) helps prose variety and does not hurt faithfulness.

*Design:* arms A and A+`presence_penalty=1.5` on the 9 report cases and the 20 chat cases.

*Rationale:* `presence_penalty=1.5` is the card's recommendation and it is currently **not** in §13's configuration. But a repetition penalty applies to *every* token, and in a grounded report the same fact legitimately appears twice ("el jugador" then "el extremo derecho"). The penalty may therefore damage faithfulness — a real risk, and one that only measurement settles.

*Metrics:* D1 violations, repeated-8-gram rate, prose diversity (distinct-3-gram ratio), and J1 prose quality.

*Decision rule:* adopt `presence_penalty=1.5` only if D1 violations stay at zero and the degeneracy rate improves. Otherwise leave it unset. **Never enable `repeat_penalty`** for the report path: it penalizes re-using a token, and the report must re-use tokens like `€` and the player's name.

### 17.5 What the experiments cost, and when

| Experiment | Runs | Wall clock | Gate |
| --- | --- | --- | --- |
| E1 report vs deterministic | 9 | ~5 min | Decides whether the LLM report ships at all. |
| E2 Spanish register | 9 | ~5 min | Decides the prompt and card corrections. |
| E3 fact-card budget | 9 | ~5 min | Decides card pruning. |
| E4 tool calling | 20 | ~10 min | Decides whether chat ships. |
| E5 thinking on/off | 60 | ~30 min | Decides `DELPHOS_LLM_ENABLE_THINKING`. |
| E6 conversation | 30 | ~20 min | Decides streaming and the drift rule. |
| E7 report sampling | 108 | ~55 min | Decides the report's sampling parameters. |
| E8 chat sampling | 160 | ~80 min | Decides the chat's sampling parameters. |
| E9 repetition penalty | 58 | ~30 min | Decides `presence_penalty`. |

**Total ≈ 4.5 hours of GPU time**, all of it on one card. That is affordable inside the schedule, and it is *why* the order matters: E1–E4 cost 25 minutes and can end the project early, so they run first. The sampling sweeps (E7–E9, ~2.7 hours) run only after the configurations they sweep are worth sweeping.

The run counts follow from the designs: E7 is 9 cases × 4 arms × 3 seeds; E8 is 20 cases × 4 arms × 2 seeds; E9 is 29 cases × 2 arms × 1 seed. E5 is 20 cases × 3 arms plus the same three arms on the 9 report cases, which is where its 60 comes from. A run is one LLM generation, and the wall-clock figures assume 30 s each at 40 t/s for a report-sized completion — the chat cases are shorter, so the chat experiments run faster than their proportional share suggests.

The results are written to [docs/REPORT_NOTES.md](REPORT_NOTES.md) as a methodology section — "human preference for LLM prose over a deterministic template: X/9", "tool-argument exact-match: Y/20", "thinking on vs off: parse rate A vs B". For a data-mining course, a measured trade-off with thresholds is worth more than the feature it describes.

**One experiment that is deliberately not here.** There is no experiment to measure whether the LLM report is "good" in the abstract. There is no instrument for that, and an LLM judge asked that question returns a number that measures the judge. Every experiment above compares against a **baseline with a known property** — the deterministic renderer, the expected tool, the expected arguments, the previous seed — which is the only way the result changes a decision.

## 18. Work order and cut order

17 days remain at the time of writing (delivery 2026-11-25 09:00). W7 is 2026-11-11 to 2026-11-17; W8 is 2026-11-18 to 2026-11-25 and holds the final APA report. The work plan already places chat at "only if report polish permits" ([docs/WORK_PLAN.md](WORK_PLAN.md) §3, W8).

**Order.**

| # | Task | Gate |
| --- | --- | --- |
| 1 | `delphos_domain` (Spanish vocabulary) + the backend dependency and the Dockerfile `COPY` | Unblocks the Spanish report and `/clusters`. |
| 2 | Compose: bind the model, CUDA image, flags (`kv_unified` included), `curl` healthcheck | Until this lands, nothing reaches the LLM. |
| 3 | `report_facts.py` + `report_render.py` (deterministic) | The correctness floor exists before any LLM call. |
| 4 | Migration `0004` + provenance columns + the `report_type` CHECK | Cache correctness. |
| 5 | `llm_client.py` + `report_schema.py` + the structured generation call | The LLM path. |
| 6 | `report_prompt.py` (Spanish) + `report_verify.py` | Grounding and verification. |
| 7 | **E1–E4** (§17): report-vs-deterministic, Spanish register, fact-card budget, tool calling | Decides what ships. Cheap, and can end the project early. |
| 8 | **E5** (§17.3): thinking on/off, three arms | Decides `DELPHOS_LLM_ENABLE_THINKING` for both features. |
| 9 | **E6** (§17.3): multi-turn conversation | Decides streaming and the drift rule. |
| 10 | **E7–E9** (§17.4): sampling sweeps | Decides the sampling parameters, and the provenance they force. |
| 11 | `chat_tools.py` + `chat_agent.py` + `api/chat.py` + `repositories/chat.py` | The chat feature — built **after** E4 passes, so it is not built for a model that cannot use tools. |
| 12 | The offline judge sweep | Methodology result for the final report. |

**The experiments are placed in the order, not appended to it.** E1–E4 cost about 25 minutes of GPU time and can cancel tasks 5, 6 and 11 entirely. Building the chat backend before measuring tool calling would spend days on a feature that a 10-minute experiment might rule out. E7–E9 come last because a sampling sweep over a configuration that is not going to ship measures nothing.

**Cut order, if the schedule breaks.** Streaming → chat persistence → chat tool loop → the LLM report path (falling back to the deterministic renderer alone, which still ships a scouting report). Items 1-4 are never cut: without them there is no model, no vocabulary, no cache correctness, and no report.

**The experiments are never cut.** They are 4.5 hours of GPU time against a feature that consumes the remaining schedule, and they are the only thing standing between a plausible-looking report and a measured one. If E1 says the LLM report is not better than the template, that is a 5-minute finding that saves the rest of the week — cutting the experiment would spend the week to learn the same thing later, more expensively.

**The harness is written before the first experiment runs.** `analysis/llm_eval/harness.py` and the two case files are part of task 7's setup, not a later cleanup. The case sets in particular encode the expected tool and arguments for all 20 chat cases, and writing them is the moment the team finds out that a question has no unambiguous right answer — which is a bug in the *question*, not in the model, and it is much cheaper to find now than after a measurement.

**The Flutter client is a separate critical path.** It does not exist yet (only a static HTML preview) and is W7 work under ADR-007 priority 2. The chat feature is backend-only in this plan; the Flutter chat screen is a follow-on and is not on the critical path of the items above.

## 19. Risks and open items

| Risk | Impact | Mitigation |
| --- | --- | --- |
| llama.cpp #20837: Qwen3.5 emits tool calls inside the thinking block, never parsed | Chat tool loop fails | Reasoning off + `enable_thinking=false`; verified manually (test 2). Granite 4.2-8B fallback with a first-class non-thinking mode. |
| The `enable_thinking=false` toggle is ignored in the shipped build (#20409 family) | Same | Verify (test 3); Granite fallback. |
| llama.cpp #30357: non-canonical whitespace invalidates the prefix cache on hybrid models, forcing a full re-prefill per turn | Chat latency | Send `reasoning_content` back verbatim or strip reasoning; keep `--cache-prompt` on. |
| `n_parallel` set explicitly **silently divides** `ctx_size` across slots | The chat forgets long conversations mid-thread, with no error | `LLAMA_ARG_KV_UNIFIED: on` (§6.2). This is the highest-risk item in the plan precisely because it fails quietly. |
| `draft-mtp` speculative decoding on a model with no MTP heads | The server aborts at startup | The flag is left **unset** in compose (§6.2); it is added only after it is verified against the actual GGUF. |
| The experiment case set names a player that is **not** in the published data | A case passes for the wrong reason, and the real failure mode goes unmeasured | Every named entity is resolved against `players.parquet` and `analytics.fct_player_predictions` when the case set is written (§17.3). "João Silva" was a real player; the case set check exists because of it. |
| The LLM judge reproduces its own prior instead of measuring quality | A confident number that decides nothing | Every comparison is blind and pairwise with a randomised order; the headline numbers are deterministic (D1–D3); human rating breaks the tie (§17.1). |
| A 9-case human rating is read as decisive | A marginal difference ships as a decision | The threshold is stated for a **large** effect, and a 6-3 result is reported as inconclusive rather than as a win (§17.2). |
| The 16 GB card is an 8 GB card | Model and context | `Q4_K_M`/`IQ4_XS`; 8K context; no projector; Qwen3.5-4B for CPU. |
| Throughput figures are derived, not measured | Report latency unknown | Measure with `llama-bench` on the target card (test 4). |
| The backend gains `delphos_ml` and its dependency tree | Image size, version-alignment discipline | Vocabulary in a separate dependency-free `delphos_domain` distribution (§9.2); the `delphos_ml` dependency is already required by the `what-if` endpoint per [docs/ARCHITECTURE.md](ARCHITECTURE.md) §4.3. |
| No Flutter client exists | The graded deliverable | Separate critical path; not extended by this plan. |
| The deterministic renderer becomes better than the LLM report | The feature adds nothing | Measure against the baseline (§7.5); serve the deterministic report when it wins. |
| The model's **Spanish prose** is weaker than expected | The report reads badly, or in English | The evidence for Spanish is strong (§7.6) but it measures reasoning, not register. Mitigated by the deterministic fallback capping the downside at "no better than the template", and by manual verification item 6. The chat path has no equivalent fallback and carries the full exposure. |

**Open items — all now closed.** Both spec-level questions were decidable from the repository, and the answers are recorded in the sections that own them.

1. **`report_type` vocabulary.** Closed: `('scouting')` only, with the API rejecting anything else. The evidence is in §12 — one generator, one product surface, and a live silent-mismatch bug that the wider vocabulary would have preserved.
2. **Session listing.** Closed: `GET /chat/sessions` is included, because `app.chat_sessions` already carries `title`, `created_at` and `updated_at` — columns that only make sense with a list view. See §15.

**What remains open is not a spec question.** It is the manual verification in §16, which needs the actual GPU, the actual GGUF file, and the actual `llama-server` build. Those are empirical checks, and §16 lists them.

## 20. See also

- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — software architecture; the LLM inference service (§4.6), the report and chat flow (§5.3), the API surface (§6), cross-cutting concerns (§9), and the ADRs (§10) that this plan produces.
- [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) — §3.18, the LLM call parameters, whose 2026-11-04 model decision this plan supersedes.
- [docs/WORK_PLAN.md](WORK_PLAN.md) — schedule, variances, and the decision log.
- [docs/REPORT_NOTES.md](REPORT_NOTES.md) — Spanish; H-20 states the superseded 3B model and the per-90 limitation (§9.3) belongs here.
- [docs/TRANSFORM_PLAN.md](TRANSFORM_PLAN.md) — the working-plan precedent for a single stage.
- [backend/AGENTS.md](../backend/AGENTS.md) — the backend component's layout, dev commands, and the 130-line module rule.
- [DESIGN.md](../DESIGN.md) — the product's visual and verbal language, which the report prompt follows.
