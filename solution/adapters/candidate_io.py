"""The candidate's side of an interview.

`FrozenOpeningIO` replays the frozen opening answer. That answer is the controlled
stimulus of the whole experiment, so it is served from the file rather than retyped - a
re-typed opening is a different opening, and the comparison across the ladder would
no longer hold.
"""

from __future__ import annotations

import asyncio
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from solution.adapters.session_store import SessionStore
from solution.application.opening_answer import freeze as freeze_opening
from solution.application.runner import CandidateIO
from solution.domain.transcript import Answer

_RULE = "-" * 72
_WIDTH = 88

_ANSWER_STYLE = Style.from_dict(
    {
        "": "ansigreen",
        "bottom-toolbar": "noreverse ansiblack bg:ansiwhite",
    }
)


def _clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def waiting_message(elapsed_seconds: float, total_seconds: float) -> str:
    """The line shown while the model composes.

    A function rather than an inline f-string so it can be tested: `rich` suppresses its
    spinner outside a terminal, so driving the real console under pytest captures nothing
    and would leave the clock arithmetic - the part that can actually be wrong - unpinned.
    """
    left = _clock(max(0.0, total_seconds - elapsed_seconds))
    return (
        f"[dim]composing the next question - about[/dim] [bold]{left}[/bold] "
        "[dim]left of the interview[/dim]"
    )


