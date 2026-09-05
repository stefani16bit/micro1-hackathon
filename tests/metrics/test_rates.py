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


class TestStructuralVocabularyIsNotDrift:
    """The correction iteration 0 forced, with the cases that forced it.

    Measured over that run, carry-over was 100% on the strength of `backend`, `api`, `ui`
    and `request`, while five consecutive questions about one idempotency key went
    uncounted. Section 2 defines carry-over as a question reaching for "a TECHNOLOGY the
    candidate raised"; a layer is not a technology, and the implementation now says so.

    The second class below is the other half, and the one that matters more: a stoplist
    that quietly emptied the metric would be a worse failure than the one it fixed,
    because nothing would look wrong.
    """

    BOUNDARY = Slot(
        "cross_boundary_debugging",
        "debugging across the frontend and backend boundary",
        SlotKind.CROSS_CUTTING,
        ("debugging", "bug", "root cause"),
        5,
    )

    def test_naming_both_sides_of_the_boundary_is_not_drift(self):
        """The exact question the old instrument punished. This competency is *defined*
        as the frontend/backend boundary, so asking about it correctly requires both
        words - and neither is in its keyword list."""
        assert not is_carry_over(
            "Tell me about a bug where the frontend showed wrong data and you traced it "
            "through the API to the backend?",
            slot=self.BOUNDARY,
            prior_answer_terms=frozenset({"frontend", "backend", "api", "ui"}),
            lexicon=LEXICON | {"frontend", "backend", "api", "ui"},
        )

    def test_a_generic_request_is_not_a_technology_the_candidate_raised(self):
        assert not is_carry_over(
            "Where exactly did you generate the key when receiving the request?",
            slot=DATA,
            prior_answer_terms=frozenset({"request"}),
            lexicon=LEXICON | {"request"},
        )

    def test_react_query_no_longer_reads_as_reaching_into_the_data_layer(self):
        """`React Query` decomposes into `react` + `query`, and `query` belonged to the
        data layer - so two purely frontend questions registered as drift."""
        frontend = Slot(
            "frontend", "frontend development", SlotKind.LANGUAGE_FRAMEWORK,
            ("react", "component"), 1,
        )
        assert not is_carry_over(
            "How did you configure the retry count in React Query?",
            slot=frontend,
            prior_answer_terms=frozenset({"query"}),
            lexicon=LEXICON | {"query"},
        )


class TestTheStoplistDidNotEmptyTheMetric:
    def test_a_named_technology_the_candidate_raised_still_counts(self):
        assert is_carry_over(
            "Why did you choose DynamoDB for the idempotency record?",
            slot=DATA,
            prior_answer_terms=frozenset({"dynamodb"}),
            lexicon=LEXICON | {"dynamodb"},
        )

    def test_a_named_technology_from_the_cv_still_grounds(self):
        assert is_grounded(
            "Tell me about the Cognito work?",
            slot=DATA,
            resume_terms=frozenset({"cognito"}),
            prior_answer_terms=frozenset(),
            lexicon=LEXICON,
        )

    def test_no_named_technology_sits_on_the_stoplist(self):
        """The guard against over-stoplisting, checked against the committed file rather
        than against a copy of it that could drift."""
        from evals.metrics.rates import STRUCTURAL

        named = {
            "react", "angular", "vue", "django", "flask", "fastapi", "express",
            "node.js", "nest.js", "golang", "dynamodb", "sql", "schema", "migration",
            "database", "rest", "graphql", "redis", "kafka", "microservices",
        }
        assert not (STRUCTURAL & named)

    def test_the_stoplist_is_loaded_rather_than_empty(self):
        """An unreadable file would silently restore the broken behaviour."""
        from evals.metrics.rates import STRUCTURAL

        assert {"frontend", "backend", "api", "request", "ui"} <= STRUCTURAL
