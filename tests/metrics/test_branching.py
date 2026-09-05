"""Sampling the next question k times measures the interviewer, or it measures the seed.

Which of those it measures is the whole validity of the thing, so the guard against a
pinned provider is tested first and hardest. The rest covers the two ways the replay could
lie: a transcript rebuilt into a conversation that never happened, and a decision point
counted where the interviewer never actually chose.
"""

import json
import time

import pytest

from evals.metrics import branching
from solution.adapters.session_store import SessionStore
from solution.domain.models import Slot, SlotKind
from solution.domain.transcript import Transcript, Utterance
from solution.application.runner import Interviewer

SLOTS = (
    Slot("frontend", "frontend development", SlotKind.LANGUAGE_FRAMEWORK,
         ("react", "component"), 1),
    Slot("data_layer", "the data layer", SlotKind.DATA_STORAGE, ("sql", "schema"), 2),
)


class Plan:
    """Only what branching reads off a slot plan."""

    slots = SLOTS
    denominator = len(SLOTS)


class Scripted(Interviewer):
    """Returns the next line of a script each time it is asked, then stops."""

    def __init__(self, lines):
        self._lines = list(lines)
        self._at = 0

    def next_utterance(self, transcript: Transcript):
        if self._at >= len(self._lines):
            return None
        line = self._lines[self._at]
        self._at += 1
        return None if line is None else Utterance(text=line, kind="question")


def record(tmp_path, turns):
    """A session record shaped the way the runner leaves one."""
    path = tmp_path / "session-x.jsonl"
    events = [("run_metadata", {"iteration": 0})]
    for question, answer in turns:
        events.append(("question_asked",
                       {"kind": "question", "text": question, "generation_seconds": 2.0}))
        events.append(("answer_received", {"text": answer, "seconds_used": 60.0}))
    with path.open("w", encoding="utf-8") as fh:
        for i, (t, d) in enumerate(events, 1):
            fh.write(json.dumps({"seq": i, "ts": time.time(), "type": t, "data": d}) + "\n")
    return SessionStore(path).events()


class Reply:
    def __init__(self, slot_id):
        self.payload = {"slot_id": slot_id, "confidence": "high"}


class StubJudge:
    """Stands in for the blind judge, which is now the only labeller there is.

    Keyed off the prompt text, because that is all `judge_question` sends it - so this
    exercises the real call path rather than monkeypatching around it. It reads only the
    section after "QUESTION": the prompt also lists every competency with its keywords, so
    matching against the whole thing would find "react" and "schema" in all of them.
    """

    name, model = "stub", "stub"

    def complete_json(self, request, **_):
        prompt = request.prompt.lower().rpartition("question")[2]
        if "react" in prompt:
            return Reply("frontend")
        if "schema" in prompt:
            return Reply("data_layer")
        return Reply("none")


class Pinned:
    name, model = "ollama", "gemma4:12b"
    seed, temperature = 42, 0.0


class ZeroTemperature:
    name, model = "ollama", "gemma4:12b"
    seed, temperature = None, 0.0


class Sampling:
    name, model = "claude_cli", "claude-sonnet-4-5-20250929"


class TestTheSamplingGuard:
    def test_a_fixed_seed_is_refused(self):
        with pytest.raises(branching.NotSampling, match="seed=42"):
            branching.guard_sampling_provider(Pinned())

    def test_zero_temperature_is_refused_even_without_a_seed(self):
        """k identical answers would read as a perfectly consistent interviewer."""
        with pytest.raises(branching.NotSampling, match="temperature"):
            branching.guard_sampling_provider(ZeroTemperature())

    def test_the_refusal_says_recording_the_change_is_part_of_the_fix(self):
        with pytest.raises(branching.NotSampling, match="CHANGELOG"):
            branching.guard_sampling_provider(Pinned())

    def test_a_provider_that_samples_is_allowed(self):
        assert branching.guard_sampling_provider(Sampling()) is None

    def test_the_check_is_by_attribute_so_a_new_adapter_is_caught(self):
        """Named providers would have to be enumerated here and would drift."""
        class FutureAdapter:
            name, model, seed, temperature = "future", "v1", 7, 0.9

        with pytest.raises(branching.NotSampling):
            branching.guard_sampling_provider(FutureAdapter())


