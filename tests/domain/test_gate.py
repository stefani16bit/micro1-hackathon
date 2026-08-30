"""The gate is where the anti-tunneling promise is actually kept. The scenario in
test_rejects_a_question_that_carries_the_previous_answer_forward is the exact failure
that motivated this project."""

from solution.domain.gate import GateContext, Violation, check_clarification, check_question
from solution.domain.models import Slot, SlotKind

LEXICON = frozenset({"react", "hooks", "cloud", "aws", "terraform", "postgresql", "redis"})

CLOUD = Slot(
    id="cloud",
    name="cloud infrastructure",
    kind=SlotKind.INFRA_OPS,
    keywords=("cloud", "aws", "terraform"),
    rank=4,
)


def ctx(**kw) -> GateContext:
    base = dict(
        slot=CLOUD, lexicon=LEXICON, prior_answer_terms=frozenset(), expect_behavioural=True
    )
    return GateContext(**{**base, **kw})


def test_accepts_a_behavioural_question_about_the_open_slot():
    q = "Tell me about a production problem in AWS you were responsible for. What happened?"
    assert check_question(q, ctx()).passed


def test_rejects_a_question_that_names_no_part_of_the_open_slot():
    result = check_question("Tell me about a time you shipped something hard?", ctx())
    assert Violation.OFF_SLOT in result.violations


def test_rejects_a_question_that_carries_the_previous_answer_forward():
    """The candidate mentioned React hooks; the open slot is cloud infrastructure.
    A question that reaches for 'hooks' is the tunnel, and it must not reach the candidate."""
    result = check_question(
        "You mentioned hooks earlier - how do you manage state with React hooks in the cloud?",
        ctx(prior_answer_terms=frozenset({"react", "hooks"})),
    )
    assert Violation.CARRY_OVER in result.violations
    assert set(result.evidence["carry_over"]) == {"react", "hooks"}


def test_a_slot_keyword_the_candidate_happened_to_mention_is_not_carry_over():
    """Overlap alone is not drift: if the term belongs to the open slot, using it is correct."""
    result = check_question(
        "Tell me about a production problem in AWS you were responsible for?",
        ctx(prior_answer_terms=frozenset({"aws", "react"})),
    )
    assert Violation.CARRY_OVER not in result.violations


def test_rejects_more_than_one_question_in_a_turn():
    result = check_question(
        "Tell me about your AWS work? And what did you learn?", ctx()
    )
    assert Violation.FORM in result.violations


def test_rejects_situational_phrasing_when_the_candidate_has_the_experience():
    result = check_question(
        "How would you approach setting up cloud infrastructure you don't know?", ctx()
    )
    assert Violation.FORM in result.violations


def test_requires_situational_phrasing_when_the_candidate_lacks_the_experience():
    behavioural = "Tell me about a time you used cloud infrastructure to solve a problem?"
    result = check_question(behavioural, ctx(expect_behavioural=False))
    assert Violation.FORM in result.violations


def test_a_clarification_that_only_restates_the_question_passes():
    result = check_clarification(
        "Sure - I'm asking about cloud infrastructure you personally operated.",
        ctx(allowed_terms=frozenset({"cloud", "aws"})),
    )
    assert result.passed


def test_a_clarification_that_introduces_new_technical_content_is_a_leak():
    result = check_clarification(
        "For example, you could have used Terraform with Redis for the cache layer.",
        ctx(allowed_terms=frozenset({"cloud", "aws"})),
    )
    assert Violation.LEAKAGE in result.violations
    assert "redis" in result.evidence["leakage"]
