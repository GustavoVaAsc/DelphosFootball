"""Spanish product vocabulary for DelphosFootball.

Input: English keys from the data: `position`, `sub_position`, Transfermarkt `league_id`,
`valuation_status`, and `cluster_id`.
Output: the approved Spanish string for each key, through the five mapping constants and
the `resolve_*` helpers that the report and the API call.
Responsibility: single owner of the product's Spanish copy for the five vocabulary groups,
kept import-free so consumers read the labels without pulling in the ML stack.

Unknown-key policy: every `resolve_*` helper returns the raw input for an unknown key
instead of raising or returning `None`, mirroring the frontend's
`LEAGUE_NAMES[s.league_id] || s.league_id` (frontend/design-preview/index.html:1631).
The mapping constants are plain dicts: direct indexing of an unknown key raises
`KeyError`, so go through a helper whenever the key may be missing.

The mappings and their helpers stay in one module because they are one vocabulary;
splitting them would scatter the approved copy across files.
"""

# Approved product copy; do not reword without a product decision.
# Mirrors POS_LABELS in the design preview (frontend/design-preview/index.html:1494),
# which is the source of truth for this vocabulary.
POSITION_LABELS: dict[str, str] = {
    "Attack": "Ataque",
    "Midfield": "Mediocampo",
    "Defender": "Defensa",
}

# Approved product copy; do not reword without a product decision.
SUB_POSITION_LABELS: dict[str, str] = {
    "Centre-Forward": "Delantero Centro",
    "Right Winger": "Extremo Derecho",
    "Left Winger": "Extremo Izquierdo",
    "Second Striker": "Segundo Delantero",
    "Attacking Midfield": "Mediapunta",
    "Central Midfield": "Mediocentro",
    "Defensive Midfield": "Pivote Defensivo",
    "Right Midfield": "Interior Derecho",
    "Left Midfield": "Interior Izquierdo",
    "Centre-Back": "Defensa Central",
    "Right-Back": "Lateral Derecho",
    "Left-Back": "Lateral Izquierdo",
}

# Approved product copy; do not reword without a product decision.
LEAGUE_LABELS: dict[str, str] = {
    "GB1": "Premier League",
    "ES1": "LaLiga",
    "L1": "Bundesliga",
    "IT1": "Serie A",
    "FR1": "Ligue 1",
    "PO1": "Primeira Liga",
    "NL1": "Eredivisie",
    "TR1": "Süper Lig",
    "BE1": "Pro League",
    "DK1": "Superliga",
    "SC1": "Premiership",
    "GR1": "Super League",
    "UKR1": "Premier Liga",
    "RU1": "Premier Liga",
}

# Approved product copy; do not reword without a product decision.
VALUATION_STATUS_LABELS: dict[str, str] = {
    "undervalued": "Infravalorado",
    "fair": "Valor Justo",
    "overvalued": "Sobrevalorado",
}

# Approved product copy; do not reword without a product decision.
# Cluster ids are integers in the data; the value is (short name, full archetype name).
CLUSTER_LABELS: dict[int, tuple[str, str]] = {
    0: ("Creador Ofensivo", "Creadores Ofensivos y Finalizadores"),
    1: ("Box-to-Box", "Todocampistas Box-to-Box y Carrileros"),
    2: ("Ancla Defensiva", "Anclas Defensivas y Especialistas de Contención"),
}


def resolve_position_label(position: str | None, sub_position: str | None) -> str:
    """Return the Spanish label for a player's position.

    Prefers `sub_position`, then `position`, then the raw English `position` (the
    frontend's `SUBPOS_LABELS[sub] || POS_LABELS[pos] || pos`); an unknown key returns
    the raw input rather than raising.
    """
    if sub_position and (label := SUB_POSITION_LABELS.get(sub_position)):
        return label
    if position and (label := POSITION_LABELS.get(position)):
        return label
    return position or sub_position or ""


def resolve_league_label(league_id: str) -> str:
    """Return the Spanish league name, or `league_id` itself when the id is unknown."""
    return LEAGUE_LABELS.get(league_id, league_id)


def resolve_valuation_label(valuation_status: str) -> str:
    """Return the Spanish valuation-status label, or the raw status when unknown."""
    return VALUATION_STATUS_LABELS.get(valuation_status, valuation_status)


def resolve_cluster_label(cluster_id: int) -> tuple[str, str] | int:
    """Return the (short name, full name) pair for a cluster, or `cluster_id` if unknown."""
    return CLUSTER_LABELS.get(cluster_id, cluster_id)