class ConsoleIO(CandidateIO):
    """Reads an answer with full line editing and a live view of the interview clock.

    **There is no per-answer limit.** The answer ends when the candidate submits it. The
    interview this models is spoken, and a spoken interview advances when the candidate
    stops talking - not when a timer fires. A typed deadline was a translation artefact:
    under a cap, answers crowd up against it, which is a candidate writing against a clock
    rather than answering a question.

    prompt_toolkit still owns the event loop, because the interview clock in the toolbar
    has to repaint while the candidate types and a plain `input()` blocks.

    **What removing the cap costs.** Answers can now lengthen from one run to the next,
    which shortens the interviews and would depress coverage for a reason that is not the
    interviewer. That confound is not prevented any more - it is measured instead: every
    run reports its answer durations, and `interview report` puts them beside coverage so
    a reader can tell the two explanations apart.
    """

    def __init__(self) -> None:
        self._console = Console(width=_WIDTH)
        self._elapsed = 0.0
        self._total = 0.0

    def note_progress(self, elapsed_seconds: float, total_seconds: float) -> None:
        self._elapsed = elapsed_seconds
        self._total = total_seconds

    @contextmanager
    def waiting(self, elapsed_seconds: float, total_seconds: float):
        """A spinner while the model writes, carrying the clock the toolbar cannot.

        The interview countdown lives in the answer prompt, which does not exist yet at
        this point in the turn - so without this the candidate watches a still terminal
        for however long generation takes, with no way to tell thinking from hung.

        The figure is the time left when generation *started*, and says "about" because of
        it. A live count would need a thread repainting the terminal underneath rich, for
        an accuracy nobody is served by: the number moves by the length of one generation,
        and the exact count returns the moment the candidate starts typing.
        """
        with self._console.status(
            waiting_message(elapsed_seconds, total_seconds), spinner="dots"
        ):
            yield

    def present(self, text: str) -> None:
        self._console.print()
        self._console.print(
            Panel(
                Text(text, style="yellow"),
                title="[bold yellow]INTERVIEWER[/bold yellow]",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    def _toolbar(self, started: float):
        """The interview clock only. There is no answer clock to show any more.

        Colour tracks how much of the *interview* is left, so it says something about the
        session rather than hurrying the sentence being written.
        """

        def render() -> HTML:
            parts = []
            if self._total:
                spent = time.perf_counter() - started
                remaining = max(0.0, self._total - self._elapsed - spent)
                if remaining > 300:
                    colour = "ansigreen"
                elif remaining > 120:
                    colour = "ansiyellow"
                else:
                    colour = "ansired"
                parts.append(
                    f' interview <style fg="{colour}"><b>{_clock(remaining)}</b></style> left'
                )
            parts.append("take your time")
            parts.append("Enter submits")
            return HTML("   |   ".join(parts) + " ")

        return render

    async def _read(self) -> str:
        """Wait for the candidate to submit. Nothing here ends the answer but them."""
        session: PromptSession[str] = PromptSession()
        started = time.perf_counter()
        try:
            return await session.prompt_async(
                "> ",
                style=_ANSWER_STYLE,
                bottom_toolbar=self._toolbar(started),
                refresh_interval=0.5,
            )
        except EOFError:
            return ""

    def collect(self) -> Answer:
        started = time.perf_counter()

        if not sys.stdin.isatty():
            text = sys.stdin.readline().rstrip("\n")
        else:
            text = asyncio.run(self._read())

        return Answer(text=text.strip(), seconds_used=time.perf_counter() - started)


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

    def note_progress(self, elapsed_seconds: float, total_seconds: float) -> None:
        self._inner.note_progress(elapsed_seconds, total_seconds)

    @contextmanager
    def waiting(self, elapsed_seconds: float, total_seconds: float):
        """Delegated, or the wrapper silently swallows the spinner.

        Both wrappers exist to intercept exactly one turn; every other presentation
        concern belongs to the console underneath. Inheriting the no-op default here is
        how a live run ends up with no indicator at all while still passing every test.
        """
        with self._inner.waiting(elapsed_seconds, total_seconds):
            yield

    def collect(self) -> Answer:
        if self._served:
            return self._inner.collect()

        self._served = True
        if self._store is not None:
            self._store.append("opening_answer_replayed", characters=len(self._opening_text))
        console = Console(width=_WIDTH)
        console.print(
            Panel(
                Text(self._opening_text, style="green"),
                title="[bold green]YOU[/bold green]  [dim]frozen opening, replayed verbatim[/dim]",
                border_style="green",
                padding=(1, 2),
            )
        )
        return Answer(text=self._opening_text, seconds_used=self._opening_seconds)


class CapturingOpeningIO(CandidateIO):
    """Collects the opening answer live and freezes it, then defers to the wrapped IO.

    The counterpart to `FrozenOpeningIO`, used exactly once: on the baseline run of an
    experiment that has no frozen opening yet. The candidate answers the first question as
    they would answer any other, and that answer becomes the stimulus every later run
    replays.

    Writing it here rather than printing it for someone to paste is deliberate. The frozen
    text is then character-for-character what was typed under the 120-second clock, with no
    step in between where it could be tidied up - and a tidied opening is a different
    experiment from the one that was actually run.
    """

    def __init__(
        self,
        inner: CandidateIO,
        target: Path,
        iteration: int,
        store: SessionStore | None = None,
        replacing: bool = False,
    ) -> None:
        self._inner = inner
        self._target = Path(target)
        self._iteration = iteration
        self._store = store
        self._replacing = replacing
        self._captured = False
        self._replaced: str | None = None

    @property
    def captured(self) -> bool:
        return self._captured

    @property
    def replaced(self) -> str | None:
        """The answer this one displaced, if it displaced one."""
        return self._replaced

    def present(self, text: str) -> None:
        self._inner.present(text)

    def note_progress(self, elapsed_seconds: float, total_seconds: float) -> None:
        self._inner.note_progress(elapsed_seconds, total_seconds)

    @contextmanager
    def waiting(self, elapsed_seconds: float, total_seconds: float):
        """Delegated, or the wrapper silently swallows the spinner.

        Both wrappers exist to intercept exactly one turn; every other presentation
        concern belongs to the console underneath. Inheriting the no-op default here is
        how a live run ends up with no indicator at all while still passing every test.
        """
        with self._inner.waiting(elapsed_seconds, total_seconds):
            yield

    def collect(self) -> Answer:
        answer = self._inner.collect()
        if self._captured:
            return answer

        if not answer.text.strip():
            return answer

        _, self._replaced = freeze_opening(
            self._target,
            answer.text,
            iteration=self._iteration,
            captured_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            replacing=self._replacing,
        )
        self._captured = True
        if self._store is not None:
            self._store.append(
                "opening_answer_frozen",
                path=str(self._target),
                characters=len(answer.text.strip()),
                replaced=self._replaced,
            )
        console = Console(width=_WIDTH)
        console.print(
            f"[dim]opening answer frozen to {self._target.name} - "
            f"every later run replays exactly this[/dim]"
        )
        return answer


class SmokeIO(CandidateIO):
    """A canned candidate, for verifying the pipeline end to end without a 25-minute sitting.

    Never used for a measured run. The answers rotate rather than repeat for one reason:
    a candidate that says the same thing to every question makes the interviewer re-ask
    instead of moving on, and a smoke transcript that looks like tunneling is worse than
    useless - it invites a conclusion the run cannot support. These answers are short,
    distinct and obviously placeholder, so nothing here reads as evidence about anything.
    """

    ANSWERS = (
        "[smoke placeholder] I did that at Company X, in TypeScript and Node.js.",
        "[smoke placeholder] Mostly on AWS - Lambda, SQS and Cognito.",
        "[smoke placeholder] At Company Y, in Python, with SQL behind it.",
        "[smoke placeholder] I have not done that one hands-on.",
    )

    def __init__(self, seconds_per_answer: float = 60.0) -> None:
        self.seconds_per_answer = seconds_per_answer
        self.questions: list[str] = []

    def present(self, text: str) -> None:
        self.questions.append(text)
        print(f"\n{_RULE}\nINTERVIEWER  ({len(self.questions)})\n{_RULE}\n{text}")

    def collect(self) -> Answer:
        answer = self.ANSWERS[(len(self.questions) - 1) % len(self.ANSWERS)]
        print(f"\nCANNED ANSWER ({self.seconds_per_answer:.0f}s of the budget)\n{answer}")
        return Answer(text=answer, seconds_used=self.seconds_per_answer)
