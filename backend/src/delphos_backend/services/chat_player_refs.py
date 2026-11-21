"""Deterministic extraction of player IDs mentioned in a PitIA answer.

Input: the final assistant answer text and the `(player_id -> name)` registry
collected from tool results during the same turn.
Output: up to 5 ordered, deduplicated player IDs that appear in the answer.
Responsibility: runs after the model answers, outside the LLM prompt/context
window, so player cards attach only real players retrieved in the turn without
passing URLs or image metadata through the model.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

MAX_REFERENCED_PLAYERS = 5
MIN_SURNAME_CHARS = 4


def _normalize(text: str) -> str:
    """Fold case and strip combining accents for accent-tolerant matching."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def _surname(normalized_name: str) -> str | None:
    """Return the last multi-character token of a multi-word name."""
    parts = normalized_name.split()
    if len(parts) < 2:
        return None
    tail = parts[-1]
    return tail if len(tail) >= MIN_SURNAME_CHARS else None


def _word_match_start(needle: str, haystack: str) -> int | None:
    """Return the first word-bounded character index of [needle] in [haystack]."""
    if not needle:
        return None
    match = re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack)
    return match.start() if match else None


def extract_referenced_player_ids(
    answer: str,
    seen_names: dict[int, str],
    *,
    limit: int = MAX_REFERENCED_PLAYERS,
) -> list[int]:
    """Return up to [limit] player IDs from [seen_names] mentioned in [answer].

    Matches accent-insensitively on the full name first, falling back to the
    surname only when that surname is unique among players seen in the turn.
    Preserves first-mention order in [answer].
    """
    if not answer or not seen_names or limit <= 0:
        return []
    normalized_answer = _normalize(answer)
    normalized_players = {
        pid: " ".join(_normalize(raw_name).split())
        for pid, raw_name in seen_names.items()
        if isinstance(pid, int) and pid > 0 and isinstance(raw_name, str) and raw_name.strip()
    }
    surname_counts = Counter(
        surname for norm in normalized_players.values() if (surname := _surname(norm)) is not None
    )

    matches: list[tuple[int, int]] = []
    for pid, norm_name in normalized_players.items():
        pos = _word_match_start(norm_name, normalized_answer)
        if pos is None:
            surname = _surname(norm_name)
            if surname is not None and surname_counts[surname] == 1:
                pos = _word_match_start(surname, normalized_answer)
        if pos is not None:
            matches.append((pos, pid))

    matches.sort()
    return [pid for _, pid in matches[:limit]]
