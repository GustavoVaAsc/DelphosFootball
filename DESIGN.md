# DESIGN.md - DelphosFootball (Clean Football Front-Office · Light Mode)

## 1. Visual Theme & Atmosphere
- **Archetype**: Clean Football Front-Office & Executive Scouting Suite (100% Web Desktop `1440x900px`).
- **Inspirations**: Transfermarkt, FotMob, The Athletic, and Stripe Dashboard.
- **Mood**: Daylight stadium clarity and editorial precision. Built for a Sporting Director (`Director Deportivo`), not a systems engineer. Every label uses natural football terminology in executive Spanish; zero API routes, zero SQL column identifiers, and zero terminal debug noise appear in the interface.
- **Football Identity Signals**:
  - Subtle vector pitch markings (`1px solid #E2E8F0` / `rgba(15, 23, 42, 0.05)`) in dossier headers and tactical archetype diagrams.
  - Mini Pitch Zone SVG diagrams (`36x24px`) highlighting the player's tactical zone (`Ataque`, `Mediocampo`, `Defensa`) on a clean light pitch surface (`#F0FDF4` with `#16A34A` / `#0284C7` / `#D97706` zone markers).
  - Authentic football badge hierarchy: Player portrait (`44x44px` in table, `64x64px` in dossier) + Club Crest (`club_logo_url`) + Nationality Flag (`<img>` from FlagCDN) + Preferred Foot (`Diestro`, `Zurdo`, `Ambidiestro`).

## 2. Color Palette & Roles (Daylight Stadium & Transfermarkt Editorial)
- **Canvas Background (Ice Grey / Sports Editorial Paper)**: `#F4F6F9`
- **Primary Surface (Cards, Table & Dossier)**: `#FFFFFF` (Pure White)
- **Subtle Elevated Surface (Filter Controls, Metric Boxes & Hover Rows)**: `#F8FAFC` (Hover/Subtle fill) and `#F1F5F9` (Active control surface)
- **Institutional Identity (Sidebar & Primary Typography)**:
  - Deep UEFA / Transfermarkt Navy: `#0F172A` (Primary text, numbers, and institutional accents)
  - Executive Navy Accent: `#1A3151` (Brand mark and active navigation indicator)
  - Secondary Text (Slate): `#475569`
  - Muted / Label Text: `#64748B`
- **Borders & Dividers**:
  - Default Hairline Border: `1px solid #E2E8F0`
  - Hover / Emphasized Border: `1px solid #CBD5E1`
  - Active Selection Border: `#047857` (Executive Pitch Green)
- **Semantic Football Valuation Tokens (On Light Background)**:
  - **Infravalorado / Oportunidad (`undervalued`)**: Text `#047857`, Pill Background `#ECFDF5`, Border `#A7F3D0`
  - **Valor Justo (`fair`)**: Text `#0369A1`, Pill Background `#F0F9FF`, Border `#BAE6FD`
  - **Sobrevalorado (`overvalued`)**: Text `#BE123C`, Pill Background `#FFF1F2`, Border `#FECDD3`
  - **Activo Élite (`is_elite_asset = true`)**: Text `#B45309`, Pill Background `#FFFBEB`, Border `#FDE68A`

## 3. Typography & Scannable Hierarchy
- **Display / Player Names & Financial Figures**: `Plus Jakarta Sans` or `Space Grotesk` (`600`, `700`, tracking `-0.02em`), colored in `#0F172A`.
- **UI & Editorial Scouting Prose**: `Inter` (`400`, `500`, `600`), line-height `1.55`, `60ch–70ch` max measure for scouting narratives.
- **Numeric Discipline**: `font-variant-numeric: tabular-nums` enforced across all `€M` transfer values, percentages, ages, and match statistics.
- **Scale**:
  - Dossier Player Name: `22px` (`1.375rem`), bold (`700`), `#0F172A`
  - Financial Valuation Figures: `22px` (`1.375rem`), bold (`700`), `#0F172A` / `#047857`
  - Section Title: `15px` (`0.9375rem`), semi-bold (`600`), `#0F172A`
  - Table Primary Text: `13.5px`, semi-bold (`600`), `#0F172A`
  - Metric Labels: `11.5px`, medium (`500`), `#64748B` (natural sentence case, never raw SQL column names)

