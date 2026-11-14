# DelphosFootball frontend guide

## Table of contents

1. [What this component is](#1-what-this-component-is)
2. [Dev commands](#2-dev-commands)
3. [Layout](#3-layout)
4. [Conventions](#4-conventions)
5. [See also](#5-see-also)

---

## 1. What this component is

`frontend/` is the Flutter web app (the `delphos_frontend` package): the scouting UI that reads the FastAPI backend. It copies the visual spec in [DESIGN.md](../DESIGN.md), whose reference implementation is the static mockup in `design-preview/`. The global conventions (English in code and docs, Conventional Commits, decision records, the `.env.example` key list) live in the [root AGENTS.md](../AGENTS.md); follow both here.

The toolchain is pinned exactly: Flutter 3.47.5 with Dart 3.13.4 (`environment` in `pubspec.yaml`), and every direct dependency has an exact version, with `pubspec.lock` committed (ARCHITECTURE.md §4.1). Bump them only in a dependency-bump commit.

`design-preview/` and `.agents/` sit inside `frontend/` but are not part of the app: the first is the HTML mockup, the second holds the team's Flutter and Dart agent skills. The skills never override [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## 2. Dev commands

Run every command from `frontend/`.

| Task | Command |
| --- | --- |
| Install dependencies | `flutter pub get` |
| Static analysis (must report no issues) | `flutter analyze` |
| Format | `dart format lib test` |
| Run the tests | `flutter test` |
| Dev server on port 3000 | `flutter run -d web-server --web-port 3000 --no-web-resources-cdn --dart-define=DELPHOS_API_URL=http://localhost:8000` |
| Release build into `build/web/` | `flutter build web --release --no-web-resources-cdn --csp --dart-define=DELPHOS_API_URL=http://localhost:8000` |
| Check the build makes no CDN request | `grep -rIl -e gstatic.com -e googleapis.com build/web` lists only `flutter.js`, `flutter_bootstrap.js` and `main.dart.js`, where the URLs are defaults that the build configuration overrides (ADR-026) |
| Serve a release build locally with the production nginx config | `docker run --rm -p 3000:8080 -e DELPHOS_API_URL=http://localhost:8000 -v "$PWD/build/web:/usr/share/nginx/html:ro" -v "$PWD/nginx:/etc/nginx/templates:ro" -v "$PWD/nginx/15-delphos-api-origin.envsh:/docker-entrypoint.d/15-delphos-api-origin.envsh:ro" nginxinc/nginx-unprivileged:1.30.6-alpine` |
| Container image | `docker compose build frontend` from the repo root; the root `.gitattributes` keeps the nginx files and `web/` LF, and the compose tmpfs mounts are owned by uid 101 so nginx can render its templates (ADR-029). The Dockerfile's CR strip covers only `docker compose build`: for the bind-mount recipe above, a clone checked out before `.gitattributes` existed must refresh `nginx/` first (delete the files and run `git checkout -- nginx/`) |

Port 3000 is already in the backend's default `DELPHOS_CORS_ORIGINS`. Use `-d chrome` instead of `-d web-server` to open a browser with hot reload. Always pass `--no-web-resources-cdn`: without it the engine loads CanvasKit from `www.gstatic.com`. `--csp` keeps dart2js from emitting `eval`, which the production CSP blocks; add it to `flutter run` too when you test against that CSP.

`DELPHOS_API_URL` is compiled in (ADR-029). The browser calls the API from the user's machine, so the value is the backend's host URL, never the compose-internal `http://backend:8000`. Without the define the app uses `http://localhost:8000`.

## 3. Layout

```
frontend/
├── lib/
│   ├── main.dart            # path URLs, the API client, runApp
│   ├── app.dart             # provider DI, theme, MaterialApp.router
│   ├── config/              # build-time configuration (DELPHOS_API_URL)
│   ├── routing/             # route paths, the GoRouter table, the explorer's URL state
│   ├── data/
│   │   ├── services/        # ApiClient and its two error types
│   │   ├── models/          # DTOs: hand-written fromJson per backend schema, plus toDomain()
│   │   └── repositories/    # players, archetypes, reports; return domain models
│   ├── domain/models/       # immutable domain models and the ValuationStatus enum
│   └── ui/
│       ├── core/
│       │   ├── theme/       # DESIGN.md §2 colours, §3 type scale, text styles, ThemeData
│       │   ├── format/      # es-ES number, money, date and match-stat formatting
│       │   ├── html/        # report_html_sanitizer: the ADR-028 allowlist, applied before HtmlWidget
│       │   ├── labels/      # Spanish labels: positions, feet, leagues, statuses, archetypes, shortfalls, countries
│       │   ├── layout/      # the dossier breakpoint
│       │   ├── shell/       # AppShell (sidebar, top bar, tab title), nav items, not-found page
│       │   ├── brand/       # the pitch glyph brand mark
│       │   ├── view_models/ # DatasetViewModel (shell facts); SectionLoad, SectionStatus and loadSection, shared by
│       │   │                # every ViewModel that loads independent sections
│       │   ├── util/        # Debouncer
│       │   └── widgets/     # Pressable, ActionButton, TextLink, StatePanel, StatusPill, PitchGlyph, LineGlyph,
│       │                    # FocusRing, FocusVisibility, InsetFocusFrame, FadeInOnce, FlagImage, PlayerAvatar
│       └── features/<feature>/{view_models,views}/   # explorer (view 1), comparator (view 2), archetypes (view 3)
├── test/                    # mirrors lib/; support/ has the fake backends, player fixtures and the app harness
├── assets/
│   ├── fonts/               # Archivo and Source Serif 4 variable fonts with their OFL.txt
│   └── flags/               # w80 PNG flags for the codes in labels/countries.dart, LICENSE.md
├── web/                     # index.html (static loading line), flutter_bootstrap.js (fallback-font base URL), manifest
│   └── fonts-fallback/      # Roboto at the path the engine requests, with its OFL; no Noto set (ADR-026)
├── nginx/                   # default.conf and security-headers templates, 15-delphos-api-origin.envsh
├── Dockerfile               # Flutter 3.47.5 build stage, unprivileged nginx serve stage, both pinned by digest
└── pubspec.yaml / pubspec.lock
```

## 4. Conventions

- Architecture (ADR-023): Layered MVVM: views are lean widgets; ViewModels extend `ChangeNotifier`, take repositories in their constructor and live in `ui/features/<feature>/view_models/`; repositories turn DTOs into domain models; `provider` injects the `ApiClient` and the repositories from `app.dart`. Views never call the `ApiClient` directly.
- Routing (ADR-024): The URL is the state. The explorer reads `/explorador?estado=&posicion=&arquetipo=&q=&pagina=&jugador=<id>` through `ExplorerQuery`, and the dossier is open when `jugador` is present. Ids from a URL go through `parseRouteId` (one to ten digits, at most 2147483647) and a search above 100 characters is dropped. Navigate with `context.go(...)` and the `Routes` constants; never hard-code a path in a view. Each module page wraps its screen in `AppShell` through `_modulePage` in `app_router.dart`; do not reintroduce a `ShellRoute`, whose nested navigator traps keyboard focus inside the page. `AppShell` also sets the browser tab title from `Routes.documentTitleFor`. There is no chat route until the chat screen exists.
- HTTP (ADR-025): Every request goes through `ApiClient`. A non-2xx answer is an `ApiException` (status, title, detail from the RFC 9457 body); no answer at all is an `ApiNetworkException`; a 2xx body that breaks the contract is a `FormatException`. Map these to the DESIGN.md §7 states in the ViewModel. A timeout aborts the request (`AbortableRequest`). `main.dart` creates the one client and owns it; widgets and tests never close a client they did not create. DTOs parse with Dart 3 map patterns and the `json_fields.dart` helpers; there is no code generation.
- Material: Import `package:material_ui/material_ui.dart`, not `package:flutter/material.dart`. Flutter 3.47 moved Material into that package and go_router 18 builds its pages from it, so mixing the two gives two incompatible `MaterialApp` and `Theme` types (ADR-030). Widget-only files import `package:flutter/widgets.dart`.
- No icon font: `uses-material-design` is `false`, so `Icons.*` renders nothing. Draw the few glyphs the design needs with `CustomPainter`, as `ui/core/brand/pitch_mark.dart` does. `flutter build web` therefore warns that it found no fonts for `MaterialIcons` and `CupertinoIcons`; the icons it means belong to framework widgets the app does not show, such as the default back button.
- No third-party requests (ADR-026): Fonts, flags, CanvasKit and the Roboto fallback font come from the app's origin. The only network images are the dataset's own portrait and crest URLs, filtered by `allowedImageUrl` in the DTO mappings and loaded through `PlayerAvatar`, which fetches the bytes (both hosts send `Access-Control-Allow-Origin: *`) and lets CanvasKit decode them: no HTML `<img>` platform views. A new image host goes into `allowedImageHosts` and into both `img-src` and `connect-src` in `nginx/security-headers.inc.template`. Do not add `google_fonts`, load flags from FlagCDN, or bundle Noto fonts; a glyph outside Archivo, Source Serif 4 and Roboto shows as missing on purpose.
- Focus (DESIGN.md §2): every interactive element is a `Pressable` (or built on it, like `NavItem`, `ActionButton` and `TextLink`), which draws the 2 px focus ring 2 px out when the element has focus and the last input was the keyboard (`FocusVisibility`, the app's `:focus-visible`: a key press shows rings, a pointer press hides them; Flutter's own highlight mode never switches back after a click): ink on light grounds, white on the sidebar. `Pressable` activates on a click, Space, Enter (Flutter web binds Enter to `ButtonActivateIntent`, not `ActivateIntent`, so both are handled) and a semantics tap, and it is a semantics container so a labelled ancestor never swallows it. A raw `GestureDetector` is not keyboard reachable; use one only as a mouse shortcut beside a real control, as a table row does. The shell puts the sidebar and the page in separate `FocusTraversalGroup`s, so Tab walks the sidebar, then the page.
- Accessibility: `main.dart` calls `SemanticsBinding.instance.ensureSemantics()` at start-up. Flutter web otherwise builds no accessibility tree until a user finds a hidden "Enable accessibility" button, so screen readers, keyboard traversal through the DOM, and browser tests would see an empty page. Give every `Pressable` a Spanish `semanticLabel`.
- Motion (DESIGN.md §5, dial MOTION 1, tokens in `ui/core/theme/motion.dart`): hover and press feedback at 160 ms with the preview's `cubic-bezier(0.16, 1, 0.3, 1)`, to confirm the pointer and the click; the dossier content's `dossierEnter` (opacity 0.65 to 1 and 3 px up, 180 ms) only when one loaded player replaces another inside an open dossier, to mark the change of player; and each dossier section's one-time fade (opacity only, 160 ms, `FadeInOnce`, no stagger) when its data replaces its skeleton, which includes a report when it arrives (keyed by report id, so a regenerated report fades in again). Opening and closing the dossier, filters, keystrokes, page changes and table rows do not animate, and nothing loops. Every duration goes through `DelphosMotion.duration`, which returns zero when `MediaQuery.disableAnimationsOf` is true. Write the purpose of a new animation in a comment beside it.
- Locale: the app runs in es-ES with `material_ui`'s `GlobalMaterialLocalizations.delegates`; do not add `flutter_localizations` directly.
- Text: UI text is Spanish (es-ES); code, comments and docs are English. Every number on screen goes through `ui/core/format/format.dart`, and every data label through `ui/core/labels/labels.dart`; a label helper returns `null` for an unknown key, and the view omits it rather than printing the raw code. Use only the six sizes in `TypeScale` and the styles in `DelphosText`: `condensed` for names and euro figures, `ui` for everything else, `prose` for report text.
- Table widths (ADR-027 amendment): Brecha is 128 px and Posición with the dossier open 142 px, wider than DESIGN.md's 120 and 130 px, so the widest pill never clips and no position word breaks inside itself. Change them only with `explorer_fit_and_focus_test.dart`, which measures both with Archivo.
- Layout (ADR-027): Designed for 1280 to 1920 px. `DossierPresentation.forWidth` decides whether the dossier is a side panel or its own page; there is no phone layout.
- Report HTML (ADR-028 and its amendment): Render report HTML only through `ReportProse`, which passes it through `sanitizeReportHtml` (only `p`, `strong`, `em`, `br`; no attributes; scripts, styles, images, media and frames dropped with their content; 20 KB cap) and then `HtmlWidget`, in Source Serif 4 15/1.55, ink-2 with `strong` in ink, at most 68 characters to the line. Change the allowlist in the sanitizer and its test, which holds ADR-028's required input; never give `HtmlWidget` unsanitized HTML or an `onTapUrl` that launches anything.
- Resumen: `ReportViewModel`, owned by `DossierViewModel` and moved to the same player, lists the newest stored report on open and generates only when asked. A generation shows a static line with the seconds (one tick a second, no spinner) and "Cancelar". Cancelling, switching player or closing the dossier completes the request's `cancel` future, which aborts the `fetch` through `AbortableRequest` and throws `RequestCancelledException`. The provenance line says "Redactado por el modelo local (<model>)" or "Plantilla determinista", never an AI badge or icon.
- Caching: nginx caches `/canvaskit/` and `/assets/assets/fonts/` as immutable for a year and revalidates everything else. After a Flutter SDK or font bump, those files keep their paths, so returning browsers keep the old copies until their cache is cleared; check this when you bump either.
- Files: One public class per file, a doc comment at the top of each file stating its responsibility, facades that only re-export, and roughly 130 lines per module at most. A module of small related functions may stay together when its doc comment says why; `labels/countries.dart` is longer because it is one data table.
- Tests: Test files mirror `lib/` and end in `_test.dart`. Repository tests fake the backend with `MockClient` through `test/support/http_fakes.dart`; explorer and app tests use `FakePlayersBackend` (`test/support/explorer_harness.dart`), which serves `/players`, `/players/{id}`, `/clusters` and `/reports` and can hold, reorder or fail requests. `pumpAppAt` loads the bundled Archivo font, so widget tests lay text out with real metrics. ViewModel logic gets its test first. A formatter or label rule gets its test first, and the test must fail before the code exists.
- Comparator (view 2): `ComparatorViewModel` loads the reference's profile, valuation and replacements, then each candidate's profile; a failed candidate is "Sin datos de temporada" in its column only. The season rules (values as displayed, deltas from displayed values, shares in pp, tone only on output metrics, no delta beside N/D) live in `features/comparator/views/compare_rules.dart` and are unit-tested; change them there, not in the widgets. The selector (`PlayerSearchViewModel`) keeps focus in the field: arrows move, Enter picks, Escape closes.
- Archetypes (view 3): `ArchetypeGrid` aligns the cards' rows (Flutter has no subgrid): the cards are a background layer and each content row is an `IntrinsicHeight` row of three cells. A childless box in a `Row` (a card surface, a share bar segment) needs `CrossAxisAlignment.stretch`, or it lays out zero tall and draws nothing. Add a card row there, not inside one card. Archetype descriptions are app copy in `ui/core/labels/archetypes.dart`, keyed by `cluster_id`.
- Dossier labels: a season grid label that does not fit at the 440 px panel wraps to a second line (at most two) instead of truncating; each grid row is an `IntrinsicHeight` row, so its four values share one line under the labels. Labels are not shortened behind tooltips, which a keyboard or touch user cannot open. A section action, such as "Comparar reemplazos", sits on its own line under the title and subtitle; write a non-breaking space (` `) between a sign or symbol and its number ("≥ 20%") so the pair never breaks.
- Countries and flags: `labels/countries.dart` covers every `country_of_citizenship` value in `ml/data/clean/players.parquet` (202 values for Kaggle v679). To add one, add its row and download its flag as described in `assets/flags/LICENSE.md`; `test/ui/core/labels/countries_test.dart` fails until the set of flag files equals the set of flag codes in the table.

## 5. See also

- [DESIGN.md](../DESIGN.md): colours, type, layout, states and vocabulary.
- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md): §4.1 for this component, §6 for the API surface, ADR-023 to ADR-030 for the frontend decisions.
- [backend/AGENTS.md](../backend/AGENTS.md): how to run the API the app reads.
- `backend/src/delphos_backend/schemas/`: the response shapes the DTOs mirror.
