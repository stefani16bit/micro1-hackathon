"""The hard deadline is a rule the candidate specified, and it runs eleven times without
supervision. These tests drive the real prompt through a pipe so the behaviour is checked
deterministically rather than discovered mid-interview."""

import asyncio
import time

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from solution.adapters.candidate_io import ConsoleIO


def read(typed: str, deadline_seconds: int) -> tuple[str, bool]:
    io = ConsoleIO()
    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input, output=DummyOutput()):
            pipe_input.send_text(typed)
            return asyncio.run(io._read_with_deadline(deadline_seconds))


def test_submitting_before_the_deadline_returns_the_answer():
    text, was_cut = read("I built payment services.\r", deadline_seconds=30)
    assert text == "I built payment services."
    assert was_cut is False


def test_the_deadline_cuts_the_prompt_and_keeps_what_was_typed():
    """The rule: an unsubmitted answer does not stop the interview. What is written by
    then is the answer - losing it would punish the candidate for the clock."""
    text, was_cut = read("I was midway through explaining the", deadline_seconds=1)
    assert text == "I was midway through explaining the"
    assert was_cut is True


def test_an_empty_answer_at_the_deadline_is_recorded_as_empty_rather_than_lost():
    text, was_cut = read("", deadline_seconds=1)
    assert text == ""
    assert was_cut is True


class TestCountdown:
    def test_counts_down_towards_the_deadline(self):
        io = ConsoleIO()
        render = io._toolbar(started=0.0, deadline_seconds=120)
        assert "this answer" in str(render().value)

    def test_never_shows_a_negative_clock_now_that_the_deadline_is_enforced(self):
        io = ConsoleIO()
        render = io._toolbar(started=time.perf_counter() - 300, deadline_seconds=120)
        assert "-" not in str(render().value)

    def test_shows_the_remaining_interview_time_when_it_is_known(self):
        io = ConsoleIO()
        io.note_progress(elapsed_seconds=600.0, total_seconds=1500.0)
        render = io._toolbar(started=time.perf_counter(), deadline_seconds=120)
        assert "interview" in str(render().value)

    def test_omits_the_interview_clock_before_the_runner_reports_progress(self):
        io = ConsoleIO()
        rendered = str(io._toolbar(started=0.0, deadline_seconds=120)().value)
        assert "interview" not in rendered