## 4. Layout & Distillation Rules (`/impeccable quieter` & `/impeccable distill`)
- **Desktop Viewport**: `1440x900px` (`h-screen overflow-hidden` shell with independent internal scroll containers).
- **Distilled Left Sidebar (`240px`)**:
  - Brand Header (`DelphosFootball · Dirección Deportiva`)
  - Only the 3 core modules:
    1. `Explorador de Mercado`
    2. `Comparador Moneyball`
    3. `Arquetipos Tácticos`
  - Discreet footer indicator at the bottom: `Temporada 2025 · 5,522 Jugadores` (no technical KDD filter lists or database status widgets).
- **Single-Line Breathing Filter Bar**:
  - Search input + Segmented/Select controls on one clean horizontal row:
    - Posición: `Todas | Ataque | Mediocampo | Defensa`
    - Estado: `Todos | Infravalorados | Valor Justo | Sobrevalorados`
    - Arquetipo: `Todos | Creadores | Box-to-Box | Defensivos`
- **Modern Transfermarkt Table**:
  - Generous row padding (`12px 16px`, equivalent to `py-3 px-4`).
  - `44x44px` player portrait on a soft light background (`#F1F5F9`) with crisp `18x18px` overlapping club crest (`club_logo_url`) and FlagCDN nationality flag.
  - Short, clear Spanish archetype badges that never truncate (`Creador Ofensivo`, `Box-to-Box`, `Ancla Defensiva`).
  - Combined `Mercado vs Valor Justo` column showing Transfermarkt price (`€60.0M`), estimated Fair Value (`Valor Justo: €156.0M`), and clean valuation badge (`Infravalorado · 2.6x`).
- **Right Dossier (Unclipped Sticky/Fixed-Height Header + Scrollable Body)**:
  - **Player Header (`flex-shrink: 0`)**: Never clipped by scroll. Displays `64x64px` portrait, club crest, nationality flag, full name, `Activo Élite` badge, and clean bio strip (`Edad`, `Altura`, `Pie hábil`, `Posición`, `Club y Liga`).
  - **Financial Valuation Card**: Clean white/soft-slate card comparing `Precio de Mercado` vs `Valor Justo`, opportunity badge (`Oportunidad: +€40.8M (+27%)`), a single comparative progress bar, and `Confianza del modelo: 88% (Consenso Positivo)`.
  - **2025 Season Metrics (`4x2` Grid)**: Lightweight 4-column by 2-row grid with label above in `#64748B` and large number below in `#0F172A`, using strictly human Spanish labels (`Minutos`, `Partidos (Titular)`, `Goles`, `Asistencias`, `% Victorias`, `Portería imbatida`, `Goles recibidos/p`, `Tarjetas (A/R)`) without repeating `"Temp. 2025"`.
  - **Top 3 Profitable Tactical Replacements**: 3 clean white cards (`#FFFFFF`, `1px solid #E2E8F0`) showing Portrait, Club Crest, Name, `% Similitud Táctica`, `Precio`, and highlighted green net savings pill (`Ahorra €35.0M · -32%`).

## 5. Depth, Elevation & Motion
- **Card Elevation**: `0 1px 3px rgba(15, 23, 42, 0.04)` with `1px solid #E2E8F0` border.
- **Micro-Interactions**: `160ms cubic-bezier(0.16, 1, 0.3, 1)` on row hover, filter switches, and view transitions. Zero pulsing or distracting animations.

## 6. Anti-Slop Guardrails
- **NEVER** display HTTP methods/endpoints (`GET /players`, `POST /reports/generate`), database schemas (`PostgreSQL`, `analytics.*`), or snake_case column names (`residual_log10`, `rf_undervalued_prob`, `win_rate`, `clean_sheet_rate`, `goals_conceded`) anywhere in the UI.
- **NEVER** use Unicode flag emojis (always use FlagCDN `<img>` tags) or em-dashes (`—`).
- **NEVER** invent statistics outside the real dataset contract.
