"""Fixed ORDER BY fragments for the player search.

Input: a sort key naming how the search results are ranked.
Output: the SQL ORDER BY fragment for that key.
Responsibility: the one allowlist between a caller-supplied sort key (a chat tool
argument chosen by the model) and the SQL text. The key is looked up, never
interpolated, so no caller input becomes SQL. `undervaluation` ranks by
`residual_log10`, the fair-value surplus (`predicted - market`, log10) that
`valuation_status` is cut from (ML_ARCHITECTURE §3.7), so the most undervalued
player is the one whose surplus is largest and the order agrees with the badge;
`overvaluation` is the same signal ascending. Every ordering ends in
`p.player_id`, so equal names or values page deterministically.
Kept separate from players.py to preserve the 130-line module budget.
"""

from __future__ import annotations

DEFAULT_SORT = "market_value"

PLAYER_ORDERINGS: dict[str, str] = {
    "market_value": "pred.market_value_eur DESC NULLS LAST, p.name ASC, p.player_id ASC",
    "undervaluation": "pred.residual_log10 DESC NULLS LAST, p.name ASC, p.player_id ASC",
    "overvaluation": "pred.residual_log10 ASC NULLS LAST, p.name ASC, p.player_id ASC",
}


def order_by_sql(sort_by: str) -> str:
    """Return the fixed ORDER BY fragment for a sort key; reject unknown keys."""
    try:
        return PLAYER_ORDERINGS[sort_by]
    except (KeyError, TypeError):
        raise ValueError(f"unknown sort_by: {sort_by!r}") from None
