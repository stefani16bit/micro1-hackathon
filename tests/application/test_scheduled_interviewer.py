"""The rung that makes topic selection code rather than conversation.

The two properties worth holding down here are the ones a prompt cannot promise: the slot
comes from the schedule whatever the candidate says, and a candidate cannot hold the
interview on one topic by asking to have the question repeated.
"""

import pytest

from solution.application.interviewers.scheduled import ScheduledInterviewer
from solution.domain.models import ResumeEvidence, Slot, SlotKind, TimeBudget
from solution.domain.transcript import Answer, Transcript, Utterance

SLOTS = (
    Slot("frontend", "frontend development", SlotKind.LANGUAGE_FRAMEWORK,
         ("frontend", "react", "component"), 1),
    Slot("backend", "backend development", SlotKind.LANGUAGE_FRAMEWORK,
         ("backend", "node.js", "express"), 2),
    Slot("data_layer", "the data layer", SlotKind.DATA_STORAGE,
         ("database", "sql", "schema"), 3),
)

EVIDENCE = {
    "frontend": ResumeEvidence("frontend", True, "Built dashboards in React"),
    "backend": ResumeEvidence("backend", True, "Maintained services in Node.js"),
    "data_layer": ResumeEvidence("data_layer", False, None),
}


class Reply:
    def __init__(self, text):
        self.payload = {"question": text}


class Stub:
    """Returns scripted questions, and records what it was asked for."""

    name, model = "stub", "stub"

    def __init__(self, *texts):
        self._texts = list(texts) or ["Tell me about a thing you built?"]
        self.calls = []

    def complete_json(self, request, **_):
        self.calls.append(request)
        text = self._texts[min(len(self.calls) - 1, len(self._texts) - 1)]
        return Reply(text)


class Plan:
    slots = SLOTS
    denominator = len(SLOTS)
    keywords = frozenset(k for s in SLOTS for k in s.keywords)


def interviewer(provider, *, gated=False, sees_transcript=False, budget=None):
    return ScheduledInterviewer(
        provider=provider,
        plan=Plan(),
        evidence=EVIDENCE,
        budget=budget or TimeBudget(total_seconds=1500),
        iteration=3,
        sees_transcript=sees_transcript,
        gated=gated,
    )


def opened() -> Transcript:
    """A transcript past the opening turn."""
    t = Transcript().with_question(Utterance("Tell me about yourself.", "opening"), 2.0)
    return t.with_answer(Answer("I work on payments.", 60.0))


class TestTheScheduleOwnsTheTopic:
    def test_the_first_question_is_the_highest_ranked_slot(self):
        u = interviewer(Stub()).next_utterance(opened())
        assert u.slot_id == "frontend"

    def test_the_answer_does_not_change_which_slot_comes_next(self):
        """The whole anti-tunneling property, as a test: the candidate talks about
        databases and the schedule still moves to the slot it was going to."""
        base = opened()
        base = base.with_question(Utterance("A frontend question?", "primary", "frontend"), 2.0)

        about_databases = base.with_answer(
            Answer("Actually most of my work is SQL and schema design.", 60.0)
        )
        about_anything = base.with_answer(Answer("Sure, I built a dashboard.", 60.0))

        assert (
            interviewer(Stub()).next_utterance(about_databases).slot_id
            == interviewer(Stub()).next_utterance(about_anything).slot_id
        )

    def test_a_slot_without_cv_evidence_is_asked_situationally(self):
        stub = Stub()
        t = opened()
        for slot in ("frontend", "backend"):
            t = t.with_question(Utterance("q?", "primary", slot), 2.0)
            t = t.with_answer(Answer("an answer", 60.0))
            t = t.with_question(Utterance("q?", "follow_up", slot), 2.0)
            t = t.with_answer(Answer("an answer", 60.0))
        interviewer(stub).next_utterance(t)
        assert "no" in stub.calls[-1].prompt.lower().split("done this work:")[1][:10]

    def test_the_transcript_is_withheld_when_context_is_isolated(self):
        stub = Stub()
        interviewer(stub, sees_transcript=False).next_utterance(opened())
        assert "I work on payments" not in stub.calls[0].prompt

    def test_the_transcript_is_supplied_at_the_rung_that_still_sees_it(self):
        stub = Stub()
        interviewer(stub, sees_transcript=True).next_utterance(opened())
        assert "I work on payments" in stub.calls[0].prompt


