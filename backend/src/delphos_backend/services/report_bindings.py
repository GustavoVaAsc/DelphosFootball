"""Binding the model's draft to the fact card.

Input: one drafted candidate and the fact card. Output: the card's candidate the
draft names, or an error. Responsibility: decide which card candidate a drafted
candidate refers to, and raise the errors that make the caller fall back to the
deterministic renderer.

A candidate is bound by name, never by position in a list: a model that reorders
its candidates would otherwise attribute one candidate's savings to another, a
wrong number about a real person published as if the model had written it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from delphos_backend.services.report_schema import ReplacementCandidate


class UnknownPlaceholderError(ValueError):
    """A draft cited a `{fact_ref}` key the fact card does not contain."""

    def __init__(self, key: str) -> None:
        super().__init__(f"draft cited unknown fact key {key!r}")


class UnknownCandidateError(UnknownPlaceholderError):
    """A draft named a candidate the fact card does not contain."""

    def __init__(self, name: str) -> None:
        # The parent's constructor would word this as a fact key, so the message is
        # built here; the class stays a subclass so one `except` covers both.
        ValueError.__init__(self, f"draft named an unknown candidate {name!r}")


def bind_candidate_scope(
    candidate: ReplacementCandidate,
    card: Mapping[str, Any],
) -> Mapping[str, dict[str, Any]]:
    """The card's candidate whose name the draft repeats verbatim.

    The name is compared after stripping the surrounding whitespace, and exactly:
    a name the card does not contain raises `UnknownCandidateError`, so the
    published sentence is either about the right player or not published at all.
    """
    wanted = candidate.nombre.strip()
    for scope in card["replacements"]:
        if str(scope["candidate_name"]["display"]).strip() == wanted:
            return scope
    raise UnknownCandidateError(wanted)
