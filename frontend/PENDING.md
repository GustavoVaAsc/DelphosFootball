# Frontend pending work (handoff, 2026-11-11)

This is a working handoff note, not a decision record: decisions live in `docs/ARCHITECTURE.md` (ADR-023 to ADR-030), schedule in `docs/WORK_PLAN.md`, visual spec in `DESIGN.md`. Delete this file once every item below is closed.

## 1. Where things stand

Branch `feat/frontend/preview-polish`, last commit `802c22b`. **Nothing after that commit is committed.** The working tree holds four separate pieces of work:

| Piece | Paths | State |
| --- | --- | --- |
| Mockup polish (collapsible dossier, audit-002 fixes) | `DESIGN.md`, `frontend/design-preview/index.html`, `frontend/design-preview/anti-slop/audit-002-2026-11-10.md` | Done, verified in the browser |
| Flutter app (views 1 to 3, dossier, shell, theme, data layer) | `frontend/` (everything except `design-preview/` and `.agents/`) | Done except section 2 below; 210 tests green at the last finished batch |
| Backend additive fields | `backend/src/delphos_backend/{schemas,repositories,api}/players.py, clusters.py`, `backend/tests/test_{players,clusters,live_integration}.py` | Done: `GET /players` items carry `fair_value_eur` and `age`; `GET /clusters` carries `as_of_date`. 240 tests green, live test green |
| Docs and config | `AGENTS.md`, `README.md`, `.env.example`, `docker-compose.yml`, `docs/ARCHITECTURE.md`, `docs/WORK_PLAN.md` | Done for the work above |

Also in the tree:
- `backend/.agents/skills/fastapi-templates/SKILL.md` and `references/details.md`: reformatted by accident by `ruff format .`. Not part of any change. Revert with `git checkout -- backend/.agents/skills/fastapi-templates`.
- `.impeccable/config.json`: one ignore for the design hook (the `--canvas` paper colour in `frontend/web/index.html` is the deliberate DESIGN.md token). Decide whether to version it or add it to `.gitignore`.

### Moving to another computer

Commit and push before switching machines (one PR per session). Suggested split:

```
git checkout -- backend/.agents/skills/fastapi-templates
git add DESIGN.md frontend/design-preview/index.html frontend/design-preview/anti-slop/audit-002-2026-11-10.md
git commit -m "feat(frontend): make the preview dossier collapsible and fix audit-002 findings"
git add backend/src backend/tests
git commit -m "feat(backend): add fair value and age to player rows and the data date to clusters"
git add frontend AGENTS.md README.md .env.example docker-compose.yml docs/ARCHITECTURE.md docs/WORK_PLAN.md
git commit -m "feat(frontend): add the Flutter web app with explorer, dossier, comparator and archetypes"
git push -u origin feat/frontend/preview-polish
```

Add the `Co-Authored-By` trailer to each message if you keep that convention. If the in-progress batch (section 2) has not finished when you commit, check `flutter analyze` and `flutter test` first: a half-applied batch may not compile.

### Setting up the other computer

- Flutter **3.47.5** stable (Dart 3.13.4), pinned in `pubspec.yaml`. Run `flutter pub get` from `frontend/`.
- Docker Desktop. From the repo root, with the published data in the `delphos_pgdata` volume (otherwise run the pipeline through `publish` first, see `ml/AGENTS.md`):
  ```
  DELPHOS_CORS_ORIGINS="http://localhost,http://localhost:80,http://localhost:3000" docker compose up -d --build db migrate backend
  ```
- Then the dev server: `flutter run -d web-server --web-port 3000 --no-web-resources-cdn --dart-define=DELPHOS_API_URL=http://localhost:8000` and open `http://localhost:3000/explorador`. All commands are in `frontend/AGENTS.md` §2.

## 2. Last batch (finished, not yet seen in a browser)

Finished after this note was first written. `flutter analyze` clean, 240 tests green, release build OK.

- **X1, X2**: Arquetipos share bar and card surfaces drew at zero height (childless boxes in a `Row`); fixed with `CrossAxisAlignment.stretch`.
- **X3**: "Comparar reemplazos" on its own line; non-breaking space in "≥ 20%".
- **X4**: Temporada labels wrap to two lines inside `IntrinsicHeight` rows.
- **Resumen report**: shows the newest stored report on open (`GET /reports?player_id=&limit=1`); "Generar informe" / "Regenerar" (`force_regenerate`); "Generando el informe… N s" with "Cancelar"; the request is aborted on cancel, player switch or close; HTML goes through `ui/core/html/report_html_sanitizer.dart` (allowlist `p`, `strong`, `em`, `br`) before `HtmlWidget`; provenance line ("Plantilla determinista · generado el …"). ADR-028 amended. Live probe: `POST /reports/generate` for 566723 answered 200 in 8.7 s with `source: deterministic` (no LLM running).
- New direct dependency: `html: 0.15.7` (already in the lockfile).

