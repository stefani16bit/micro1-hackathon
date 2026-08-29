"""Value objects shared by the whole domain. No I/O, no model calls, no mutation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SlotKind(str, Enum):
    """Determines which question template a slot falls back to when generation fails.

    Taken from research/interview-guidance.md section 2.
    """

    LANGUAGE_FRAMEWORK = "language_framework"
    DATA_STORAGE = "data_storage"
    INFRA_OPS = "infra_ops"
    CROSS_CUTTING = "cross_cutting"


@dataclass(frozen=True, slots=True)
class Slot:
    """One competency the job description requires.

    Slots come from the job description and are frozen before the interview starts.
    Candidate answers fill slots; they never create them.
    """

    id: str
    name: str
    kind: SlotKind
    keywords: tuple[str, ...]
    rank: int  # relevance order, 1 is most relevant


@dataclass(frozen=True, slots=True)
class ResumeEvidence:
    """What the resume says about one slot, resolved once and frozen before turn 1.

    `has_experience` decides behavioural versus situational phrasing; it is deliberately
    not re-derived mid-interview, so the question type cannot drift with the conversation.
    """

    slot_id: str
    has_experience: bool
    quote: str | None = None


@dataclass(frozen=True, slots=True)
class TimeBudget:
    total_seconds: int = 1500
    answer_deadline_seconds: int = 120
    turn_overhead_seconds: int = 15

    @property
    def turn_cost_seconds(self) -> int:
        return self.answer_deadline_seconds + self.turn_overhead_seconds


class ActionType(Enum):
    OPENING = "opening"
    PRIMARY = "primary"
    FOLLOW_UP = "follow_up"
    END = "end"


@dataclass(frozen=True, slots=True)
class Action:
    """What the interviewer does next. Produced by the scheduler, never by the model."""

    type: ActionType
    slot: Slot | None = None
    answer_deadline_seconds: int = 0
    reason: str = ""
