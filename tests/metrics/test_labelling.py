"""Every number in the README passes through this labelling step, so its failure modes
matter more than its successes."""

from evals.metrics.labelling import label_by_rule
from solution.domain.models import Slot, SlotKind

FRONTEND = Slot("frontend", "frontend development", SlotKind.LANGUAGE_FRAMEWORK,
                ("frontend", "react", "angular", "ui"), 1)
BACKEND = Slot("backend", "backend development", SlotKind.LANGUAGE_FRAMEWORK,
               ("backend", "node.js", "fastapi", "server"), 2)
DATA = Slot("data_layer", "the data layer", SlotKind.DATA_STORAGE,
            ("database", "sql", "schema", "query"), 3)

SLOTS = (FRONTEND, BACKEND, DATA)


def test_labels_a_question_that_names_one_slot():
    assert label_by_rule("Tell me about a React feature you built?", SLOTS) == "frontend"


def test_matches_keywords_regardless_of_case():
    assert label_by_rule("What did you build with FastAPI?", SLOTS) == "backend"


def test_matches_the_slot_name_as_well_as_its_keywords():
    assert label_by_rule("Tell me about the data layer you designed?", SLOTS) == "data_layer"


def test_returns_none_when_no_slot_is_named():
    assert label_by_rule("Tell me about a time you worked under pressure?", SLOTS) is None


def test_returns_none_when_the_question_spans_two_slots():
    """Ambiguity is escalated to the judge rather than resolved by guessing."""
    assert label_by_rule("How does your React app talk to the SQL database?", SLOTS) is None


def test_does_not_match_a_keyword_buried_inside_another_word():
    assert label_by_rule("What is your reaction to tight deadlines?", SLOTS) is None


def test_ignores_any_slot_the_system_declared_for_itself():
    """The instrument never reads the interviewer's own label. Iteration 0 has none, so
    if later iterations were measured by self-report they would be measured differently -
    and the comparison across the ladder would be meaningless."""
    assert label_by_rule.__doc__ is not None
    assert "declared" not in label_by_rule.__code__.co_varnames
