# Frontend pending work (handoff, updated 2026-11-13)

This is a working handoff note, not a decision record: decisions live in `docs/ARCHITECTURE.md` (ADR-023 to ADR-030), schedule in `docs/WORK_PLAN.md`, visual spec in `DESIGN.md`. Delete this file once every item below is closed.

## 1. Where things stand

The Flutter app, the preview polish and the backend additive fields are merged into `main` (PR #16, `91f2abe`).

Branch `fix/frontend/docker-and-load-perf`, cut from `91f2abe`. Uncommitted at the time of writing; two changes, both reviewed and approved to ship:

| Change | Paths | State |
| --- | --- | --- |
| Container start-up fix | `.gitattributes` (new), `docker-compose.yml`, `frontend/Dockerfile`, `frontend/AGENTS.md`, ADR-029 bullet in `docs/ARCHITECTURE.md` | Done, 2 review rounds. The `frontend` image used to exit 127 on a Windows checkout (CRLF in the sourced `.envsh`; root-owned tmpfs for `conf.d`). Now LF is enforced, the build stage strips CRs, the tmpfs mounts are uid 101 with size caps and `noexec,nosuid,nodev`, templates are 0644. Verified live: CSP, `no-cache` / `immutable`, gzip, read-only, `127.0.0.1:80` |
| Explorer table stays mounted (perf A + B, section 7) | `lib/ui/features/explorer/views/explorer_layout.dart`, `explorer_screen.dart:126`, `test/ui/features/explorer/explorer_table_stability_test.dart` (new), ADR-027 amendment | Done, 2 review rounds. `flutter analyze` clean, 243 tests green |

`docs/ARCHITECTURE.md` carries one line for each change; stage it with `git add -p` if you commit them separately. Commit messages carry **no** `Co-Authored-By` trailer or any Claude attribution.

Also in the tree:
- `.impeccable/config.json`: one ignore for the design hook (the `--canvas` paper colour in `frontend/web/index.html` is the deliberate DESIGN.md token). Decide whether to version it or add it to `.gitignore`.
- `.playwright-mcp/` (gitignored): logs left by the browser tools; safe to delete.

### Setting up another computer

- Flutter **3.47.5** stable (Dart 3.13.4), pinned in `pubspec.yaml`. Run `flutter pub get` from `frontend/`.
- Docker Desktop. From the repo root, with the published data in the `delphos_pgdata` volume (otherwise run the pipeline through `publish` first, see `ml/AGENTS.md`):
  ```
  DELPHOS_CORS_ORIGINS="http://localhost,http://localhost:80,http://localhost:3000" docker compose up -d --build db migrate backend frontend
  ```
  The app is then at `http://localhost/explorador` (release build). A clone checked out before `.gitattributes` existed must refresh `frontend/nginx/` only if it bind-mounts it (see `frontend/AGENTS.md`); `docker compose build` is fine either way.
- The dev server (`flutter run -d web-server ...`, `frontend/AGENTS.md` §2) is debug mode: about 48 s to the first frame. **Never judge speed on it**; use the Docker release build.

## 2. Batch under browser verification

Merged in PR #16, partly checked in the browser (section 3).

- **X1, X2**: Arquetipos share bar and card surfaces drew at zero height (childless boxes in a `Row`); fixed with `CrossAxisAlignment.stretch`.
- **X3**: "Comparar reemplazos" on its own line; non-breaking space in "≥ 20%".
- **X4**: Temporada labels wrap to two lines inside `IntrinsicHeight` rows.
- **Resumen report**: shows the newest stored report on open (`GET /reports?player_id=&limit=1`); "Generar informe" / "Regenerar" (`force_regenerate`); "Generando el informe… N s" with "Cancelar"; the request is aborted on cancel, player switch or close; HTML goes through `ui/core/html/report_html_sanitizer.dart` (allowlist `p`, `strong`, `em`, `br`) before `HtmlWidget`; provenance line ("Plantilla determinista · generado el …"). ADR-028 amended. With no LLM running the backend answers in about 9 s with `source: deterministic`.

## 3. Verification still owed

- [ ] **Browser pass, in progress** (2026-11-13, stopped twice by the usage limit, saved, to be resumed): section 2 batch, keyboard pass on every view (it had reached the comparator), narrow layout (< 1100 px) on every entry point, and the table-jump bug. It runs against the image built **before** perf A + B; repeat the dossier open/close checks after rebuilding.
- [ ] **Re-measure after A + B**: rebuild `frontend` (`docker compose build frontend` and `up -d --no-deps frontend`), then measure dossier open/close long tasks on the release build. Before: about 730 ms CPU per open, about 470 ms per close.
- [x] Docker image built, run and checked (2026-11-12): nginx templates render, zero CSP violations with CanvasKit (`wasm-unsafe-eval`, `blob:` workers), read-only container, `127.0.0.1:80:8080`.
- [x] Load performance review (2026-11-12): section 7.
- [ ] **antislop audit 003** on the real app (owner priority): `frontend/anti-slop/audit-003-<date>.md`, numbered findings, the owner picks what to fix (global mode is `after`). Include the Delivery Gate with a recorded click-through.
- [ ] Design-skill review requested by the owner: `design:design-system` (tokens, type scale and spacing in code vs DESIGN.md, hard-coded values), `design:accessibility-review` (focus, keyboard, semantics, contrast with the antislop script), and a motion review with the `animate` skill against MOTION 1.
- [ ] `yordick-puerco` and `yordick-abogangster` re-review of the scaffold fix round, the explorer, dossier, comparator, archetypes and report batches (deferred by the owner; the re-review of the fix round was cut off by a rate limit).

## 4. Open decisions (owner)

- Search writes one browser history entry per debounced query (`context.go`); `replace` would avoid it.
- `/canvaskit/` and `/assets/assets/fonts/` are cached as immutable but their paths carry no hash: after a Flutter SDK bump a returning browser could mix versions. A versioned path would remove the risk (also fixes H4, section 7).
- A deep link to a player who is not on the current page keeps the dossier open (paging is server side).
- Escape on a focused but closed select closes the dossier; DESIGN.md says a select keeps Escape. (The browser pass is re-checking it.)
- Several files run 131 to 149 lines (`api_client`, `report_view_model`, `compare_table_body`, `dossier_panel`, `explorer_screen` at 145, and others); `labels/countries.dart` is 240 (one data table, documented). Split or accept.
- The report provenance prints the raw model id ("qwen/qwen3.5-9b"); DESIGN.md's no-debug-text rule may call for a friendlier label.
- The dossier shows the newest stored report for the player regardless of ADR-021's cache key (model, prompt version, TTL); the provenance line says who wrote it and when. Keep or align with ADR-021.
- DESIGN.md still says flags come from FlagCDN (§1, §6); ADR-026 supersedes it for the app. Update DESIGN.md.
- The pitch drawings and card boxes were kept close to the mockup on purpose; the owner wants to improve them in the real app.

Decided 2026-11-12: below 1100 px the full-page dossier still replaces the table, so the table's scroll is lost on close. Kept as is (DESIGN.md: the dossier is its own page); pinned by test 3 in `explorer_table_stability_test.dart`.

## 5. For the ML / backend side (Gustavo)

- **Archetype labels vs members (audit-002 #23)**: "Ancla Defensiva" lists Cole Palmer, Antoine Semenyo and Nico Paz as representatives (the API orders by market value, not by centrality); "Creador Ofensivo" holds full-backs and centre-backs. Either the cluster-to-name mapping or the representative choice needs a look.
- **`starter_ratio` above 1** for some rows (Rayan, Diogo Bezerra, Steven Zuber: starts above matches). The UI prints N/D; the source needs fixing.
- **Vocabulary mismatch**: `ml/src/delphos_domain/labels.py` says "Valor Justo" and Title Case sub-positions; the app and DESIGN.md say "En precio" and sentence case. The LLM report will use the backend wording.
- **Unhandled 500s leave without CORS headers**, so the app shows them as a network error (ADR-025 note). A catch-all problem+json handler inside the CORS middleware fixes it.
- **Backend port binds on all interfaces** in compose; the frontend binds `127.0.0.1` only.
- `/clusters` `cluster_name` comes in English; the app maps `cluster_id` to Spanish labels.

## 6. Rest of the week 7 plan

- Mon 16: end-to-end demo in Docker Compose (db, migrate, backend, frontend), antislop audit 003 fixes chosen by the owner.
- Tue 17: buffer; update `docs/WORK_PLAN.md` (W7 Actual, status date, variances).
- Week 8: final report (APA 7) and the baseline vs actual comparison; the chat screen only if the report allows it.

## 7. Performance (measured 2026-11-12)

The owner felt the app slow on load and while navigating. Measured with Playwright Chromium against the release build in Docker and the dev server; raw data was kept in the session scratchpad only.

### Load

| | Release (nginx) | Dev server (DDC) |
| --- | --- | --- |
| First frame, localhost (median) | 1.39 s | 47.9 s |
| First frame, throttled Fast 4G | 4.80 s | 108 s |
| Requests / transferred (cold) | 40 / 6.89 MB | 895 / 164 MB |

| Hypothesis | Verdict | Evidence |
| --- | --- | --- |
| H1 debug mode | Confirmed | Table above: the slowness the owner saw was most likely the dev server |
| H2 serial chain | Confirmed | Bootstrap, then `main.dart.js` and wasm in parallel, then fonts last (about 1.95 s of 4.7 s throttled) |
| H3 fonts whole and uncompressed | Confirmed | Four TTFs (the three bundled plus Roboto fallback), 2.90 MB, 44% of the bytes. Served as `application/octet-stream` (nginx's `mime.types` has no ttf), so never gzipped; gzip would save about 0.9 s on Fast 4G |
| H4 `no-cache` revalidation | Confirmed, minor | Warm reload: 14 conditional requests, 40 KB, about 0.3 s at 40 ms latency |
| H5 full-size image decode | Rejected as main cause | Images are already 139×181 and small; about 115 ms per page |

Also found: `--no-web-resources-cdn` bundles `assets/fonts/fallback/Roboto-Regular.ttf` (171 KB), loaded before the first frame and served `no-cache`. The explorer page size is 50 (`explorer_query.dart:59`), not 20.

### Navigation (profile build)

The app's own `lib/` code costs under 10 ms per interaction; the cost is Flutter framework work driven by the widget tree shape. Only visible rows are built (`ListView.builder`), about 25 ms per visible row per page click plus about 100 ms fixed, so page size does not matter.

| # | Cause | Fix | State |
| --- | --- | --- | --- |
| A | Opening or closing the dossier disposed and rebuilt the whole table (and jumped its scroll to the top) | Table always first child of a `Row` | **Done** (section 1) |
| B | Every dossier notification rebuilt the filter bar and all rows | Separate listeners | **Done** (section 1) |
| C | Paging rebuilds the old rows only to show "Cargando jugadores…" (`players_table.dart:85-109`, `explorer_view_model.dart:94-96`) | Only the footer depends on `isRefreshing` | Pending, 100 to 150 ms per click |
| D | Hover `setState` rebuilds the whole row (`player_row.dart:50-51`) | Hover wrapper with the row as `child` | Pending, cheap |
| E | Heavy rows (about 180 widgets): two Material `Tooltip`s, full `Pressable`, nested `Container`s in the avatar | Lighter row | Pending, needs a design and a11y call |
| F | `Image.network` without `cacheWidth`/`cacheHeight` (`player_avatar.dart:78`, `:112`) | Add them, plus a widget test | Pending, cheap |
| I | Paging with the dossier open navigates twice (`explorer_view_model.dart:122-126`) | Close the dossier within the page change | Pending, touches the ADR-024 URL flow |

Not recommended: removing `ensureSemantics()` (breaks screen readers and tests), fewer rows per page (no effect).

### Load fixes still open (owner to choose)

| Fix | Targets | Cost and risk |
| --- | --- | --- |
| `types { font/ttf ttf; }` plus `font/ttf` in `gzip_types` in `nginx/default.conf.template` | H3 | Two lines, low risk |
| Subset the fonts (`pyftsubset`, keep the variable axes and every glyph the UI and LLM reports can print) | H3 | Build step; record an ADR |
| `flutter build web --wasm` (skwasm) | H2 | Needs COOP/COEP; conflicts with the third-party image hosts; untested |
| Hashed or versioned build paths | H4 | Larger change; decide with the section 4 item |

Constraints: ADR-026 (no third-party CDN; keep `--no-web-resources-cdn`), the CSP in `nginx/security-headers.inc.template` (keep `--csp`; a new image host goes into `lib/data/models/image_url_allowlist.dart` too), DESIGN.md (static loading line, Archivo and Source Serif 4 stay; subsetting is fine, swapping families is not), and the exact pins in `pubspec.yaml`.

Known test fragility (review minor, shipped): `explorer_table_stability_test.dart:42-47` taps the third and fourth built `PlayerRow`s after a drag; built rows include the cache extent, so a change in viewport or row height could make the taps miss. Filter rows by their rect inside `PlayersTable`.
