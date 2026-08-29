"""The candidate's side of an interview.

`ConsoleIO` enforces the deadline on the keystroke loop rather than on a blocking read, so
what the candidate has typed when time runs out *is* the answer. That matches how a timed
interview actually behaves: you do not lose what you said because you were mid-sentence.

`FrozenOpeningIO` wraps it to replay the frozen opening answer. That answer is the
controlled stimulus of the whole experiment, so it is served from the file rather than
retyped - a re-typed opening is a different opening, and the comparison across the
eleven runs would no longer hold.
"""

from __future__ import annotations

import sys
import time

from solution.adapters.session_store import SessionStore
from solution.application.runner import CandidateIO
from solution.domain.transcript import Answer

_RULE = "-" * 72


class ConsoleIO(CandidateIO):
    def __init__(self, warn_at_seconds: int = 30) -> None:
        self.warn_at_seconds = warn_at_seconds

    def present(self, text: str) -> None:
        print(f"\n{_RULE}\nINTERVIEWER\n{_RULE}\n{text}\n")

    def collect(self, deadline_seconds: int) -> Answer:
        print(f"YOU  ({deadline_seconds}s, Enter to submit)")
        print("> ", end="", flush=True)
        started = time.perf_counter()
        text, timed_out = self._read_until(started + deadline_seconds)
        elapsed = min(time.perf_counter() - started, float(deadline_seconds))
        if timed_out:
            print("\n[time]  deadline reached - moving to the next question")
        return Answer(text=text.strip(), seconds_used=elapsed, timed_out=timed_out)

    def _read_until(self, deadline: float) -> tuple[str, bool]:
        try:
            import msvcrt
        except ImportError:
            return self._read_until_posix(deadline)

        buffer: list[str] = []
        warned = False
        while True:
            if time.perf_counter() >= deadline:
                return "".join(buffer), True

            remaining = deadline - time.perf_counter()
            if not warned and remaining <= self.warn_at_seconds:
                warned = True
                print(f"\n[{int(remaining)}s left]\n> {''.join(buffer)}", end="", flush=True)

            if not msvcrt.kbhit():
                time.sleep(0.02)
                continue

            character = msvcrt.getwch()
            if character in ("\r", "\n"):
                print()
                return "".join(buffer), False
            if character == "\x03":  # Ctrl-C
                raise KeyboardInterrupt
            if character == "\x08":  # backspace
                if buffer:
                    buffer.pop()
                    print("\b \b", end="", flush=True)
                continue
            if character.isprintable():
                buffer.append(character)
                print(character, end="", flush=True)

    def _read_until_posix(self, deadline: float) -> tuple[str, bool]:
        """Line-based fallback. Loses partial text at the deadline; Windows does not."""
        import select

        remaining = max(0.0, deadline - time.perf_counter())
        ready, _, _ = select.select([sys.stdin], [], [], remaining)
        if not ready:
            return "", True
        return sys.stdin.readline().rstrip("\n"), False


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
            timed_out=False,
        )


class SmokeIO(CandidateIO):
    """A canned candidate, for verifying the pipeline end to end without a 25-minute sitting.

    Never used for a measured run: every answer is the same short placeholder, so nothing
    it produces is evidence about anything.
    """

    ANSWER = (
        "I worked on that at Thoughtworks, mostly in TypeScript and Node.js. "
        "It went well and we shipped it."
    )

    def __init__(self, seconds_per_answer: float = 60.0) -> None:
        self.seconds_per_answer = seconds_per_answer
        self.questions: list[str] = []

    def present(self, text: str) -> None:
        self.questions.append(text)
        print(f"\n{_RULE}\nINTERVIEWER  ({len(self.questions)})\n{_RULE}\n{text}")

    def collect(self, deadline_seconds: int) -> Answer:
        print(f"\nCANNED ANSWER ({self.seconds_per_answer:.0f}s of the budget)")
        return Answer(text=self.ANSWER, seconds_used=self.seconds_per_answer, timed_out=False)
