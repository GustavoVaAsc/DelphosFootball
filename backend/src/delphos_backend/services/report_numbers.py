"""Numeric token extraction for the scouting-report verifier (LLM_PLAN §8.2).

Input: Spanish report prose. Output: the numeric tokens it contains, each with its
offset and a context snippet, plus the canonical value of a token.
Responsibility: recognise the numeric spellings the product uses (`€25.0M`, `75%`,
`1.8x`, `1,800`) and reduce each of them to a canonical value, so the verifier can
compare the numbers in the prose with the numbers of the fact card by value instead
of by spelling.

The tokeniser and the canonicaliser are one concept — a token only means something
once the rules that read it are applied — so they share this module; the checker
that uses them lives in `report_verify`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from delphos_backend.services.report_prompt import PLACEHOLDER_RE

_NUMBER_TOKEN_RE = re.compile(
    r"""
    (?<![\d.,])                                  # not the tail of a longer number
    [+-]?€?                                      # optional sign and currency symbol
    (?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?|\d+(?:,\d{1,2})?)  # grouped, decimal or malformed comma
    (?:%|x|[KMB])?                               # percent, ratio or magnitude suffix
    (?!(?:\d|,\d))                              # not a digit, and not a comma continuing the number
    """,
    re.VERBOSE,
)
_SUFFIX_SCALE = {"k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}
_CONTEXT_WINDOW = 24
_ENTITY_RE = re.compile(r"&#x?[0-9a-fA-F]+;")
"""A numeric HTML entity, e.g. `&#x27;` for the apostrophe `html.escape` writes."""


@dataclass(frozen=True)
class NumberToken:
    """One numeric token in prose: the literal token, its offset, and a snippet."""

    token: str
    start: int
    context: str


def canonicalize_number(token: str) -> str | None:
    """Canonical value of a numeric token: '€25.0M' -> '25000000', '75%' -> '0.75'.

    Dot is decimal (product convention); comma is a thousands separator only, and a
    comma used otherwise returns None so the verifier flags it. None means "not a
    number this product can have written".
    """
    text = token.strip().replace("€", "").replace(" ", "")
    if not text:
        return None
    negative = text.startswith("-")
    text = text.lstrip("+-")
    scale = 1.0
    percent = False
    if text.endswith("%"):
        text, percent = text[:-1], True
    elif text and text[-1].lower() in _SUFFIX_SCALE:
        scale = _SUFFIX_SCALE[text[-1].lower()]
        text = text[:-1]
    elif text.endswith("x"):
        text = text[:-1]
    if "," in text:
        if not re.fullmatch(r"\d{1,3}(?:,\d{3})+", text):
            return None
        text = text.replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return None
    if percent:
        value /= 100.0
    if negative:
        value = -value
    return format(value * scale, ".12g")


def extract_number_tokens(text: str) -> list[NumberToken]:
    """Every numeric token in text with offset and context (formats per LLM_PLAN §7.4).

    Two kinds of text are blanked out before scanning, keeping the offsets
    stable, because neither is a numeric claim of the prose:

    - {fact_ref} placeholders: their keys are backend-controlled references, not
      model assertions;
    - numeric HTML entities: the report is escaped before it is verified, so an
      apostrophe in a player's name reads as `&#x27;` and its `27` would be
      flagged as an ungrounded number.
    """
    masked = PLACEHOLDER_RE.sub(lambda match: " " * len(match.group(0)), text)
    masked = _ENTITY_RE.sub(lambda match: " " * len(match.group(0)), masked)
    occurrences = []
    for match in _NUMBER_TOKEN_RE.finditer(masked):
        occurrences.append(
            NumberToken(
                token=match.group(0),
                start=match.start(),
                context=text[
                    max(0, match.start() - _CONTEXT_WINDOW) : match.end() + _CONTEXT_WINDOW
                ],
            )
        )
    return occurrences
