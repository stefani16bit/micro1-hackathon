"""The turn loop, shared by every iteration. Only the `Interviewer` is swapped between
them, so the fairness properties the comparison rests on are implemented once and cannot
drift between the baseline and the finished system:

- **The candidate is never cut off.** There is no per-answer limit; the interview advances
  when the candidate submits, as a spoken screening interview advances when they stop
  talking.
- **No question is asked once the budget is spent.** Checked at the turn boundary, so an
  answer already under way may run past the mark and the interview ends after it.
- **Only an interviewer that cannot read the answers may compose ahead.** See
  `Interviewer.may_compose_ahead`.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

from solution.adapters.session_store import SessionStore
from solution.domain.models import TimeBudget
from solution.domain.transcript import Answer, Transcript, Utterance


class CandidateIO(ABC):
    """How the candidate is reached. A console for a live session, a script for tests."""

    @abstractmethod
    def present(self, text: str) -> None:
        """Show the interviewer's turn to the candidate."""

    @abstractmethod
    def collect(self) -> Answer:
        """Collect one answer, however long the candidate takes over it."""

    def note_progress(self, elapsed_seconds: float, total_seconds: float) -> None:
        """Told where the interview stands, before each answer is collected.

        Presentation only. A console implementation shows a countdown; the canned and
        scripted ones ignore it.
        """

    @contextmanager
    def waiting(self, elapsed_seconds: float, total_seconds: float) -> Iterator[None]:
        """Held open while the interviewer composes its next turn.

        The countdown lives in the answer prompt, which exists only while an answer is
        being read - so during generation there was nothing on screen at all, and the
        first thing a candidate met was a terminal that looked frozen. It cost a sitting
        before anyone noticed.

        Presentation only, and a no-op by default. `generation_seconds` is measured
        outside this block, so nothing shown here reaches a number.
        """
        yield


class Interviewer(ABC):
    """What differs between iterations. Everything else in this module does not."""

    label: str = "interviewer"

    may_compose_ahead: bool = False

    @abstractmethod
    def next_utterance(self, transcript: Transcript) -> Utterance | None:
        """The next thing to say, or None when the interviewer considers itself done."""

    def compose_ahead(self, transcript: Transcript) -> None:
        """Begin composing the next question, and return immediately.

        Called while the candidate is still answering, and only when
        `may_compose_ahead`. Implementations must not block: whatever they produce is
        picked up by the following `next_utterance`, which is free to discard it if the
        schedule has moved on.
        """

    def stopped_because(self) -> str:
        """Why `next_utterance` returned None. Overridden where the interviewer knows."""
        return "interviewer_finished"


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
        expected_answer_seconds=budget.expected_answer_seconds,
        composes_ahead=interviewer.may_compose_ahead,
    )

    while True:
        if transcript.elapsed_seconds >= budget.total_seconds:
            end_reason = "time_exhausted"
            break

        started = clock()
        with io.waiting(transcript.elapsed_seconds, budget.total_seconds):
            utterance = interviewer.next_utterance(transcript)
        generation_seconds = clock() - started

        if utterance is None:
            end_reason = interviewer.stopped_because()
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

        if interviewer.may_compose_ahead:
            interviewer.compose_ahead(transcript)

        io.note_progress(transcript.elapsed_seconds, budget.total_seconds)
        answer = io.collect()
        store.append(
            "answer_received",
            text=answer.text,
            seconds_used=round(answer.seconds_used, 2),
        )
        transcript = transcript.with_answer(answer)

    store.append(
        "interview_ended",
        reason=end_reason,
        elapsed_seconds=round(transcript.elapsed_seconds, 2),
        questions_asked=len(transcript.questions),
    )
    return InterviewOutcome(transcript=transcript, end_reason=end_reason)
