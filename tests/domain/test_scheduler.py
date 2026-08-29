"""The scheduler encodes two promises to the candidate: the answer deadline is a constant,
and breadth is never traded for depth. Both are tested here rather than asserted in prose."""

import pytest

from solution.domain.models import ActionType, Slot, SlotKind, TimeBudget
from solution.domain.scheduler import decide_next
from solution.domain.session import SessionState

BUDGET = TimeBudget(total_seconds=1500, answer_deadline_seconds=120, turn_overhead_seconds=15)
TURN = 135  # answer_deadline + turn_overhead


def slot(rank: int, sid: str) -> Slot:
    return Slot(id=sid, name=sid, kind=SlotKind.CROSS_CUTTING, keywords=(sid,), rank=rank)


SLOTS = (slot(1, "backend"), slot(2, "frontend"), slot(3, "cloud"))


def state(**kw) -> SessionState:
    return SessionState.initial(SLOTS).evolve(**kw)


def test_a_fresh_session_opens_with_the_standard_opening_turn():
    assert decide_next(state(), BUDGET, followup_wanted=False).type is ActionType.OPENING


def test_after_the_opening_it_asks_the_highest_ranked_slot_first():
    action = decide_next(state(opening_asked=True), BUDGET, followup_wanted=False)
    assert action.type is ActionType.PRIMARY
    assert action.slot.id == "backend"


def test_slots_are_asked_in_relevance_order():
    s = state(opening_asked=True).with_closed("backend")
    assert decide_next(s, BUDGET, followup_wanted=False).slot.id == "frontend"


def test_a_followup_is_allowed_when_every_remaining_primary_still_fits():
    s = state(opening_asked=True, elapsed_seconds=TURN).with_primary_asked("backend")
    action = decide_next(s, BUDGET, followup_wanted=True)
    assert action.type is ActionType.FOLLOW_UP
    assert action.slot.id == "backend"


def test_breadth_beats_depth_when_time_only_covers_the_remaining_primaries():
    # Two primaries left (frontend, cloud) and room for exactly two more turns:
    # the follow-up must be refused even though the model asked for it.
    s = state(
        opening_asked=True,
        elapsed_seconds=BUDGET.total_seconds - 2 * TURN,
    ).with_primary_asked("backend")
    action = decide_next(s, BUDGET, followup_wanted=True)
    assert action.type is ActionType.PRIMARY
    assert action.slot.id == "frontend"


def test_the_followup_budget_is_capped_per_slot():
    s = state(opening_asked=True, elapsed_seconds=TURN).with_primary_asked("backend")
    s = s.with_followup_asked("backend")
    action = decide_next(s, BUDGET, followup_wanted=True, max_followups_per_slot=1)
    assert action.type is ActionType.PRIMARY


def test_the_interview_ends_once_every_slot_is_closed():
    s = state(opening_asked=True)
    for sid in ("backend", "frontend", "cloud"):
        s = s.with_closed(sid)
    action = decide_next(s, BUDGET, followup_wanted=False)
    assert action.type is ActionType.END
    assert action.reason == "all_slots_covered"


def test_no_turn_is_issued_that_the_remaining_time_cannot_honour():
    s = state(opening_asked=True, elapsed_seconds=BUDGET.total_seconds - TURN + 1)
    action = decide_next(s, BUDGET, followup_wanted=False)
    assert action.type is ActionType.END
    assert action.reason == "time_exhausted"


@pytest.mark.parametrize("elapsed", [0, 600, 1200, 1364])
def test_the_answer_deadline_never_shrinks_with_remaining_time(elapsed):
    """D6: the interview shortens, the candidate's turn does not."""
    s = state(opening_asked=True, elapsed_seconds=elapsed)
    action = decide_next(s, BUDGET, followup_wanted=False)
    assert action.answer_deadline_seconds == BUDGET.answer_deadline_seconds
