"""The lock is what turns PREREGISTRATION.md section 4 from a promise into a mechanism.

Every scenario the section names as invalidating is tested here, because a guardrail whose
failure mode is silence is worse than none: the run would proceed, the numbers would look
fine, and the comparison across the rungs would be quietly meaningless.
"""

import pymupdf
import yaml

from solution.adapters.session_store import SessionStore
from solution.adapters.slot_plan import load_slot_plan
from solution.application import experiment as exp

SETTINGS = {
    "total_seconds": 1500,
    "expected_answer_seconds": 120,
    "turn_overhead_seconds": 15,
    "max_slots": 6,
}

SLOTS = {
    "role": "fullstack",
    "source": "test",
    "frozen_at": "2026-08-30",
    "slots": [
        {"id": "frontend", "name": "frontend", "kind": "language_framework", "rank": 1,
         "keywords": ["react", "frontend"]},
        {"id": "cloud", "name": "cloud", "kind": "infra_ops", "rank": 2,
         "keywords": ["aws", "cloud"]},
    ],
}


def build(tmp_path, *, opening="I am a software engineer.", brief="facts by competency"):
    """A complete, coherent experiment: everything present and in step."""
    root = tmp_path
    role_dir = root / "roles" / "fullstack"
    case_dir = root / "evals" / "cases" / "case-01"
    role_dir.mkdir(parents=True)
    case_dir.mkdir(parents=True)

    (role_dir / "role.txt").write_text("A fullstack role. React. AWS.", encoding="utf-8")
    (role_dir / "slots.yaml").write_text(yaml.safe_dump(SLOTS), encoding="utf-8")

    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Alice Example  React and AWS")
    document.save(case_dir / "cv-original.pdf")
    document.close()

    (case_dir / "resume-evidence.yaml").write_text("evidence: []\n", encoding="utf-8")
    (case_dir / "opening-answer.md").write_text(
        f"# opening\n\nSome prose.\n\n```\n{opening}\n```\n", encoding="utf-8"
    )
    (case_dir / "response-brief.md").write_text(brief, encoding="utf-8")
    return root, role_dir, case_dir


def inputs_for(root, role_dir, case_dir, settings=None):
    return exp.compute_inputs(
        root=root,
        role_dir=role_dir,
        case_dir=case_dir,
        plan=load_slot_plan(role_dir / "slots.yaml"),
        settings=settings or SETTINGS,
    )


def lock_for(root, role_dir, case_dir, settings=None):
    return exp.build_lock(
        inputs_for(root, role_dir, case_dir, settings),
        exp.compute_tracked(case_dir=case_dir),
        commit="abc1234",
    )


