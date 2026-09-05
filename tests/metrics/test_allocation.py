"""Coverage says a competency was reached; allocation says what it cost the others.

The cases below are the ones where a count could quietly disagree with the sentence it is
supposed to support - a chain interrupted by a question nobody could label, a histogram
that forgets the competencies nothing reached, and the denominators that decide whether an
unresolved question flatters the interviewer or counts against it.
"""

import math

import pytest

from evals.metrics import allocation

FOUR_IN_A_ROW = ["a", "b", "b", "b", "b", "c"]


class TestLongestChain:
    def test_counts_consecutive_questions_on_one_competency(self):
        assert allocation.longest_chain(FOUR_IN_A_ROW) == 4

    def test_the_same_slot_returned_to_later_is_not_one_chain(self):
        """Coming back after a detour is not the failure - never leaving is."""
        assert allocation.longest_chain(["b", "a", "b", "a", "b"]) == 1

    def test_an_unresolved_question_breaks_the_chain(self):
        """An unlabelled question is not evidence the interviewer stayed on topic, so it
        must not be allowed to bridge two runs into one."""
        assert allocation.longest_chain(["b", "b", None, "b", "b"]) == 2

    def test_a_scheduled_interview_cannot_exceed_its_follow_up_ceiling(self):
        """One primary plus one follow-up per slot, which is what the scheduler allows."""
        assert allocation.longest_chain(["a", "a", "b", "b", "c", "c"]) == 2

    def test_no_questions_is_zero_rather_than_an_error(self):
        assert allocation.longest_chain([]) == 0

    def test_nothing_resolved_is_zero(self):
        assert allocation.longest_chain([None, None, None]) == 0


class TestHistogram:
    def test_counts_each_competency(self):
        assert allocation.slot_histogram(FOUR_IN_A_ROW) == {"a": 1, "b": 4, "c": 1}

    def test_unresolved_labels_are_left_out(self):
        assert allocation.slot_histogram(["a", None, "a"]) == {"a": 2}

    def test_a_competency_nothing_reached_is_absent_rather_than_zero(self):
        """The histogram reports what was asked. Which competencies were missed is
        coverage's job, and it already names them."""
        assert "d" not in allocation.slot_histogram(FOUR_IN_A_ROW)


class TestMaxSlotShare:
    def test_is_the_busiest_competencys_share_of_every_question_asked(self):
        assert allocation.max_slot_share(FOUR_IN_A_ROW) == pytest.approx(4 / 6)

    def test_unresolved_questions_stay_in_the_denominator(self):
        """They were asked and the candidate spent time on them. Dropping them would
        inflate every share here."""
        assert allocation.max_slot_share(["b", "b", None, None]) == 0.5

    def test_no_questions_is_zero(self):
        assert allocation.max_slot_share([]) == 0.0


class TestNormalisedEntropy:
    def test_one_question_per_competency_is_one(self):
        even = allocation.normalised_entropy(["a", "b", "c", "d", "e", "f"], 6)
        assert even == pytest.approx(1.0)

    def test_everything_on_one_competency_is_zero(self):
        assert allocation.normalised_entropy(["b", "b", "b", "b"], 6) == 0.0

    def test_that_zero_is_not_a_negative_zero(self):
        """-sum() of a single term yields -0.0, which renders as "-0.00" - a number that
        reads as broken, at exactly the most concentrated interview a run can produce."""
        assert math.copysign(1.0, allocation.normalised_entropy(["b"] * 4, 6)) == 1.0

    def test_a_chain_longer_than_the_plan_is_still_counted(self):
        """Nothing caps the chain: it is measured off the record, not chosen."""
        assert allocation.describe(["b"] * 12, 6)["longest_chain"] == 12

    def test_a_concentrated_interview_scores_below_an_even_one(self):
        even = allocation.normalised_entropy(["a", "b", "c", "d", "e", "f"], 6)
        lopsided = allocation.normalised_entropy(["a", "b", "b", "b", "b", "b"], 6)
        assert lopsided < even

    def test_the_scale_is_comparable_across_plans_of_different_sizes(self):
        """Normalising by log(denominator) is what makes a six-slot role and a ten-slot
        role read on the same axis - without it the bigger plan always looks better."""
        six = allocation.normalised_entropy(list("abcdef"), 6)
        ten = allocation.normalised_entropy(list("abcdefghij"), 10)
        assert six == pytest.approx(1.0) and ten == pytest.approx(1.0)

    def test_a_single_slot_plan_cannot_be_spread_and_reports_zero(self):
        """log(1) is 0 and would divide; there is also nothing to spread over."""
        assert allocation.normalised_entropy(["a", "a"], 1) == 0.0

    def test_matches_shannon_entropy_before_normalisation(self):
        """Guards the formula itself rather than its behaviour."""
        expected = math.log(2) / math.log(6)
        assert allocation.normalised_entropy(["a", "a", "b", "b"], 6) == pytest.approx(expected)


class TestDescribe:
    def test_reports_the_busiest_competency_by_name(self):
        result = allocation.describe(FOUR_IN_A_ROW, 6)
        assert result["most_asked_slot"] == "b"
        assert result["longest_chain"] == 4
        assert result["questions"] == 6
        assert result["unresolved"] == 0

    def test_counts_unresolved_questions_separately(self):
        result = allocation.describe(["a", None, None], 6)
        assert result["questions"] == 3
        assert result["unresolved"] == 2

    def test_an_empty_session_describes_itself_without_raising(self):
        result = allocation.describe([], 6)
        assert result["most_asked_slot"] is None
        assert result["longest_chain"] == 0
        assert result["max_slot_share"] == 0.0


class TestRender:
    def test_puts_the_chain_beside_the_ceiling_the_schedule_allows(self):
        """A chain of 4 means nothing alone and a great deal beside a ceiling of 2."""
        lines = allocation.render(allocation.describe(FOUR_IN_A_ROW, 6), ceiling=2)
        assert any("4 consecutive" in line and "allows 2" in line for line in lines)

    def test_omits_the_ceiling_when_the_iteration_guarantees_none(self):
        lines = allocation.render(allocation.describe(FOUR_IN_A_ROW, 6))
        assert not any("allows" in line for line in lines)
