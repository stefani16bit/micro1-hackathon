"""Topic selection. This module is the reason the interviewer cannot tunnel: it is the
only place that decides what gets asked next, and it never reads the candidate's answers.

Two promises are encoded here and covered by tests:

1. Nothing here can shorten an answer. When the schedule falls behind, what gives way is
   the interview.
2. Breadth is never traded for depth: a follow-up happens only when every remaining
   primary question still fits in the time left.
"""

from __future__ import annotations

from solution.domain.models import Action, ActionType, TimeBudget
from solution.domain.session import SessionState


def _affords_followup(state: SessionState, budget: TimeBudget) -> bool:
    """Would a follow-up still leave room for every primary question that is owed?

    Answered against the forecast, because the real cost of a turn is not knowable in
    advance once answers are unbounded. A forecast that turns out low means the interview
    ends with primaries unasked - which is a finding about the schedule, not a reason to
    start cutting the candidate off.
    """
    remaining = budget.total_seconds - state.elapsed_seconds
    after_followup = remaining - budget.expected_turn_seconds
    return after_followup >= state.remaining_primaries * budget.expected_turn_seconds


def decide_next(
    state: SessionState,
    budget: TimeBudget,
    *,
    followup_wanted: bool,
    max_followups_per_slot: int = 1,
) -> Action:
    """Return the next interviewer action, or END with the reason it stopped."""
    remaining = budget.total_seconds - state.elapsed_seconds
    if remaining < budget.expected_turn_seconds:
        return Action(ActionType.END, reason="time_exhausted")

    if not state.opening_asked:
        return Action(ActionType.OPENING)

    open_slots = state.open_slots
    if not open_slots:
        return Action(ActionType.END, reason="all_slots_covered")

    current = open_slots[0]
    progress = state.progress[current.id]

    if not progress.primary_asked:
        return Action(ActionType.PRIMARY, slot=current)

    if (
        followup_wanted
        and progress.followups_asked < max_followups_per_slot
        and _affords_followup(state, budget)
    ):
        return Action(ActionType.FOLLOW_UP, slot=current)

    for candidate in open_slots[1:]:
        if not state.progress[candidate.id].primary_asked:
            return Action(ActionType.PRIMARY, slot=candidate)

    return Action(ActionType.END, reason="all_slots_covered")
