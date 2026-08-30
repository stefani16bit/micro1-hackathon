"""The turn loop is shared by all eleven iterations. Only the interviewer is swapped, so
every fairness property the comparison depends on is tested once, here."""

from solution.application.runner import CandidateIO, Interviewer, run_interview
from solution.domain.models import TimeBudget
from solution.domain.transcript import Answer, Transcript, Utterance

BUDGET = TimeBudget(total_seconds=300, answer_deadline_seconds=120, turn_overhead_seconds=15)


class ScriptedInterviewer(Interviewer):
    label = "scripted"

    def __init__(self, *utterances: Utterance | None, repeat_last: bool = False):
        self._queue = list(utterances)
        self._repeat_last = repeat_last

    def next_utterance(self, transcript: Transcript) -> Utterance | None:
        if not self._queue:
            return None
        if self._repeat_last and len(self._queue) == 1:
            return self._queue[0]
        return self._queue.pop(0)


class ScriptedIO(CandidateIO):
    def __init__(self, *answers: Answer, default: Answer | None = None):
        self._queue = list(answers)
        self._default = default
        self.presented: list[str] = []
        self.deadlines: list[int] = []

    def present(self, text: str) -> None:
        self.presented.append(text)

    def collect(self, deadline_seconds: int) -> Answer:
        self.deadlines.append(deadline_seconds)
        if self._queue:
            return self._queue.pop(0)
        if self._default is not None:
            return self._default
        return Answer(text="", seconds_used=0.0, over_deadline=True)


def question(text: str = "Tell me about your backend work?") -> Utterance:
    return Utterance(text=text, kind="primary", slot_id="backend")


def test_presents_each_question_and_records_the_answer(tmp_path, store_factory):
    io = ScriptedIO(Answer("I built payment services.", 60.0))
    outcome = run_interview(
        interviewer=ScriptedInterviewer(question()),
        io=io,
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert io.presented == ["Tell me about your backend work?"]
    assert [e.text for e in outcome.transcript.answers] == ["I built payment services."]


def test_stops_when_the_interviewer_has_nothing_left_to_ask(tmp_path, store_factory):
    outcome = run_interview(
        interviewer=ScriptedInterviewer(question(), None),
        io=ScriptedIO(Answer("Done.", 10.0)),
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert outcome.end_reason == "interviewer_finished"
    assert len(outcome.transcript.questions) == 1


def test_never_issues_a_turn_the_remaining_time_cannot_honour(tmp_path, store_factory):
    """300 s of budget at 135 s per turn leaves room for two, not three."""
    outcome = run_interview(
        interviewer=ScriptedInterviewer(question(), repeat_last=True),
        io=ScriptedIO(default=Answer("...", 120.0)),
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert outcome.end_reason == "time_exhausted"
    assert len(outcome.transcript.questions) == 2


def test_always_offers_the_full_answer_deadline(tmp_path, store_factory):
    """D6: the interview shortens when time runs short; the candidate's turn never does."""
    io = ScriptedIO(default=Answer("...", 120.0))
    run_interview(
        interviewer=ScriptedInterviewer(question(), repeat_last=True),
        io=io,
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert io.deadlines == [120, 120]


def test_a_timed_out_answer_does_not_end_the_interview(tmp_path, store_factory):
    outcome = run_interview(
        interviewer=ScriptedInterviewer(question("First?"), question("Second?")),
        io=ScriptedIO(Answer("", 120.0, over_deadline=True), Answer("Second answer.", 30.0)),
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert len(outcome.transcript.questions) == 2
    assert outcome.transcript.answers[0].over_deadline is True


def test_persists_every_turn_as_it_happens(tmp_path, store_factory):
    store = store_factory(tmp_path)
    run_interview(
        interviewer=ScriptedInterviewer(question()),
        io=ScriptedIO(Answer("An answer.", 45.0)),
        store=store,
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    kinds = [event.type for event in store.events()]
    assert kinds == ["interview_started", "question_asked", "answer_received", "interview_ended"]


def test_elapsed_time_counts_the_interviewer_thinking_as_well_as_the_answering(
    tmp_path, store_factory
):
    """A slow interviewer spends the candidate's budget, and the transcript says so."""
    ticks = iter([0.0, 20.0, 100.0, 120.0, 200.0, 200.0])
    outcome = run_interview(
        interviewer=ScriptedInterviewer(question("First?"), question("Second?")),
        io=ScriptedIO(default=Answer("...", 30.0)),
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: next(ticks),
    )
    # two questions costing 20 s of generation each, two answers of 30 s
    assert outcome.transcript.elapsed_seconds == 100.0