class TestIdentity:
    def test_the_same_inputs_produce_the_same_lock_id(self, tmp_path):
        """Content-addressed, so re-freezing an unchanged experiment is idempotent."""
        root, role_dir, case_dir = build(tmp_path)
        assert inputs_for(root, role_dir, case_dir).lock_id == (
            inputs_for(root, role_dir, case_dir).lock_id
        )

    def test_changing_an_input_mints_a_new_id_on_its_own(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        before = inputs_for(root, role_dir, case_dir).lock_id
        (role_dir / "role.txt").write_text("A completely different job.", encoding="utf-8")
        assert inputs_for(root, role_dir, case_dir).lock_id != before

    def test_the_response_brief_does_not_change_the_id(self, tmp_path):
        """It is tracked, not locked: rule 1 of the brief allows it to grow."""
        root, role_dir, case_dir = build(tmp_path)
        before = inputs_for(root, role_dir, case_dir).lock_id
        (case_dir / "response-brief.md").write_text("grown by one fact", encoding="utf-8")
        assert inputs_for(root, role_dir, case_dir).lock_id == before

    def test_the_opening_is_hashed_from_the_block_not_the_file(self, tmp_path):
        """A typo in the surrounding prose is not a changed stimulus."""
        root, role_dir, case_dir = build(tmp_path)
        before = inputs_for(root, role_dir, case_dir).lock_id
        opening = case_dir / "opening-answer.md"
        opening.write_text(
            opening.read_text(encoding="utf-8").replace("Some prose.", "Some prose, edited."),
            encoding="utf-8",
        )
        assert inputs_for(root, role_dir, case_dir).lock_id == before

    def test_a_changed_opening_answer_does_change_the_id(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        before = inputs_for(root, role_dir, case_dir).lock_id
        root2, role2, case2 = build(tmp_path / "other", opening="Something else entirely.")
        assert inputs_for(root2, role2, case2).lock_id != before


class TestRoundTrip:
    def test_a_written_lock_reads_back_identically(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        path = tmp_path / "evals" / "experiment-lock.yaml"
        exp.write_lock(path, lock)

        restored = exp.load_lock(path)
        assert restored.lock_id == lock.lock_id
        assert restored.inputs.locked == lock.inputs.locked
        assert dict(restored.inputs.budget) == dict(lock.inputs.budget)
        assert dict(restored.tracked) == dict(lock.tracked)

    def test_an_absent_lock_is_none_rather_than_an_error(self, tmp_path):
        assert exp.load_lock(tmp_path / "nothing.yaml") is None

    def test_a_lock_over_a_missing_input_is_refused_as_incomplete(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        (case_dir / "opening-answer.md").write_text("# no fenced block\n", encoding="utf-8")
        current = inputs_for(root, role_dir, case_dir)
        assert not current.complete
        assert "opening answer" in current.missing


class TestDrift:
    """One test per item PREREGISTRATION.md section 4 lists as invalidating."""

    def test_no_drift_when_nothing_moved(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        assert exp.compare(lock, inputs_for(root, role_dir, case_dir)) == ()

    def test_a_swapped_cv_is_drift(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)

        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "Bob Different  Vue and GCP")
        document.save(case_dir / "cv-original.pdf")
        document.close()

        drifts = exp.compare(lock, inputs_for(root, role_dir, case_dir))
        assert [d.field for d in drifts] == ["cv_source_sha256"]

    def test_a_changed_slot_plan_is_drift(self, tmp_path):
        """The plan is the denominator of coverage - this is the one that matters most."""
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)

        plan = yaml.safe_load((role_dir / "slots.yaml").read_text(encoding="utf-8"))
        plan["slots"][0]["keywords"].append("angular")
        (role_dir / "slots.yaml").write_text(yaml.safe_dump(plan), encoding="utf-8")

        drifts = exp.compare(lock, inputs_for(root, role_dir, case_dir))
        assert [d.field for d in drifts] == ["slot_plan_fingerprint"]
        assert "denominator of coverage" in drifts[0].consequence

    def test_a_changed_role_is_drift(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        (role_dir / "role.txt").write_text("A completely different job.", encoding="utf-8")
        assert [d.field for d in exp.compare(lock, inputs_for(root, role_dir, case_dir))] == [
            "role_sha256"
        ]

    def test_a_changed_opening_answer_is_drift(self, tmp_path):
        """The controlled stimulus. If it moves, coverage cannot be attributed."""
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        (case_dir / "opening-answer.md").write_text(
            "# opening\n\n```\nA different opening entirely.\n```\n", encoding="utf-8"
        )
        drifts = exp.compare(lock, inputs_for(root, role_dir, case_dir))
        assert [d.field for d in drifts] == ["opening_answer_sha256"]
        assert "controlled stimulus" in drifts[0].consequence

    def test_a_changed_time_budget_is_drift(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        shortened = {**SETTINGS, "expected_answer_seconds": 90}
        drifts = exp.compare(lock, inputs_for(root, role_dir, case_dir, shortened))
        assert [d.field for d in drifts] == ["budget"]

    def test_pointing_at_a_different_case_is_drift(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        _, _, other_case = build(tmp_path / "second")
        current = exp.compute_inputs(
            root=root,
            role_dir=role_dir,
            case_dir=other_case,
            plan=load_slot_plan(role_dir / "slots.yaml"),
            settings=SETTINGS,
        )
        assert "case_path" in {d.field for d in exp.compare(lock, current)}

    def test_a_grown_response_brief_is_reported_but_never_blocks(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        (case_dir / "response-brief.md").write_text("one more fact", encoding="utf-8")

        assert exp.compare(lock, inputs_for(root, role_dir, case_dir)) == ()
        tracked = exp.compare_tracked(lock, exp.compute_tracked(case_dir=case_dir))
        assert [d.field for d in tracked] == ["response_brief_sha256"]


class TestTheDriftReport:
    def test_lists_every_locked_input_not_only_the_changed_one(self, tmp_path):
        """A table with one row reads as the only thing that was checked."""
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        (role_dir / "role.txt").write_text("Different.", encoding="utf-8")
        current = inputs_for(root, role_dir, case_dir)

        rendered = exp.render_drift(lock, exp.compare(lock, current), ["iteration-00"], current)

        for label in exp.LOCKED_LABELS.values():
            assert label in rendered
        assert rendered.count("CHANGED") == 1
        assert "ok" in rendered

    def test_names_the_measured_runs_that_already_depend_on_the_lock(self, tmp_path):
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        (role_dir / "role.txt").write_text("Different.", encoding="utf-8")
        current = inputs_for(root, role_dir, case_dir)

        rendered = exp.render_drift(
            lock, exp.compare(lock, current), ["iteration-00", "iteration-01"], current
        )
        assert "iteration-00, iteration-01" in rendered
        assert lock.lock_id in rendered
        assert "interview run --baseline --restart" in rendered

    def test_says_the_abandoned_results_stay_reported(self, tmp_path):
        """Section 4 also forbids selective reporting, so the fix must not suggest deleting."""
        root, role_dir, case_dir = build(tmp_path)
        lock = lock_for(root, role_dir, case_dir)
        (role_dir / "role.txt").write_text("Different.", encoding="utf-8")
        current = inputs_for(root, role_dir, case_dir)

        rendered = exp.render_drift(lock, exp.compare(lock, current), [], current)
        assert "not" in rendered and "deleted" in rendered


class TestMeasuredRuns:
    def _write_session(self, results, bucket, lock_id):
        store = SessionStore(results / bucket / f"session-{bucket}.jsonl")
        store.append("run_metadata", iteration=0, experiment={"lock_id": lock_id})
        store.append("interview_ended", reason="all_slots_covered")

    def test_finds_runs_by_the_lock_they_recorded(self, tmp_path):
        results = tmp_path / "results"
        self._write_session(results, "iteration-00", "aaaaaaaaaaaa")
        self._write_session(results, "iteration-01", "aaaaaaaaaaaa")
        self._write_session(results, "iteration-02", "bbbbbbbbbbbb")

        assert exp.measured_runs_for("aaaaaaaaaaaa", results) == ("iteration-00", "iteration-01")

    def test_ignores_pilot_and_smoke_buckets(self, tmp_path):
        results = tmp_path / "results"
        self._write_session(results, "pilot", "aaaaaaaaaaaa")
        self._write_session(results, "smoke", "aaaaaaaaaaaa")
        assert exp.measured_runs_for("aaaaaaaaaaaa", results) == ()

    def test_an_interrupted_run_still_counts(self, tmp_path):
        """It consumed the candidate and it is in the record: the experiment is under way."""
        results = tmp_path / "results"
        store = SessionStore(results / "iteration-00" / "session-a.jsonl")
        store.append("run_metadata", iteration=0, experiment={"lock_id": "aaaaaaaaaaaa"})
        store.append("interview_ended", reason="interrupted_by_candidate")
        assert exp.measured_runs_for("aaaaaaaaaaaa", results) == ("iteration-00",)

    def test_finds_the_run_that_created_the_experiment(self, tmp_path):
        """The baseline that captures its own opening answer cannot stamp the lock into
        run_metadata - the lock does not exist yet - so it records it at the end instead.

        Reading only run_metadata made exactly the run that starts a ladder invisible to
        the guard protecting that ladder.
        """
        results = tmp_path / "results"
        store = SessionStore(results / "iteration-00" / "session-a.jsonl")
        store.append("run_metadata", iteration=0, experiment=None)
        store.append("opening_answer_frozen", characters=120)
        store.append("interview_ended", reason="time_exhausted")
        store.append("experiment_recorded", lock_id="aaaaaaaaaaaa", frozen_at="2026-08-31")

        assert exp.measured_runs_for("aaaaaaaaaaaa", results) == ("iteration-00",)

    def test_run_metadata_wins_when_both_carry_a_lock(self, tmp_path):
        results = tmp_path / "results"
        store = SessionStore(results / "iteration-01" / "session-a.jsonl")
        store.append("run_metadata", iteration=1, experiment={"lock_id": "aaaaaaaaaaaa"})
        store.append("experiment_recorded", lock_id="bbbbbbbbbbbb")

        assert exp.measured_runs_for("aaaaaaaaaaaa", results) == ("iteration-01",)

    def test_no_results_directory_is_simply_no_runs(self, tmp_path):
        assert exp.measured_runs_for("aaaaaaaaaaaa", tmp_path / "absent") == ()