class TestClarification:
    def _asked(self) -> Transcript:
        t = opened()
        t = t.with_question(
            Utterance("Tell me about a React dashboard you built?", "primary", "frontend"), 2.0
        )
        return t

    def test_a_request_to_repeat_gets_the_question_restated(self):
        t = self._asked().with_answer(Answer("Sorry, what do you mean?", 10.0))
        u = interviewer(Stub("Which dashboard did you build?")).next_utterance(t)
        assert u.kind == "clarification"
        assert u.slot_id == "frontend"

    def test_clarifying_does_not_advance_the_schedule(self):
        """The candidate has not had the question yet, so the slot cannot be spent."""
        t = self._asked().with_answer(Answer("Sorry, what do you mean?", 10.0))
        assert interviewer(Stub("Which one?")).next_utterance(t).slot_id == "frontend"

    def test_a_second_request_moves_the_interview_on(self):
        """One clarification per question. An interview that can be held on one topic by
        repeating 'what do you mean' has this project's failure from the other side."""
        t = self._asked().with_answer(Answer("Sorry, what do you mean?", 10.0))
        t = t.with_question(Utterance("Which dashboard?", "clarification", "frontend"), 2.0)
        t = t.with_answer(Answer("I still don't understand", 10.0))

        u = interviewer(Stub("A backend question?")).next_utterance(t)
        assert u.slot_id == "backend"
        assert u.kind == "primary"

    def test_moving_on_says_so_rather_than_ignoring_the_question(self):
        t = self._asked().with_answer(Answer("what do you mean?", 10.0))
        t = t.with_question(Utterance("Which dashboard?", "clarification", "frontend"), 2.0)
        t = t.with_answer(Answer("still not following", 10.0))

        text = interviewer(Stub("A backend question?")).next_utterance(t).text
        assert "frontend development" in text and "move us" in text

    def test_a_clarification_does_not_spend_the_slots_follow_up(self):
        """It repeats a question rather than asking a new one, so the budget it would
        otherwise consume is the interviewer's fault to absorb."""
        t = self._asked().with_answer(Answer("what do you mean?", 10.0))
        t = t.with_question(Utterance("Which dashboard?", "clarification", "frontend"), 2.0)
        t = t.with_answer(Answer("I built an operations portal.", 60.0))

        u = interviewer(Stub("Anything more on it?")).next_utterance(t)
        assert (u.slot_id, u.kind) == ("frontend", "follow_up")


class TestTheGate:
    def test_a_question_carrying_the_answer_forward_is_regenerated(self):
        t = opened().with_question(
            Utterance("A frontend question?", "primary", "frontend"), 2.0
        )
        t = t.with_answer(Answer("I used Express on the server.", 60.0))
        stub = Stub(
            "How did Express shape the backend you built?",
            "What was the hardest React component you built?",
        )
        u = interviewer(stub, gated=True).next_utterance(t)
        assert len(stub.calls) == 2
        assert u.text == "What was the hardest React component you built?"

    def test_two_rejections_fall_back_to_the_template(self):
        t = opened().with_question(
            Utterance("A frontend question?", "primary", "frontend"), 2.0
        )
        t = t.with_answer(Answer("I used Express on the server.", 60.0))
        stub = Stub("How did Express shape the backend?")
        u = interviewer(stub, gated=True).next_utterance(t)
        assert len(stub.calls) == 2
        assert "frontend development" in u.text

    def test_an_ungated_rung_ships_what_the_model_wrote(self):
        t = opened().with_question(
            Utterance("A frontend question?", "primary", "frontend"), 2.0
        )
        t = t.with_answer(Answer("I used Express on the server.", 60.0))
        stub = Stub("How did Express shape the backend?")
        u = interviewer(stub, gated=False).next_utterance(t)
        assert len(stub.calls) == 1
        assert u.text == "How did Express shape the backend?"


class TestTheCeilingIsInTheCode:
    def test_no_slot_can_exceed_one_primary_and_one_follow_up(self):
        """`longest_chain` is compared against this number, so it has to be a property of
        the schedule rather than of a run that happened to behave."""
        t = opened()
        seen = []
        for _ in range(12):
            u = interviewer(Stub()).next_utterance(t)
            if u is None:
                break
            seen.append(u.slot_id)
            t = t.with_question(Utterance(u.text, u.kind, u.slot_id), 2.0)
            t = t.with_answer(Answer("an answer", 60.0))

        for slot in {s for s in seen if s}:
            assert seen.count(slot) <= 2


