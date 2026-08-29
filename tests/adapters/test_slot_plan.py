"""The slot plan is frozen before any interview runs and is the denominator of the primary
metric. A malformed plan must fail loudly at load time, not silently distort every number
that follows."""

import pytest
import yaml

from solution.adapters.slot_plan import SlotPlanError, load_slot_plan

VALID = {
    "role": "Fullstack Developer",
    "source": "https://example.com/posting (retrieved 2026-08-29)",
    "frozen_at": "2026-08-29",
    "slots": [
        {"id": "backend", "name": "backend and API design", "kind": "cross_cutting", "rank": 2,
         "keywords": ["backend", "api", "endpoint"]},
        {"id": "frontend", "name": "frontend", "kind": "language_framework", "rank": 1,
         "keywords": ["frontend", "react", "ui"]},
    ],
    "excluded": [{"name": "observability", "reason": "does not fit the 25-minute budget"}],
}


def write(tmp_path, plan):
    path = tmp_path / "slots.yaml"
    path.write_text(yaml.safe_dump(plan), encoding="utf-8")
    return path


def test_loads_slots_in_relevance_order(tmp_path):
    plan = load_slot_plan(write(tmp_path, VALID))
    assert [s.id for s in plan.slots] == ["frontend", "backend"]


def test_exposes_the_coverage_denominator(tmp_path):
    assert load_slot_plan(write(tmp_path, VALID)).denominator == 2


def test_keeps_the_excluded_competencies_so_the_cut_is_documented(tmp_path):
    plan = load_slot_plan(write(tmp_path, VALID))
    assert plan.excluded[0]["name"] == "observability"


def test_collects_every_keyword_for_the_lexicon(tmp_path):
    plan = load_slot_plan(write(tmp_path, VALID))
    assert plan.keywords >= {"backend", "react", "endpoint"}


def test_rejects_duplicate_slot_ids(tmp_path):
    broken = {**VALID, "slots": [{**VALID["slots"][0], "rank": 1},
                                 {**VALID["slots"][0], "rank": 2}]}
    with pytest.raises(SlotPlanError, match="duplicate"):
        load_slot_plan(write(tmp_path, broken))


def test_rejects_ranks_that_are_not_one_through_n(tmp_path):
    broken = {**VALID, "slots": [{**VALID["slots"][0], "rank": 1},
                                 {**VALID["slots"][1], "rank": 3}]}
    with pytest.raises(SlotPlanError, match="rank"):
        load_slot_plan(write(tmp_path, broken))


def test_rejects_a_slot_with_no_keywords(tmp_path):
    broken = {**VALID, "slots": [{**VALID["slots"][0], "rank": 1, "keywords": []},
                                 {**VALID["slots"][1], "rank": 2}]}
    with pytest.raises(SlotPlanError, match="keywords"):
        load_slot_plan(write(tmp_path, broken))


def test_rejects_an_unrecognised_slot_kind(tmp_path):
    broken = {**VALID, "slots": [{**VALID["slots"][0], "rank": 1, "kind": "vibes"},
                                 {**VALID["slots"][1], "rank": 2}]}
    with pytest.raises(SlotPlanError, match="kind"):
        load_slot_plan(write(tmp_path, broken))


def test_rejects_a_plan_with_no_slots(tmp_path):
    with pytest.raises(SlotPlanError, match="at least one"):
        load_slot_plan(write(tmp_path, {**VALID, "slots": []}))
