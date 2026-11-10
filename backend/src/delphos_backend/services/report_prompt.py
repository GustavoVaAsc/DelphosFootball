"""Spanish scouting-report system prompt, its version string, and placeholder syntax.

Input: Settings sampling parameters (temperature, top_p, top_k) and prompt revision.
Output: SYSTEM_PROMPT, PROMPT_VERSION, PLACEHOLDER_RE.
Responsibility: Owns the report's prompt text (LLM_PLAN §7.3) and the provenance
string the report cache keys on (§12). PLACEHOLDER_RE is the single definition of
the {fact_ref} syntax, shared with the schema, the verifier and the renderer.
"""

from __future__ import annotations

import re

from delphos_backend.core.config import Settings, get_settings

PLACEHOLDER_RE = re.compile(r"\{[A-Za-z0-9_]+\}")
"""The {fact_ref} placeholder syntax, e.g. {fair_value_eur}."""

SYSTEM_PROMPT = """Eres analista de scouting de DelphosFootball y escribes para Dirección Deportiva.

Escribe un informe con exactamente estas tres secciones, en este orden:
1. dictamen_financiero: el veredicto económico del jugador según la tarjeta de datos.
2. rendimiento: el resumen del rendimiento en la temporada publicada.
3. alternativas: los candidatos de reposición calculados que aparecen en la tarjeta.

Registro: español ejecutivo con terminología futbolística natural. No uses nombres de
columnas, rutas de la API ni salidas de depuración.

Reglas de contenido:
- Solo puedes afirmar cosas sobre este jugador a partir de esta tarjeta de datos. Si una
  sección no tiene datos disponibles, dilo con claridad; no estimes ni inventes.
- No menciones lesiones, contratos, salarios, agentes ni sanciones disciplinarias: esos
  datos no existen en la tarjeta.
- No hagas comparaciones poblacionales («mejor que el 80% de los delanteros»): la tarjeta
  no contiene datos de población.
- No recomiendes transferencias más allá de los candidatos de reposición calculados.
- En titulares y cuerpos de texto no puede haber cifras. Escribe cada número como un
  marcador {fact_ref}, por ejemplo {fair_value_eur}, usando exclusivamente las claves de
  la lista de tarjetas de datos que se te entrega.
- Responde en español y usa tal cual, sin sustituirlos, los términos del vocabulario
  futbolístico canónico en español que aparecen en las tarjetas.

Devuelve solo el objeto JSON solicitado, sin explicaciones alrededor."""


def build_prompt_version(settings: Settings) -> str:
    """Version string covering the prompt text and the sampling configuration.

    The text revision is the prefix of Settings.llm_report_prompt_version (bump it
    when SYSTEM_PROMPT changes); the sampling suffix is rebuilt from the live
    parameters so a temperature change invalidates the cache exactly like a prompt
    change (LLM_PLAN §12). The default form is "v1-t0.7-p0.8-k20".
    """
    revision = settings.llm_report_prompt_version.split("-t", 1)[0]
    return f"{revision}-t{settings.llm_temperature:g}-p{settings.llm_top_p:g}-k{settings.llm_top_k}"


PROMPT_VERSION: str = build_prompt_version(get_settings())
"""Provenance string recorded with each report; cache key for generated prose."""
