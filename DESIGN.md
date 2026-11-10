# DESIGN.md - DelphosFootball (Football front office, light mode)

## 1. Visual theme and atmosphere
- **Archetype**: Football front-office and scouting suite for a Sporting Director (`Director Deportivo`). Desktop web only (see §4).
- **References, not templates**: Transfermarkt ES market tables (dense rows, price first), FotMob player page (one player, one verdict, stats grid), The Athletic data graphics (warm paper, ink, one accent per meaning).
- **Dial**: `Dial: ENERGY 1 / RHYTHM 1 / MOTION 1` (a calm executive tool that is read for minutes at a time, not a landing page).
- **Mood**: Printed match-day report. Ink on warm paper, figures set like a scoreboard, colour only where money moves. Every label uses natural football terminology in executive Spanish; no API routes, no SQL column identifiers, no debug text appear in the interface.
- **Why these choices**:
  - Colour: warm paper and navy ink read as editorial sports press; green and red are kept for the one question the product answers (is this player cheap or expensive), so they stay legible as signals.
  - Type: a condensed grotesque for names and euro figures echoes kit numbers and scoreboards and fits long names in narrow columns; a serif for scouting prose separates the written report from the data.
  - Layout: master-detail matches the job (scan the market, open one player, read the verdict and the replacements) without page changes.
  - Cards: flat bordered containers, one level deep, because the content is tables and figures, not objects that float.
- **Football identity signals**:
  - Mini pitch glyph (`36x24px`) per table row, marking the player's zone (`Ataque`, `Mediocampo`, `Defensa`). Pitch lines in neutral warm grey; the zone filled in ink at low opacity with an ink outline. No zone hues: the zone's position on the pitch already carries the meaning.
  - Archetype pitch banners in view 3, drawn the same way.
  - Badge hierarchy: player portrait (`44x44px` in table, `64x64px` in dossier) + club crest (`club_logo_url`) + nationality flag (`<img>` from FlagCDN) + preferred foot (`Diestro`, `Zurdo`, `Ambidiestro`).

## 2. Colour palette and roles
Each colour has one job. Ratios measured with the antislop `contrast-check.py` script.

| Token | Hex | Role | Contrast |
|---|---|---|---|
| `--canvas` | `#F4F2EC` | App background (warm newsprint paper) | n/a |
| `--surface` | `#FFFFFF` | Table, dossier, panels | n/a |
| `--surface-subtle` | `#FAF9F6` | Table header, row hover, pitch glyph ground | n/a |
| `--surface-muted` | `#EEEBE3` | "En precio" pill ground, neutral fills | n/a |
| `--ink` | `#13233A` | Primary text, figures, sidebar, focus ring, selected row bar | 15.80 on surface, 14.11 on canvas, 13.26 on muted |
| `--ink-2` | `#4A5568` | Secondary text | 7.53 on surface, 6.72 on canvas |
| `--ink-3` | `#5E6673` | Muted text, labels, placeholders | 5.79 on surface, 5.18 on canvas, 4.86 on muted, 5.03 on selected row |
| `--rule` | `#E3DFD6` | Hairlines and dividers (decorative, not a control boundary) | 1.33 on surface |
| `--control-border` | `#7F8690` | Input, select and segmented-control borders | 3.67 on surface, 3.28 on canvas, 3.08 on muted |
| `--pitch-line` | `#8F8B81` | Pitch markings in glyphs and banners | 3.40 on surface, 3.23 on subtle |
| `--selected-bg` | `#EDEFF2` | Selected table row (ink tint) | ink 13.71, ink-3 5.03 |
| `--up` | `#0B6E4F` | ONLY `undervalued`, and better-than-reference output deltas in the comparator | 6.25 on surface, 5.59 on canvas |
| `--up-bg` | `#E6F1EC` | Ground of the "Infravalorado" pill | up 5.41 |
| `--down` | `#B3261E` | ONLY `overvalued`, and worse-than-reference output deltas in the comparator | 6.54 on surface, 5.84 on canvas |
| `--down-bg` | `#F8E8E6` | Ground of the "Sobrevalorado" pill | down 5.50 |
| `--sidebar-bg` | `#13233A` | Navy sidebar (same hue as ink) | n/a |
| `--sidebar-active` | `#22395A` | Active nav item ground | white 11.66 |
| `--sidebar-text` | `#C9D1DC` | Nav labels | 10.26 on sidebar |
| `--sidebar-muted` | `#9AA7B8` | Sidebar subtitle, footer, icons | 6.47 on sidebar, 4.77 on active |

