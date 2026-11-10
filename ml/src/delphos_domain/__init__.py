"""DelphosFootball domain vocabulary package.

Input: none (package facade).
Output: the Spanish product labels and resolution helpers of `delphos_domain.labels`.
Responsibility: publish the dependency-free vocabulary as the public `delphos_domain`
surface; this facade only re-exports from `labels` and must never import the ML stack,
because backend consumers rely on `import delphos_domain` staying light.
"""

from delphos_domain.labels import (
    CLUSTER_LABELS,
    LEAGUE_LABELS,
    POSITION_LABELS,
    SUB_POSITION_LABELS,
    VALUATION_STATUS_LABELS,
    resolve_cluster_label,
    resolve_league_label,
    resolve_position_label,
    resolve_valuation_label,
)

__all__ = [
    "CLUSTER_LABELS",
    "LEAGUE_LABELS",
    "POSITION_LABELS",
    "SUB_POSITION_LABELS",
    "VALUATION_STATUS_LABELS",
    "resolve_cluster_label",
    "resolve_league_label",
    "resolve_position_label",
    "resolve_valuation_label",
]
