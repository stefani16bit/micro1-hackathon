"""The candidate's side of an interview.

`FrozenOpeningIO` replays the frozen opening answer. That answer is the controlled
stimulus of the whole experiment, so it is served from the file rather than retyped - a
re-typed opening is a different opening, and the comparison across the eleven runs would
no longer hold.
"""

from __future__ import annotations

import asyncio
import sys
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from solution.adapters.session_store import SessionStore
from solution.application.runner import CandidateIO
from solution.domain.transcript import Answer

_RULE = "-" * 72
_WIDTH = 88

# The candidate types in green; the interviewer speaks in yellow.
_ANSWER_STYLE = Style.from_dict(
    {
        "": "ansigreen",  # what the candidate types
        "bottom-toolbar": "noreverse ansiblack bg:ansiwhite",
    }
)


def _clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class ConsoleIO(CandidateIO):
    """Reads an answer with full line editing, a live countdown, and a hard deadline.

    prompt_toolkit owns the event loop, which makes all three possible at once. A plain
    `input()` could offer none of them: it blocks, so no countdown can repaint and no
    timer can interrupt it. Every earlier compromise here came from that limitation, not
    from a design preference.

    At the deadline the prompt is closed and **whatever has been typed becomes the
    answer**. That keeps the rule the candidate specified - an answer not submitted in
    time does not stop the interview - while removing a confound it would otherwise
    leave: if answers were allowed to run long, they would lengthen across iterations,
    shorten the interviews and depress coverage for a reason that is not the interviewer.
    """

    def __init__(self) -> None:
        self._console = Console(width=_WIDTH)
        self._elapsed = 0.0
        self._total = 0.0

    def note_progress(self, elapsed_seconds: float, total_seconds: float) -> None:
        self._elapsed = elapsed_seconds
        self._total = total_seconds

    def present(self, text: str) -> None:
        # markup=False: a question may legitimately contain square brackets, and rich
        # would otherwise read them as styling tags and swallow them.
        self._console.print()
        self._console.print(
            Panel(
                Text(text, style="yellow"),
                title="[bold yellow]INTERVIEWER[/bold yellow]",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    def _toolbar(self, started: float, deadline_seconds: int):
        def render() -> HTML:
            spent = time.perf_counter() - started
            answer_left = max(0.0, deadline_seconds - spent)
            if answer_left > 45:
                colour = "ansigreen"
            elif answer_left > 15:
                colour = "ansiyellow"
            else:
                colour = "ansired"
            parts = [
                f' this answer <style fg="{colour}"><b>{_clock(answer_left)}</b></style>',
            ]
            if self._total:
                remaining = max(0.0, self._total - self._elapsed - spent)
                parts.append(f"interview {_clock(remaining)} left")
            parts.append("Enter submits")
            return HTML("   |   ".join(parts) + " ")

        return render

    async def _read_with_deadline(self, deadline_seconds: int) -> tuple[str, bool]:
        """Return (text, was_cut). At the deadline the prompt closes and keeps the draft."""
        session: PromptSession[str] = PromptSession()
        started = time.perf_counter()
        was_cut = False

        async def cut() -> None:
            nonlocal was_cut
            await asyncio.sleep(deadline_seconds)
            was_cut = True
            application = session.app
            if application.is_running:
                application.exit(result=session.default_buffer.text)

        timer = asyncio.ensure_future(cut())
        try:
            text = await session.prompt_async(
                "> ",
                style=_ANSWER_STYLE,
                bottom_toolbar=self._toolbar(started, deadline_seconds),
                refresh_interval=0.5,
            )
        except EOFError:
            text = ""
        finally:
            timer.cancel()
        return text, was_cut

    def collect(self, deadline_seconds: int) -> Answer:
        started = time.perf_counter()

        if not sys.stdin.isatty():
            # No terminal to draw a toolbar on. Degrade to a plain read rather than crash.
            text, was_cut = sys.stdin.readline().rstrip("\n"), False
        else:
            text, was_cut = asyncio.run(self._read_with_deadline(deadline_seconds))

        elapsed = min(time.perf_counter() - started, float(deadline_seconds))
        if was_cut:
            self._console.print(
                f"[dim]{_clock(deadline_seconds)} reached - "
                f"kept what you had written and moved on[/dim]"
            )
        return Answer(text=text.strip(), seconds_used=elapsed, over_deadline=was_cut)


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

    def collect(self, deadline_seconds: int) -> Answer:
        if self._served:
            return self._inner.collect(deadline_seconds)

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