@pytest.mark.parametrize("iteration,transcript,gated", [(1, True, False), (2, False, False),
                                                        (3, False, True)])
def test_each_rung_switches_on_exactly_what_the_ladder_says(iteration, transcript, gated):
    """The claim in PREREGISTRATION.md 3e is that the rungs differ by one mechanism each."""
    from solution.adapters.cli import RUNGS

    assert RUNGS[iteration] == {"sees_transcript": transcript, "gated": gated}


class TestAFollowUpFollowsSomethingUp:
    """The defect this fixes: a follow-up was generated from the same prompt as a primary,
    so the model never knew it was deepening and wrote a second standalone question."""

    def after_a_primary(self) -> Transcript:
        t = opened()
        t = t.with_question(Utterance("Tell me about React?", "primary", "frontend"), 2.0)
        return t.with_answer(Answer("I built the dashboard in React with TypeScript.", 60.0))

    def test_a_primary_is_told_nothing_the_candidate_said(self):
        stub = Stub()
        interviewer(stub).next_utterance(opened())
        assert "THIS IS A FOLLOW-UP" not in stub.calls[0].prompt
        assert "I work on payments" not in stub.calls[0].prompt

    def test_a_follow_up_is_given_the_answer_it_is_following_up_on(self):
        stub = Stub()
        u = interviewer(stub).next_utterance(self.after_a_primary())
        assert u.kind == "follow_up" and u.slot_id == "frontend"
        assert "THIS IS A FOLLOW-UP" in stub.calls[0].prompt
        assert "I built the dashboard in React with TypeScript." in stub.calls[0].prompt

    def test_a_follow_up_is_given_that_answer_and_no_other(self):
        """It stays inside the slot the schedule chose; the rest of the transcript is
        still withheld, so this cannot move the interview anywhere."""
        stub = Stub()
        interviewer(stub).next_utterance(self.after_a_primary())
        assert "I work on payments" not in stub.calls[0].prompt

    def test_the_gate_lets_a_follow_up_pick_up_the_words_it_is_following(self):
        """A deepening question that names TypeScript is carry-over by the letter of the
        rule - the candidate raised it and it is not a frontend keyword. This is the one
        place echoing the candidate is the entire point, so the gate is widened by exactly
        the terms in the answer being followed up on."""
        deepening = "What made TypeScript the right call for that React dashboard?"
        u = interviewer(Stub(deepening), gated=True).next_utterance(self.after_a_primary())
        assert u.text == deepening

    def test_the_same_words_in_a_primary_are_still_drift(self):
        """The widening is bounded to the follow-up. A primary about another competency
        that reached for TypeScript is exactly the tunneling the gate exists to stop."""
        t = opened().with_answer(Answer("I used TypeScript everywhere.", 60.0))
        stub = Stub("How did TypeScript shape your React components?")
        u = interviewer(stub, gated=True).next_utterance(t)
        assert u.kind == "primary"
        assert len(stub.calls) == 2


class TestComposingAheadOfTheAnswer:
    def test_only_an_isolated_rung_may_compose_ahead(self):
        """Composing ahead is sound because the question cannot depend on the answer, and
        that is true exactly when the transcript is withheld."""
        assert interviewer(Stub(), sees_transcript=True).may_compose_ahead is False
        assert interviewer(Stub(), sees_transcript=False).may_compose_ahead is True

    def test_a_question_composed_ahead_is_used_without_a_second_model_call(self):
        stub = Stub("Tell me about the React dashboard?")
        subject = interviewer(stub)
        subject.compose_ahead(opened())
        subject._collect_ahead()
        assert len(stub.calls) == 1

        u = subject.next_utterance(opened())
        assert u.text == "Tell me about the React dashboard?"
        assert len(stub.calls) == 1

    def test_a_speculation_the_schedule_no_longer_wants_is_discarded(self):
        """It speculated the next primary; by the turn boundary the schedule wants a
        follow-up on the slot already open, so the composed question is thrown away."""
        stub = Stub("A question about the frontend?")
        subject = interviewer(stub)
        subject.compose_ahead(opened())
        subject._collect_ahead()

        t = opened()
        t = t.with_question(Utterance("Tell me about React?", "primary", "frontend"), 2.0)
        t = t.with_answer(Answer("I built a dashboard.", 60.0))
        u = subject.next_utterance(t)

        assert u.kind == "follow_up"
        assert len(stub.calls) == 2