Rules:
- "En precio" (`fair`) is rendered in ink on `--surface-muted`, with no hue.
- The model estimate figure ("Valor estimado") takes the colour of the verdict (`valuation_status`), never of the raw gap: `--up` for Infravalorado, `--down` for Sobrevalorado, ink for En precio. Each player shows exactly one verdict: an "En precio" player whose estimate sits 27% above price stays ink. The dossier dumbbell's gap segment follows the same rule, with `--ink-3` for En precio (the geometry still shows the direction).
- Comparator deltas against the reference use `--up` / `--down` only for output metrics where more is unambiguously better (minutes, goals, assists, starter share, win share). Age and price deltas stay neutral in `--ink-3`: every candidate is cheaper by construction, and the savings row already says so.
- The archetype share bar uses ink tones only (`--ink`, `--ink-2`, `--control-border`), separated by 2px gaps. No new hues.
- "Activo élite" is plain secondary text, never a pill or a colour.
- Focus ring (2px, offset 2px) and the selected row (ink tint plus a 3px inset ink bar) use ink, not green. On the navy sidebar the focus ring is white.
- Replacement savings are shown in ink: a cheaper candidate is a price difference, not a valuation verdict.

## 3. Typography and hierarchy
- **Archivo** (Google Fonts, variable, `wdth 62..125`, `wght 100..900`):
  - Condensed cut (`font-stretch: 80%`) for player names and every euro figure, with `font-variant-numeric: tabular-nums`. Reason: scoreboard and kit-number voice, and long names fit narrow columns.
  - Normal width for UI text (labels, controls, table body, navigation).
- **Source Serif 4** for scouting and report prose, `15px`, line-height `1.55`, `68ch` max measure. Reason: the written report reads as a report, apart from the data.
- **Numeric discipline**: tabular numerals on every euro value, percentage, age and match statistic.
- **Scale** (only these six sizes): `11 / 12 / 13 / 15 / 20 / 28` px.
  - `28`: reserved for the two dossier valuation figures (market price and estimate).
  - `20`: page title, dossier player name, archetype title in view 3.
  - `15`: section titles, table player name and price, stat figures, report prose, brand name.
  - `13`: body and table text, controls, navigation.
  - `12`: secondary lines, pills, labels, buttons, footers.
  - `11`: stat labels and axis labels only.
- **Case**: Spanish sentence case everywhere ("Precio de mercado", "Ahorro estimado"), except proper nouns and module names (`Explorador de Mercado`, `Comparador Moneyball`, `Arquetipos Tácticos`). No wide-tracked uppercase labels.
- **Vocabulary**:
  - The model's estimate (`fair_value_eur`) is "Valor estimado". Never "Valor justo".
  - Statuses (`valuation_status`) are "Infravalorado", "En precio", "Sobrevalorado", identical in table pills, filters, comparator and report text.
- **Number format**: Spanish (`es-ES`) through one helper: thousands "5.522", money "€150,0 M" (thousands "€153 mil"), decimals with comma ("1,18"), height "1,84 m", dates "27 may 2026".

## 4. Layout
- **Desktop only**: minimum width `1440px`, designed at `1440x900`. Below 1440 the shell keeps its width and the page scrolls horizontally. The Flutter app owns responsive layouts; this preview does not.
- **Shell**: full-height grid, independent internal scroll containers, no page-level vertical scroll.
- **Sidebar (`240px`, navy)**:
  - Brand header (`DelphosFootball · Dirección Deportiva`).
  - The 3 modules: `Explorador de Mercado`, `Comparador Moneyball`, `Arquetipos Tácticos`.
  - Nav item font weight is constant across states (active is shown with ground and text colour only), so labels never reflow or wrap.
  - Footer on one line: `5.522 jugadores · 2025/26`, derived from the data.
