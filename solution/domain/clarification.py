"""Telling a request to repeat the question from an answer to it.

This reads the candidate's turn and does not breach the anti-tunneling property: it asks
whether the turn is an answer at all, never what it says. The topic is unchanged either
way.

Asymmetric on purpose - mistaking a real answer for a request to repeat costs the
candidate the substance of their turn, so it takes an explicit marker or a short turn that
is plainly a question.
"""

from __future__ import annotations

import re

_MARKERS = (
    "what do you mean",
    "can you clarify",
    "could you clarify",
    "can you explain",
    "could you explain",
    "can you rephrase",
    "could you rephrase",
    "not sure what you",
    "don't understand",
    "do not understand",
    "didn't understand",
    "did not understand",
    "not following",
    "say that again",
    "repeat the question",
    "nao entendi",
    "não entendi",
    "pode explicar",
    "poderia explicar",
    "como assim",
    "pode repetir",
    "poderia repetir",
    "nao ficou claro",
    "não ficou claro",
)

_SHORT_TURN = 160


def is_clarification_request(text: str) -> bool:
    """Is this the candidate asking for the question again, rather than answering it?"""
    stripped = text.strip()
    if not stripped:
        return False

    lowered = stripped.lower()
    if any(marker in lowered for marker in _MARKERS):
        return True

    return len(stripped) <= _SHORT_TURN and _is_interrogative(stripped)


def _is_interrogative(text: str) -> bool:
    """Ends on a question mark, or opens with a question word."""
    if text.rstrip().endswith("?"):
        return True
    first = re.split(r"[\s,]+", text.strip().lower(), maxsplit=1)[0]
    return first in {"what", "which", "how", "sorry", "could", "can", "would", "desculpa", "qual"}
