"""The console is where the promise not to rush the candidate is actually kept.

The whole of this file used to test the opposite: a 120-second timer that closed the
prompt and kept whatever draft was there. That was a translation artefact — the interview
being modelled is spoken, and a spoken interview advances when the candidate stops
talking. These tests now pin the absence of the timer, because an absence is exactly the
kind of property that gets reintroduced by accident.

They drive the real prompt through a pipe rather than a stub, so what is checked is the
thing that runs during an interview.
"""

from contextlib import contextmanager
import asyncio
import time

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from solution.adapters.candidate_io import (
    CapturingOpeningIO,
    ConsoleIO,
    FrozenOpeningIO,
    waiting_message,
)


def read(typed: str) -> str:
    io = ConsoleIO()
    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input, output=DummyOutput()):
            pipe_input.send_text(typed)
            return asyncio.run(io._read())


def test_the_answer_is_whatever_the_candidate_submitted():
    assert read("I built payment services.\r") == "I built payment services."


def test_nothing_ends_the_answer_but_the_candidate():
    """There is no timer to cancel, no deadline argument, and no way to pass one.

    Checked against the signature rather than by waiting, because a test that waits for a
    timer that should not exist can only ever pass slowly or fail slowly.
    """
    import inspect

    assert list(inspect.signature(ConsoleIO.collect).parameters) == ["self"]
    assert list(inspect.signature(ConsoleIO._read).parameters) == ["self"]
    assert not hasattr(ConsoleIO, "_read_with_deadline")


def test_a_long_answer_is_returned_whole():
    """The confound this reintroduces — answers lengthening between runs — is measured in
    the metrics rather than prevented here. See `describe()` in evals/metrics/measure.py."""
    long_answer = ("I built payment services. " * 60).strip()
    assert read(long_answer + "\r") == long_answer


def test_an_empty_submission_is_recorded_as_empty_rather_than_lost():
    assert read("\r") == ""


class TestTheToolbar:
    def test_shows_the_interview_clock_when_the_runner_has_reported_progress(self):
        io = ConsoleIO()
        io.note_progress(elapsed_seconds=600.0, total_seconds=1500.0)
        rendered = str(io._toolbar(started=time.perf_counter())().value)
        assert "interview" in rendered
        assert "left" in rendered

    def test_shows_no_clock_for_the_answer_itself(self):
        """A clock on the answer is the pressure this change removed. It must not creep
        back in as a display-only feature: a candidate watching a number count up against
        their own sentence is being hurried by it either way."""
        io = ConsoleIO()
        io.note_progress(elapsed_seconds=600.0, total_seconds=1500.0)
        rendered = str(io._toolbar(started=time.perf_counter())().value)
        assert "this answer" not in rendered
        assert "take your time" in rendered

    def test_never_shows_a_negative_clock_when_the_interview_has_overrun(self):
        io = ConsoleIO()
        io.note_progress(elapsed_seconds=1600.0, total_seconds=1500.0)
        rendered = str(io._toolbar(started=time.perf_counter())().value)
        assert "-" not in rendered

    def test_omits_the_interview_clock_before_the_runner_reports_progress(self):
        io = ConsoleIO()
        rendered = str(io._toolbar(started=time.perf_counter())().value)
        assert "interview" not in rendered


class TestTheIndicatorWhileTheModelThinks:
    """The countdown lives in the answer prompt, which does not exist during generation.

    Without an indicator the candidate meets a still terminal for however long the model
    takes - fifteen to thirty-five seconds - with no way to tell thinking from hung. That
    cost a sitting, so these tests hold the fix down, including the delegation that is easy
    to leave out and impossible to notice from a passing suite.
    """

    def test_it_shows_the_time_left_in_the_interview(self):
        assert "20:00" in waiting_message(elapsed_seconds=300.0, total_seconds=1500.0)

    def test_it_never_shows_a_negative_clock_when_the_interview_has_overrun(self):
        message = waiting_message(elapsed_seconds=1600.0, total_seconds=1500.0)
        assert "0:00" in message and "-0" not in message

    def test_the_console_opens_and_closes_it_without_raising(self):
        """rich suppresses the spinner outside a terminal, so this pins the plumbing
        rather than the paint: the context manager runs and yields."""
        ran = False
        with ConsoleIO().waiting(300.0, 1500.0):
            ran = True
        assert ran

    def test_the_frozen_opening_wrapper_delegates_rather_than_swallowing_it(self):
        """A wrapper that inherits the no-op default leaves a live run with no indicator
        at all, and every test still passes. This is that test."""
        seen = []

        class Inner(ConsoleIO):
            @contextmanager
            def waiting(self, elapsed_seconds, total_seconds):
                seen.append((elapsed_seconds, total_seconds))
                yield

        io = FrozenOpeningIO(inner=Inner(), opening_text="x", opening_seconds=1.0)
        with io.waiting(300.0, 1500.0):
            pass
        assert seen == [(300.0, 1500.0)]

    def test_the_capturing_wrapper_delegates_too(self, tmp_path):
        seen = []

        class Inner(ConsoleIO):
            @contextmanager
            def waiting(self, elapsed_seconds, total_seconds):
                seen.append((elapsed_seconds, total_seconds))
                yield

        io = CapturingOpeningIO(inner=Inner(), target=tmp_path / "o.md", iteration=0)
        with io.waiting(60.0, 1500.0):
            pass
        assert seen == [(60.0, 1500.0)]
