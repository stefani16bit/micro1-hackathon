"""The turn loop is shared by every iteration. Only the interviewer is swapped, so
every fairness property the comparison depends on is tested once, here."""

from solution.application.runner import CandidateIO, Interviewer, run_interview
from solution.domain.models import TimeBudget
from solution.domain.transcript import Answer, Transcript, Utterance

BUDGET = TimeBudget(total_seconds=300, expected_answer_seconds=120, turn_overhead_seconds=15)


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

    def present(self, text: str) -> None:
        self.presented.append(text)

    def collect(self) -> Answer:
        if self._queue:
            return self._queue.pop(0)
        if self._default is not None:
            return self._default
        return Answer(text="", seconds_used=0.0)


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


def test_asks_no_further_question_once_the_budget_is_spent(tmp_path, store_factory):
    """300 s of budget and 120 s answers: the third turn is never started."""
    outcome = run_interview(
        interviewer=ScriptedInterviewer(question(), repeat_last=True),
        io=ScriptedIO(default=Answer("...", 120.0)),
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert outcome.end_reason == "time_exhausted"
    assert len(outcome.transcript.questions) == 3
    assert outcome.transcript.elapsed_seconds >= BUDGET.total_seconds


def test_an_answer_already_under_way_may_run_past_the_budget(tmp_path, store_factory):
    """The check is at the turn boundary, so nothing is cut off mid-sentence. An interview
    that ends slightly over is a better artifact than one that truncates a candidate."""
    outcome = run_interview(
        interviewer=ScriptedInterviewer(question(), repeat_last=True),
        io=ScriptedIO(default=Answer("a very long answer", 400.0)),
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert outcome.transcript.answers[0].seconds == 400.0
    assert outcome.transcript.elapsed_seconds > BUDGET.total_seconds
    assert len(outcome.transcript.questions) == 1


def test_the_candidates_turn_is_never_limited(tmp_path, store_factory):
    """There is no argument by which the loop could impose one."""
    import inspect

    from solution.application.runner import CandidateIO as Port

    assert list(inspect.signature(Port.collect).parameters) == ["self"]


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
    assert outcome.transcript.elapsed_seconds == 100.0


class ComposingInterviewer(ScriptedInterviewer):
    """Records when the loop offered it the chance to compose ahead."""

    may_compose_ahead = True

    def __init__(self, *utterances):
        super().__init__(*utterances)
        self.composed_after: list[int] = []

    def compose_ahead(self, transcript: Transcript) -> None:
        self.composed_after.append(len(transcript.questions))


class FinishedInterviewer(Interviewer):
    label = "finished"

    def next_utterance(self, transcript: Transcript):
        return None

    def stopped_because(self) -> str:
        return "all_slots_covered"


def test_only_an_interviewer_that_may_compose_ahead_is_asked_to(tmp_path, store_factory):
    """The baseline is handed the transcript every turn, so its next question cannot
    exist before the answer does. The loop must not offer it the chance anyway."""
    plain = ScriptedInterviewer(question(), question())
    run_interview(
        interviewer=plain,
        io=ScriptedIO(default=Answer("...", 30.0)),
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert not hasattr(plain, "composed_after")
    assert plain.may_compose_ahead is False


def test_composing_ahead_happens_after_the_question_and_before_the_answer(
    tmp_path, store_factory
):
    interviewer = ComposingInterviewer(question("First?"), question("Second?"))
    run_interview(
        interviewer=interviewer,
        io=ScriptedIO(default=Answer("...", 30.0)),
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert interviewer.composed_after == [1, 2]


def test_the_record_says_whether_the_interviewer_composed_ahead(tmp_path, store_factory):
    """A run where the wait was hidden and one where it was paid are different runs."""
    store = store_factory(tmp_path)
    run_interview(
        interviewer=ComposingInterviewer(question()),
        io=ScriptedIO(Answer("An answer.", 45.0)),
        store=store,
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    started = next(e for e in store.events() if e.type == "interview_started")
    assert started.data["composes_ahead"] is True


def test_the_interviewer_says_why_it_stopped(tmp_path, store_factory):
    """The scheduler knows it ran out of time; the loop used to record every stop as
    `interviewer_finished` and throw that away."""
    outcome = run_interview(
        interviewer=FinishedInterviewer(),
        io=ScriptedIO(),
        store=store_factory(tmp_path),
        budget=BUDGET,
        clock=lambda: 0.0,
    )
    assert outcome.end_reason == "all_slots_covered"
