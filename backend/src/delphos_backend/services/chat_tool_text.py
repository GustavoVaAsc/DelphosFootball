"""Small text helpers shared by the Spanish tool-call descriptions.

Input: untrusted display text, cluster ids, and a preposition phrase plus a noun phrase.
Output: sanitised text, a cluster name, and the contracted preposition phrase.
Responsibility: keep the sanitiser, the cluster name and the "de el" -> "del" and
"a el" -> "al" contraction in one place, so the describe modules stay under the
module-size budget and agree on how untrusted text is cleaned.
"""

from __future__ import annotations

import re
import unicodedata

from delphos_domain import resolve_cluster_label

MAX_NAME_CHARS = 40
_UNSAFE_TEXT = re.compile(r"[\x00-\x1f\x7f-\x9f{}\[\]<>\\\"_«»]")
_UNSAFE_CATEGORIES = {"Cc", "Cf", "Zl", "Zp"}
_CONTRACTIONS = {"de": "del", "a": "al"}


def safe_display_text(text: str) -> str:
    """Untrusted text made safe to show: no control or structural characters, capped."""
    kept = "".join(" " if unicodedata.category(c) in _UNSAFE_CATEGORIES else c for c in text)
    return " ".join(_UNSAFE_TEXT.sub(" ", kept).split())[:MAX_NAME_CHARS].strip()


def cluster_name(cluster_id: int) -> str:
    """The short Spanish archetype name of a cluster id."""
    label = resolve_cluster_label(cluster_id)
    return label[0] if isinstance(label, tuple) else str(label)


def contract(lead: str, phrase: str) -> str:
    """Join a lead ending in 'de' or 'a' to a phrase, contracting before 'el '."""
    head, _, last = lead.rpartition(" ")
    if phrase.startswith("el ") and last in _CONTRACTIONS:
        return f"{head} {_CONTRACTIONS[last]} {phrase[3:]}"
    return f"{lead} {phrase}"
