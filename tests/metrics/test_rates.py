"""Carry-over is the tunneling measurement and grounding is its counterweight. Both are
set comparisons, so both are tested against the cases where they could quietly disagree
with what they claim to measure."""

from evals.metrics.rates import is_carry_over, is_grounded
from solution.domain.models import Slot, SlotKind

LEXICON = frozenset(
    {"react", "hooks", "aws", "cognito", "lambda", "dynamodb", "database", "query", "pix"}
)

DATA = Slot("data_layer", "the data layer", SlotKind.DATA_STORAGE,
            ("database", "sql", "schema", "query"), 4)


class TestCarryOver:
    def test_a_question_reaching_for_a_term_the_candidate_raised_is_drift(self):
        assert is_carry_over(
            "How do you manage state with React hooks?",
            slot=DATA,
            prior_answer_terms=frozenset({"react", "hooks"}),
            lexicon=LEXICON,
        )

    def test_a_term_belonging_to_the_open_slot_is_not_drift(self):
        """Overlap alone is not tunneling: asking about the slot is the job."""
        assert not is_carry_over(
            "Tell me about a slow database query you fixed?",
            slot=DATA,
            prior_answer_terms=frozenset({"database", "query"}),
            lexicon=LEXICON,
        )

    def test_a_term_the_candidate_never_raised_is_not_drift(self):
        """Reaching into the CV is grounding, not drift. Only the transcript carries over."""
        assert not is_carry_over(
            "Tell me about the DynamoDB event store?",
            slot=DATA,
            prior_answer_terms=frozenset({"react"}),
            lexicon=LEXICON,
        )

    def test_an_unlabelled_question_has_no_slot_to_excuse_the_carried_term(self):
        assert is_carry_over(
            "Tell me more about Pix?",
            slot=None,
            prior_answer_terms=frozenset({"pix"}),
            lexicon=LEXICON,
        )


class TestGrounding:
    RESUME = frozenset({"aws", "cognito", "lambda", "dynamodb", "pix", "database", "query"})

    def test_a_question_reaching_into_the_cv_is_grounded(self):
        assert is_grounded(
            "Tell me about a production problem with Cognito you owned?",
            slot=DATA,
            resume_terms=self.RESUME,
            prior_answer_terms=frozenset(),
            lexicon=LEXICON,
        )

    def test_a_generic_slot_question_is_not_grounded(self):
        """Only slot vocabulary: this question would be identical for every candidate."""
        assert not is_grounded(
            "Tell me about a time a database query was the bottleneck?",
            slot=DATA,
            resume_terms=self.RESUME,
            prior_answer_terms=frozenset(),
            lexicon=LEXICON,
        )

    def test_echoing_the_candidate_is_not_grounding(self):
        """Repeating what was just said is carry-over wearing grounding's clothes. The
        credit goes to an interviewer that read the CV, not one that echoes the answer."""
        assert not is_grounded(
            "Tell me more about the Lambda work?",
            slot=DATA,
            resume_terms=self.RESUME,
            prior_answer_terms=frozenset({"lambda"}),
            lexicon=LEXICON,
        )

    def test_a_term_absent_from_the_cv_is_not_grounding(self):
        assert not is_grounded(
            "What do you think of Kubernetes?",
            slot=DATA,
            resume_terms=self.RESUME,
            prior_answer_terms=frozenset(),
            lexicon=LEXICON | {"kubernetes"},
        )
