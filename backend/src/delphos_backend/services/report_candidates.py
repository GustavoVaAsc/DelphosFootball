"""The candidates a drafted report must carry (LLM_PLAN §8.2).

Input: a validated draft and the fact card. Output: what the draft's candidate list
does not match in the card, and the one repair request that names it.
Responsibility: check that the alternatives section assesses every candidate the card
holds, so a published report cannot silently lose a market option.

Nothing compared the two lists: a draft that left a candidate out was published, and
the report showed fewer options than the data holds without saying so. The draft is
now rejected as a schema failure — it earns the pipeline's one repair attempt — and
the deterministic renderer answers if the repair still does not carry every candidate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from delphos_backend.services.report_schema import ScoutingReportDraft

__all__ = ["build_candidate_repair_messages", "candidate_problems"]


def candidate_problems(draft: ScoutingReportDraft, card: Mapping[str, Any]) -> list[str]:
    """What the draft's candidate list does not match in the card, in words.

    A candidate the card holds and the draft does not assess is a lost market
    option. A count that differs from the card's is the same defect seen from the
    other side: the draft repeats a candidate, or adds one the card does not hold.

    The description never carries a candidate NAME: it travels into the repair
    request, which is an instruction message, and a name is database text. The
    repair points at the POSITION in the card's candidate list instead.
    """
    problems: list[str] = []
    card_names = [
        str(candidate["candidate_name"]["display"]).strip() for candidate in card["replacements"]
    ]
    drafted = [candidate.nombre.strip() for candidate in draft.alternativas.candidatos]
    absent = [name for name in card_names if name not in drafted]
    if absent:
        problems.append(f"faltan {len(absent)} de los {len(card_names)} candidatos de la tarjeta")
    if len(drafted) != len(card_names):
        problems.append(
            f"la sección de alternativas trae {len(drafted)} candidato(s) y la tarjeta "
            f"tiene {len(card_names)}"
        )
    return problems


def build_candidate_repair_messages(
    messages: Sequence[Mapping[str, str]], problems: Sequence[str]
) -> list[dict[str, str]]:
    """Append the one repair request, naming what the draft's candidate list missed.

    The request names no candidate: it points at the list the model already has
    (the data region's NOMBRES DE LOS CANDIDATOS listing) and at the positions
    it must fill, so no database string reaches an instruction message.
    """
    repair = (
        "Tu borrador anterior no evaluó a todos los candidatos de la tarjeta: "
        f"{'; '.join(problems)}. Reescribe la sección de alternativas con una valoración "
        "para CADA candidato de la lista NOMBRES DE LOS CANDIDATOS, con su nombre exacto "
        "en el campo «nombre», y no añadas ningún otro candidato."
    )
    return [dict(message) for message in messages] + [{"role": "user", "content": repair}]
