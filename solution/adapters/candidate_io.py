"""The candidate's side of an interview.

`FrozenOpeningIO` replays the frozen opening answer. That answer is the controlled
stimulus of the whole experiment, so it is served from the file rather than retyped - a
re-typed opening is a different opening, and the comparison across the eleven runs would
no longer hold.
"""

from __future__ import annotations

import time

from solution.adapters.session_store import SessionStore
from solution.application.runner import CandidateIO
from solution.domain.transcript import Answer

_RULE = "-" * 72


class ConsoleIO(CandidateIO):
    """Reads an answer using the terminal's own line editing.

    The deadline is a target, not a cut. A blocking read cannot be interrupted cleanly,
    and every workaround costs the candidate arrow keys, Home/End and everything else the
    console gives for free - a bad trade for someone typing eleven interviews. Capturing
    half-written text was never required either: the rule is that an answer not submitted
    in time means the interview moves on, not that a fragment gets recorded.

    So the control becomes detection rather than prevention. The answer is accepted
    whenever it is submitted, the real time is recorded, and going over is flagged. If
    answers lengthen across iterations - which would shorten interviews and depress
    coverage for reasons that have nothing to do with the interviewer - that shows up as
    a number instead of hiding inside one.
    """

    def present(self, text: str) -> None:
        print(f"\n{_RULE}\nINTERVIEWER\n{_RULE}\n{text}\n")

    def collect(self, deadline_seconds: int) -> Answer:
        print(f"YOU  (target {deadline_seconds}s - Enter submits)")
        started = time.perf_counter()
        try:
            text = input("> ")
        except EOFError:
            text = ""
        elapsed = time.perf_counter() - started
        over_deadline = elapsed > deadline_seconds
        if over_deadline:
            print(f"[time]  {elapsed:.0f}s, over the {deadline_seconds}s target - recorded")
        return Answer(text=text.strip(), seconds_used=elapsed, over_deadline=over_deadline)


class FrozenOpeningIO(CandidateIO):
    """Replays the frozen opening answer, then defers to the wrapped IO."""

    def __init__(
        self,
        inner: CandidateIO,
        opening_text: str,
        opening_seconds: float,
        store: SessionStore | None = None,
    ) -> None:
        self._inner = inner
        self._opening_text = opening_text
        self._opening_seconds = opening_seconds
        self._store = store
        self._served = False

    def present(self, text: str) -> None:
        self._inner.present(text)

    def collect(self, deadline_seconds: int) -> Answer:
        if self._served:
            return self._inner.collect(deadline_seconds)

        self._served = True
        if self._store is not None:
            self._store.append("opening_answer_replayed", characters=len(self._opening_text))
        print(f"YOU  (frozen opening answer, replayed verbatim)\n{self._opening_text}\n")
        return Answer(
            text=self._opening_text,
            seconds_used=self._opening_seconds,
            over_deadline=False,
        )


class SmokeIO(CandidateIO):
    """A canned candidate, for verifying the pipeline end to end without a 25-minute sitting.

    Never used for a measured run. The answers rotate rather than repeat for one reason:
    a candidate that says the same thing to every question makes the interviewer re-ask
    instead of moving on, and a smoke transcript that looks like tunneling is worse than
    useless - it invites a conclusion the run cannot support. These answers are short,
    distinct and obviously placeholder, so nothing here reads as evidence about anything.
    """

    ANSWERS = (
        "[smoke placeholder] I did that at Thoughtworks, in TypeScript and Node.js.",
        "[smoke placeholder] Mostly on AWS - Lambda, SQS and Cognito.",
        "[smoke placeholder] At Accenture, in Python, with SQL behind it.",
        "[smoke placeholder] I have not done that one hands-on.",
    )

    def __init__(self, seconds_per_answer: float = 60.0) -> None:
        self.seconds_per_answer = seconds_per_answer
        self.questions: list[str] = []

    def present(self, text: str) -> None:
        self.questions.append(text)
        print(f"\n{_RULE}\nINTERVIEWER  ({len(self.questions)})\n{_RULE}\n{text}")

    def collect(self, deadline_seconds: int) -> Answer:
        answer = self.ANSWERS[(len(self.questions) - 1) % len(self.ANSWERS)]
        print(f"\nCANNED ANSWER ({self.seconds_per_answer:.0f}s of the budget)\n{answer}")
        return Answer(text=answer, seconds_used=self.seconds_per_answer, over_deadline=False)
