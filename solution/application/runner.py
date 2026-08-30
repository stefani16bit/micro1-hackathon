"""The turn loop.

Shared by all eleven iterations. Only the `Interviewer` is swapped between them, so every
fairness property the comparison depends on - the constant answer deadline, the shared
time budget, the persistence format - is implemented once and cannot drift between the
baseline and the finished system.

Two rules live here rather than in any interviewer:

- **The answer deadline is a constant.** When the schedule falls behind, the interview
  ends; the candidate's turn is never shortened to pay for it.
- **No turn is issued that the remaining time cannot honour.** Asking a question there is
  not time for produces a truncated answer and a worse measurement than not asking.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from solution.adapters.session_store import SessionStore
from solution.domain.models import TimeBudget
from solution.domain.transcript import Answer, Transcript, Utterance


class CandidateIO(ABC):
    """How the candidate is reached. A console for a live session, a script for tests."""

    @abstractmethod
    def present(self, text: str) -> None:
        """Show the interviewer's turn to the candidate."""

    @abstractmethod
    def collect(self, deadline_seconds: int) -> Answer:
        """Collect one answer, ending at the deadline whether or not it is finished."""


class Interviewer(ABC):
    """What differs between iterations. Everything else in this module does not."""

    label: str = "interviewer"

    @abstractmethod
    def next_utterance(self, transcript: Transcript) -> Utterance | None:
        """The next thing to say, or None when the interviewer considers itself done."""


@dataclass(frozen=True, slots=True)
class InterviewOutcome:
    transcript: Transcript
    end_reason: str


def run_interview(
    *,
    interviewer: Interviewer,
    io: CandidateIO,
    store: SessionStore,
    budget: TimeBudget,
    clock: Callable[[], float] = time.perf_counter,
) -> InterviewOutcome:
    transcript = Transcript()
    store.append(
        "interview_started",
        interviewer=interviewer.label,
        total_seconds=budget.total_seconds,
        answer_deadline_seconds=budget.answer_deadline_seconds,
    )

    while True:
        remaining = budget.total_seconds - transcript.elapsed_seconds
        if remaining < budget.turn_cost_seconds:
            end_reason = "time_exhausted"
            break

        started = clock()
        utterance = interviewer.next_utterance(transcript)
        generation_seconds = clock() - started

        if utterance is None:
            end_reason = "interviewer_finished"
            break

        io.present(utterance.text)
        store.append(
            "question_asked",
            kind=utterance.kind,
            slot_id=utterance.slot_id,
            text=utterance.text,
            generation_seconds=round(generation_seconds, 2),
        )
        transcript = transcript.with_question(utterance, generation_seconds)

        answer = io.collect(budget.answer_deadline_seconds)
        store.append(
            "answer_received",
            text=answer.text,
            seconds_used=round(answer.seconds_used, 2),
            over_deadline=answer.over_deadline,
        )
        transcript = transcript.with_answer(answer)

    store.append(
        "interview_ended",
        reason=end_reason,
        elapsed_seconds=round(transcript.elapsed_seconds, 2),
        questions_asked=len(transcript.questions),
    )
    return InterviewOutcome(transcript=transcript, end_reason=end_reason)
