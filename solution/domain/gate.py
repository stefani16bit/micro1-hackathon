"""Verification of everything the interviewer is about to say.

The model is free to write; it is not free to wander. The gate is deterministic on
purpose: an anti-tunneling property that depends on a model behaving well is a hope,
whereas a set comparison is a guarantee. Every decision here is logged, so the gate's
own rejection rate becomes evidence in the changelog rather than an untested claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from solution.domain.lexicon import extract_terms
from solution.domain.models import Slot

_SITUATIONAL_MARKERS = (
    "how would you",
    "what would you",
    "you're asked to",
    "you are asked to",
    "suppose you",
    "imagine you",
    "if you were",
)


class Violation(str, Enum):
    OFF_SLOT = "off_slot"
    CARRY_OVER = "carry_over"
    LEAKAGE = "leakage"
    FORM = "form"


@dataclass(frozen=True, slots=True)
class GateContext:
    slot: Slot
    lexicon: frozenset[str]
    prior_answer_terms: frozenset[str] = frozenset()
    allowed_terms: frozenset[str] = frozenset()
    expect_behavioural: bool = True


@dataclass(frozen=True, slots=True)
class GateResult:
    violations: tuple[Violation, ...] = ()
    evidence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.violations


def _slot_terms(slot: Slot) -> frozenset[str]:
    return frozenset({slot.name.lower(), *(k.lower() for k in slot.keywords)})


def _names_the_slot(text: str, slot: Slot, terms: frozenset[str]) -> bool:
    if terms & _slot_terms(slot):
        return True
    lowered = text.lower()
    return any(term in lowered for term in _slot_terms(slot))


def check_question(text: str, context: GateContext) -> GateResult:
    """Verify a primary question or a follow-up before the candidate ever sees it."""
    terms = extract_terms(text, context.lexicon)
    slot_terms = _slot_terms(context.slot)
    violations: list[Violation] = []
    evidence: dict[str, tuple[str, ...]] = {}

    if not _names_the_slot(text, context.slot, terms):
        violations.append(Violation.OFF_SLOT)
        evidence["off_slot"] = tuple(sorted(slot_terms))

    carried = (terms & context.prior_answer_terms) - slot_terms - context.allowed_terms
    if carried:
        violations.append(Violation.CARRY_OVER)
        evidence["carry_over"] = tuple(sorted(carried))

    form_problems: list[str] = []
    if text.count("?") != 1:
        form_problems.append("expected exactly one question")

    is_situational = any(marker in text.lower() for marker in _SITUATIONAL_MARKERS)
    if context.expect_behavioural and is_situational:
        form_problems.append("situational phrasing for a candidate with the experience")
    if not context.expect_behavioural and not is_situational:
        form_problems.append("behavioural phrasing for a candidate without the experience")

    if form_problems:
        violations.append(Violation.FORM)
        evidence["form"] = tuple(form_problems)

    return GateResult(violations=tuple(violations), evidence=evidence)


def check_clarification(text: str, context: GateContext) -> GateResult:
    """Verify a reply to a candidate's clarification request.

    Restating, scoping and encouraging are allowed. Introducing technical content the
    candidate has not produced is assistance, and assistance corrupts the measurement.
    """
    terms = extract_terms(text, context.lexicon)
    leaked = terms - context.allowed_terms
    if not leaked:
        return GateResult()
    return GateResult(
        violations=(Violation.LEAKAGE,),
        evidence={"leakage": tuple(sorted(leaked))},
    )