- **Top bar**: page title and one line of plain metadata, `Temporada 2025/26 · datos al 5 jun 2026` (latest `as_of_date` in the data). No pills.
- **Filter bar (view 1)**: one row that fits inside the 24px gutters at 1440. Search, then `Estado` as the primary segmented control (`Todos | Infravalorado | En precio | Sobrevalorado`), then `Posición` and `Arquetipo` as selects, then `Restablecer filtros` (enabled only when a filter is active). Option labels match the badge names.
- **Master-detail split**: the dossier has a fixed width of `440px`; the ledger takes the rest (`692px` at 1440).
- **Market table (ledger)**: columns `Jugador | Edad | Posición | Mercado | Valor estimado | Brecha`.
  - Row padding `10px 14px`: 10px vertical and 14px at the row edges; 16px between columns (8px per cell side) so six columns fit at 1440.
  - Fixed widths `48 / 130 / 76 / 100 / 120px` for Edad, Posición, Mercado, Valor estimado and Brecha; Jugador takes the rest. No header wraps at 1440.
  - Jugador: `44x44px` portrait with a `20x20px` crest; then three lines: name, flag + club, archetype as plain muted text (`Creador Ofensivo`, `Box-to-Box`, `Ancla Defensiva`, as published by the clustering stage). Club and archetype do not share a line: together they need up to 226px and the column has about 140px, so a shared line would wrap unevenly.
  - Edad in whole years. Posición: pitch glyph + sub-position (the broad line is in a tooltip; the glyph already shows it).
  - Mercado and Valor estimado right-aligned with tabular numerals; Valor estimado coloured by status.
  - Brecha: the status pill (the only pill in the row) over the ratio estimate / price (`1,3x`). No extra sign mark: for En precio it would show a second verdict.
  - Footer on one line: `18 de 5.522 jugadores`.
  - When the explorer opens with a selection made elsewhere (archetype list, comparator, review state), the selected row is scrolled into view.
- **Dossier (fixed header + scrollable body)**:
  - **Header** (`flex-shrink: 0`, never clipped): portrait with crest, full name with room to breathe, "Activo élite" as discreet text, one line for flag, country, club and league, and one definition row with hairline separators: `Edad · Altura · Pie · Posición`. No action buttons in the header.
  - **Valuation**: "Precio de mercado" and "Valor estimado" at 28px; below them, one line with the status pill (driven only by `valuation_status`) and the gap in plain text; a labelled dumbbell (axis from €0, market dot, estimate dot, gap segment coloured by status, euro amounts at each dot, no separate legend); then the model line: "Probabilidad de infravaloración (Random Forest): NN%" from `rf_undervalued_prob`, and whether Random Forest and the decision tree agree (`rf_undervalued_pred` vs `dt_undervalued_pred`). The text never contradicts `valuation_status`.
  - **Season** (`4x2` grid): `Minutos`, `Partidos (titular)`, `Goles`, `Asistencias`, `Victorias`, `Portería imbatida`, `Goles recibidos/p`, `Tarjetas (A/R)`. Subtitle shows the archetype and the player's own `as_of_date`.
  - **Replacements**: up to 3 rows separated by hairlines (portrait, crest, name, similarity, price, savings in ink). Subtitle "Mismo arquetipo y posición · ahorro mínimo del 20%". The section header carries the secondary action "Comparar reemplazos". With fewer than 3 candidates, a note above the rows states "N de 3 reemplazos" and the reason from `shortfall_reason` (§7).
  - **Resumen**: factual report in Source Serif 4. It states figures and the status; it never claims a cause the data does not contain.
- **Comparador Moneyball (one comparison table)**: metrics as rows; the reference player and up to 3 candidates as columns.
  - The reference column comes first and is set apart by its header (`--surface-muted` header, `--surface-subtle` cells). No colour stripes.
  - Groups: "Valoración" (precio de mercado, valor estimado, estado, ahorro frente a la referencia, similitud táctica) and "Temporada 2025/26" (liga, edad, minutos, goles, asistencias, titular, victorias).
  - Candidate cells show a signed delta against the reference, computed from the values as displayed so the arithmetic on screen adds up; share deltas in percentage points ("+8 pp"). Toning per §2.
  - Savings is one row. The reference cell of that row states the price ceiling for a replacement (80% of its price).
  - With fewer than 3 candidates, one placeholder column carries "N de 3 reemplazos" and the shortfall text. Never a padded candidate.
  - Player selector above the table, "Resumen" below it.
