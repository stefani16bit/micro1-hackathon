"""The two guardrail rates. Both are set comparisons - no model is involved.

They are deliberately opposites, and the pair is what separates a *personalised*
interview from a *tunneled* one:

- **carry-over** counts questions that reach for something the candidate raised, outside
  the competency being asked about. That is the drift this project exists to remove.
- **grounding** counts questions that reach into the CV for something the candidate has
  *not* raised. That is the personalisation worth keeping.

A fixed questionnaire scores zero on both. A tunneling interviewer scores high on
carry-over and low on grounding. The interview we want scores high on grounding and near
zero on carry-over - which no single number could express, and is why there are two.
"""

from __future__ import annotations

from solution.domain.lexicon import extract_terms
from solution.domain.models import Slot


def _slot_vocabulary(slot: Slot | None) -> frozenset[str]:
    if slot is None:
        return frozenset()
    return frozenset({slot.name.lower(), *(keyword.lower() for keyword in slot.keywords)})


def is_carry_over(
    question: str,
    *,
    slot: Slot | None,
    prior_answer_terms: frozenset[str],
    lexicon: frozenset[str],
) -> bool:
    """Does this question pull a topic out of what the candidate already said?

    A term belonging to the competency being asked about does not count: asking about the
    slot is the job, and the candidate mentioning it first does not make it drift.
    """
    terms = extract_terms(question, lexicon)
    return bool((terms & prior_answer_terms) - _slot_vocabulary(slot))


def is_grounded(
    question: str,
    *,
    slot: Slot | None,
    resume_terms: frozenset[str],
    prior_answer_terms: frozenset[str],
    lexicon: frozenset[str],
) -> bool:
    """Does this question reach into the CV for something specific to this candidate?

    Terms already raised by the candidate are excluded: echoing an answer back is
    carry-over wearing grounding's clothes. The credit belongs to an interviewer that
    read the CV, not to one that repeats what it just heard.
    """
    terms = extract_terms(question, lexicon)
    return bool((terms & resume_terms) - _slot_vocabulary(slot) - prior_answer_terms)