class TestRebuildingTheTranscript:
    def test_replays_what_was_actually_said_in_order(self, tmp_path):
        events = record(tmp_path, [("Q1?", "A1"), ("Q2?", "A2")])
        rebuilt = branching.transcript_from_record(events)
        assert [e.text for e in rebuilt.entries] == ["Q1?", "A1", "Q2?", "A2"]

    def test_keeps_the_durations_the_record_holds(self, tmp_path):
        events = record(tmp_path, [("Q1?", "A1")])
        rebuilt = branching.transcript_from_record(events)
        assert rebuilt.elapsed_seconds == pytest.approx(62.0)

    def test_ignores_events_that_are_not_turns(self, tmp_path):
        """A record carries metadata, gate decisions and model calls too."""
        events = record(tmp_path, [("Q1?", "A1")])
        assert len(branching.transcript_from_record(events).entries) == 2


class TestDecisionPoints:
    def test_one_per_answer(self, tmp_path):
        events = record(tmp_path, [("Q1?", "A1"), ("Q2?", "A2"), ("Q3?", "A3")])
        points = branching.decision_points(branching.transcript_from_record(events))
        assert len(points) == 3

    def test_each_prefix_ends_on_the_answer_it_continues_from(self, tmp_path):
        events = record(tmp_path, [("Q1?", "A1"), ("Q2?", "A2")])
        points = branching.decision_points(branching.transcript_from_record(events))
        assert [p.entries[-1].text for p in points] == ["A1", "A2"]

    def test_prefixes_grow_rather_than_repeat(self, tmp_path):
        events = record(tmp_path, [("Q1?", "A1"), ("Q2?", "A2")])
        points = branching.decision_points(branching.transcript_from_record(events))
        assert len(points[0].entries) == 2 and len(points[1].entries) == 4

    def test_an_empty_record_has_nowhere_to_branch(self):
        assert branching.decision_points(Transcript()) == []


class TestBranching:
    def test_an_interviewer_that_always_picks_one_competency_scores_one(self, tmp_path):
        events = record(tmp_path, [("Q1?", "A1")])
        result = branching.branch_session(
            events=events,
            plan=Plan(),
            build_interviewer=lambda: Scripted(["Tell me about a React component?"]),
            samples=3,
            judge_provider=StubJudge(),
        )
        assert result["mean_distinct_slots"] == 1.0
        assert result["fully_consistent_points"] == 1

    def test_an_interviewer_that_wanders_scores_above_one(self, tmp_path):
        events = record(tmp_path, [("Q1?", "A1")])
        lines = iter([
            "Tell me about a React component?",
            "How did you change the schema?",
            "Tell me about a React component?",
        ])

        result = branching.branch_session(
            events=events,
            plan=Plan(),
            build_interviewer=lambda: Scripted([next(lines)]),
            samples=3,
            judge_provider=StubJudge(),
        )
        assert result["mean_distinct_slots"] == 2.0
        assert result["max_distinct_slots"] == 2
        assert result["fully_consistent_points"] == 0

    def test_a_sample_where_the_interviewer_stops_is_recorded_not_dropped(self, tmp_path):
        """Stopping early is a different failure from drifting, and both are findings."""
        events = record(tmp_path, [("Q1?", "A1")])
        result = branching.branch_session(
            events=events,
            plan=Plan(),
            build_interviewer=lambda: Scripted([None]),
            samples=2,
        )
        samples = result["points"][0]["samples"]
        assert [s["resolved_by"] for s in samples] == ["finished", "finished"]

    def test_without_a_judge_the_unlabelled_are_reported_not_guessed(self, tmp_path):
        events = record(tmp_path, [("Q1?", "A1")])
        result = branching.branch_session(
            events=events,
            plan=Plan(),
            build_interviewer=lambda: Scripted(["What are you looking for in a role?"]),
            samples=2,
        )
        assert result["resolved_by"]["unresolved"] == 2
        assert result["points"][0]["distinct_slots"] == []

    def test_every_sample_lands_in_the_record_with_its_own_coordinates(self, tmp_path):
        """k calls share a prompt fingerprint, so the trace numbers them as attempts.
        These events are what say which decision point and which sample each one was."""
        events = record(tmp_path, [("Q1?", "A1"), ("Q2?", "A2")])
        store = SessionStore(tmp_path / "branch.jsonl")
        branching.branch_session(
            events=events,
            plan=Plan(),
            build_interviewer=lambda: Scripted(["Tell me about a React component?"]),
            samples=2,
            store=store,
        )
        written = [e for e in store.events() if e.type == "branch_sample"]
        assert len(written) == 4
        assert {(e.data["decision_point"], e.data["sample"]) for e in written} == {
            (1, 1), (1, 2), (2, 1), (2, 2)
        }