- **Arquetipos Tácticos**:
  - Intro card with one stacked share bar: player count and share of the total per archetype, legend aligned under each segment.
  - Three cards share row tracks through CSS subgrid (top line, title block, pitch, metrics, representative players, link), so the pitch diagrams and lists align whatever the title length.
  - Representative players as a compact list of text links (flag and name on the left, price on the right, hairlines between rows). One quiet text link per card: "Ver en el explorador".

## 5. Depth and motion
- **Depth**: border only on flat containers (`1px solid var(--rule)`); shadow only on what floats (none in the current views, plus the tiny crest disc over a portrait). No card-in-card nesting: sections inside a panel are separated by hairlines and spacing, not by nested bordered boxes.
- **Motion**: `160-180ms cubic-bezier(0.16, 1, 0.3, 1)` on hover, filter switches and view changes. No loops, no pulsing.
- The dossier animates only when the selected player changes, never on filter or keystroke.
- No transitions on elements that are re-created by re-rendering; they would never run.
- Skeletons are static blocks: no shimmer, no pulse.
- `prefers-reduced-motion: reduce` cuts every animation and transition to near zero.

## 6. Anti-slop guardrails
- **NEVER** display HTTP methods or endpoints (`GET /players`, `POST /reports/generate`), database schemas (`PostgreSQL`, `analytics.*`), or snake_case column names (`residual_log10`, `rf_undervalued_prob`, `win_rate`, `clean_sheet_rate`, `goals_conceded`) anywhere in the UI.
- **NEVER** use Unicode flag emojis (always FlagCDN `<img>` tags) or em dashes.
- **NEVER** invent statistics, confidence scores or labels outside the real dataset contract. If a value is not in the data, it is not on screen.

## 7. States
Implemented in the preview so the Flutter app can copy them. Review one with the URL parameter `?state=loading | error | no-season | shortfall | empty`. With no parameter the preview shows the loaded view; unknown values are ignored. There are no demo controls in the UI.
- **Table loading** (`loading`): 8 static skeleton rows and "Cargando jugadores…" in the table footer; the dossier shows a skeleton with "Cargando ficha del jugador…"; filters are disabled; views 2 and 3 show "Cargando datos".
- **API unreachable** (`error`): one panel across table and dossier: "No se pudo conectar con el servidor de datos", one plain sentence, and "Reintentar". Retry shows the loading state for 700ms, then the loaded view, and moves focus to the page title. Filters are disabled, and views 2 and 3 show the same panel.
- **Player without season stats** (`no-season`): the first player is treated as having no season row.
  - The dossier keeps identity, valuation and replacements, and replaces the stats grid with "Sin estadísticas de temporada para este jugador."
  - Age comes from the birth date at the latest data date, and the league is omitted.
  - In the comparator, the reference's season cells read "Sin datos de temporada" and candidate cells show no deltas.
- **Replacements shortfall** (`shortfall`): opens the first player with `qualifying_count < 3` (Rayan in the current data). The text comes from `shortfall_reason`, and codes never reach the UI raw:
  - `no_same_cluster_and_position_peer`: "Ningún otro jugador comparte arquetipo y posición."
  - `no_peer_within_athletic_distance`: "Ningún jugador del mismo arquetipo y posición está dentro de la distancia de similitud exigida."
  - `no_peer_below_cost_ceiling`: "Ningún jugador similar cuesta al menos un 20% menos."
  - `no_non_overvalued_peer`: "Los jugadores similares y más baratos están sobrevalorados."
  - `fewer_than_three_qualifying_peers`: "Solo N jugadores cumplen todos los criterios: mismo arquetipo y posición, similitud suficiente, ahorro mínimo del 20% y no sobrevalorado."
  - Any other code: a generic "Solo N jugadores cumplen los criterios de reemplazo."
- **Filtered to empty** (`empty`): the filters are preset to the first status and archetype pair with no rows. The message names the active filters ("Filtros activos: estado En precio · arquetipo Ancla Defensiva."), next to "Restablecer filtros".