Commit split suggested by the coder for this batch, if you prefer finer commits than section 1: `fix(frontend): draw archetype share bar and card surfaces`, `fix(frontend): keep dossier subtitle and season labels readable`, `feat(frontend): add cancellable report requests to the API client`, `feat(frontend): render scouting reports in the dossier Resumen`.

## 3. Verification still owed

- [ ] Browser pass of section 2 (report flow, cancel, regenerate, provenance, fade, X1 to X4) against the live API. Views 1 to 3 before that batch were checked in Chromium on 2026-11-11 with zero console errors.
- [ ] **antislop audit 003** on the real app (owner priority): `frontend/anti-slop/audit-003-<date>.md`, numbered findings, the owner picks what to fix (global mode is `after`). Include the Delivery Gate with a recorded click-through.
- [ ] Design-skill review requested by the owner: `design:design-system` (tokens, type scale and spacing in code vs DESIGN.md, hard-coded values), `design:accessibility-review` (focus, keyboard, semantics, contrast with the antislop script), and a motion review with the `animate` skill against MOTION 1.
- [ ] `yordick-puerco` and `yordick-abogangster` re-review of the scaffold fix round, the explorer, dossier, comparator, archetypes and report batches (deferred by the owner; the re-review of the fix round was cut off by a rate limit).
- [ ] Docker image never built here (daemon was off during the scaffold): `docker compose build frontend`, run it, and check the nginx templates, the CSP (no violations with CanvasKit, `wasm-unsafe-eval`, `blob:` workers), the read-only container and `127.0.0.1:80:8080`.
- [ ] Keyboard pass in a real browser on every view: Tab order, Enter and Space, Escape, focus return, rings only for keyboard.
- [ ] Narrow layout (< 1100 px): dossier as a full page on every entry point.

## 4. Open decisions (owner)

- Search writes one browser history entry per debounced query (`context.go`); `replace` would avoid it.
- `/canvaskit/` and `/assets/assets/fonts/` are cached as immutable but their paths carry no hash: after a Flutter SDK bump a returning browser could mix versions. A versioned path would remove the risk.
- A deep link to a player who is not on the current page keeps the dossier open (paging is server side).
- Escape on a focused but closed select closes the dossier; DESIGN.md says a select keeps Escape.
- Several files run 131 to 149 lines (`api_client`, `report_view_model`, `compare_table_body`, `dossier_panel`, `explorer_screen`, and others); `labels/countries.dart` is 240 (one data table, documented). Split or accept.
- The report provenance prints the raw model id ("qwen/qwen3.5-9b"); DESIGN.md's no-debug-text rule may call for a friendlier label.
- The dossier shows the newest stored report for the player regardless of ADR-021's cache key (model, prompt version, TTL); the provenance line says who wrote it and when. Keep or align with ADR-021.
- DESIGN.md still says flags come from FlagCDN (§1, §6); ADR-026 supersedes it for the app. Update DESIGN.md.
- The pitch drawings and card boxes were kept close to the mockup on purpose; the owner wants to improve them in the real app.

## 5. For the ML / backend side (Gustavo)

- **Archetype labels vs members (audit-002 #23)**: "Ancla Defensiva" lists Cole Palmer, Antoine Semenyo and Nico Paz as representatives (the API orders by market value, not by centrality); "Creador Ofensivo" holds full-backs and centre-backs. Either the cluster-to-name mapping or the representative choice needs a look.
- **`starter_ratio` above 1** for some rows (Rayan, Diogo Bezerra, Steven Zuber: starts above matches). The UI prints N/D; the source needs fixing.
- **Vocabulary mismatch**: `ml/src/delphos_domain/labels.py` says "Valor Justo" and Title Case sub-positions; the app and DESIGN.md say "En precio" and sentence case. The LLM report will use the backend wording.
- **Unhandled 500s leave without CORS headers**, so the app shows them as a network error (ADR-025 note). A catch-all problem+json handler inside the CORS middleware fixes it.
- **Backend port binds on all interfaces** in compose; the frontend now binds `127.0.0.1` only.
- `/clusters` `cluster_name` comes in English; the app maps `cluster_id` to Spanish labels.

## 6. Rest of the week 7 plan

- Mon 16: end-to-end demo in Docker Compose (db, migrate, backend, frontend), antislop audit 003 fixes chosen by the owner.
- Tue 17: buffer; update `docs/WORK_PLAN.md` (W7 Actual, status date, variances).
- Week 8: final report (APA 7) and the baseline vs actual comparison; the chat screen only if the report allows it.
