"""The preflight decides what may be rebuilt silently and what must stop the run.

That line is the whole point of the module: rebuilding the redacted CV changes nothing
about the experiment, while re-freezing the slot plan changes what coverage is measured
over. These tests pin the line in place.
"""

import pymupdf
import yaml

from solution.adapters.cv_redaction import file_digest, recorded_source_digest
from solution.adapters.slot_plan import load_slot_plan
from solution.application.preflight import prepare

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


def write_cv(path, line="Alice Example  +55 11 98888-7777  alice@example.com  React and AWS"):
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), line)
    document.save(path)
    document.close()


def build_case(tmp_path, *, role_text="Fullstack role. React. AWS.", cv_line=None):
    """A consistent role and case: everything in step, nothing to report."""
    role_dir = tmp_path / "role"
    case_dir = tmp_path / "case"
    role_dir.mkdir()
    case_dir.mkdir()

    (role_dir / "role.txt").write_text(role_text, encoding="utf-8")
    plan = {**SLOTS, "provenance": {"role_sha256": file_digest(role_dir / "role.txt")}}
    (role_dir / "slots.yaml").write_text(yaml.safe_dump(plan), encoding="utf-8")

    if cv_line:
        write_cv(case_dir / "cv-original.pdf", cv_line)
    else:
        write_cv(case_dir / "cv-original.pdf")

    (case_dir / "opening-answer.md").write_text(
        "# opening\n\n```\nI am a software engineer.\n```\n", encoding="utf-8"
    )

    prepare(role_dir=role_dir, case_dir=case_dir)
    evidence = {
        "provenance": {
            "cv_source_sha256": file_digest(case_dir / "cv-original.pdf"),
            "slot_plan_fingerprint": load_slot_plan(role_dir / "slots.yaml").fingerprint,
        },
        "evidence": [{"slot_id": "frontend", "has_experience": False, "evidence_quote": ""}],
    }
    (case_dir / "resume-evidence.yaml").write_text(yaml.safe_dump(evidence), encoding="utf-8")
    return role_dir, case_dir


def test_a_consistent_case_reports_nothing(tmp_path):
    role_dir, case_dir = build_case(tmp_path)
    report = prepare(role_dir=role_dir, case_dir=case_dir)
    assert report.ok
    assert report.derived == ()


class TestTheRedactedCv:
    def test_is_rebuilt_when_it_is_missing(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        (case_dir / "cv.pdf").unlink()

        report = prepare(role_dir=role_dir, case_dir=case_dir)

        assert (case_dir / "cv.pdf").exists()
        assert any("cv.pdf rebuilt" in line for line in report.derived)

    def test_is_rebuilt_when_the_original_changes(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        before = recorded_source_digest(case_dir / "cv.pdf")
        write_cv(case_dir / "cv-original.pdf", "Bob Example  +55 11 90000-1111  bob@example.com")

        prepare(role_dir=role_dir, case_dir=case_dir)

        assert recorded_source_digest(case_dir / "cv.pdf") != before

    def test_removes_the_contact_details_it_finds(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        (case_dir / "cv.pdf").unlink()
        prepare(role_dir=role_dir, case_dir=case_dir)

        with pymupdf.open(case_dir / "cv.pdf") as document:
            text = "\n".join(page.get_text() for page in document)
        assert "alice@example.com" not in text
        assert "Alice Example" in text


class TestStaleResumeEvidence:
    def test_is_caught_when_the_cv_is_swapped(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        write_cv(case_dir / "cv-original.pdf", "Bob Example  +55 11 90000-1111  bob@example.com")

        report = prepare(role_dir=role_dir, case_dir=case_dir)

        assert not report.ok
        assert any("different CV" in problem.what for problem in report.problems)

    def test_is_caught_when_the_slot_plan_changes(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        plan = yaml.safe_load((role_dir / "slots.yaml").read_text(encoding="utf-8"))
        plan["slots"][0]["keywords"].append("angular")
        (role_dir / "slots.yaml").write_text(yaml.safe_dump(plan), encoding="utf-8")

        report = prepare(role_dir=role_dir, case_dir=case_dir)

        assert any("different slot plan" in problem.what for problem in report.problems)

    def test_is_the_one_thing_a_caller_may_rebuild_on_its_own(self, tmp_path):
        """Only evidence staleness is safely automatable, and only before a measurement."""
        role_dir, case_dir = build_case(tmp_path)
        write_cv(case_dir / "cv-original.pdf", "Bob Example  +55 11 90000-1111  bob@example.com")

        assert prepare(role_dir=role_dir, case_dir=case_dir).needs_evidence_refresh


class TestTheFrozenSlotPlan:
    def test_a_changed_role_stops_the_run(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        (role_dir / "role.txt").write_text("A completely different job.", encoding="utf-8")

        report = prepare(role_dir=role_dir, case_dir=case_dir)

        assert not report.ok
        assert any("different role.txt" in problem.what for problem in report.problems)

    def test_a_changed_role_is_never_rebuilt_automatically(self, tmp_path):
        """Re-extracting the plan moves the denominator of the primary metric."""
        role_dir, case_dir = build_case(tmp_path)
        (role_dir / "role.txt").write_text("A completely different job.", encoding="utf-8")

        assert not prepare(role_dir=role_dir, case_dir=case_dir).needs_evidence_refresh

    def test_a_missing_plan_stops_the_run(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        (role_dir / "slots.yaml").unlink()

        report = prepare(role_dir=role_dir, case_dir=case_dir)

        assert any("slots.yaml is missing" in problem.what for problem in report.problems)


class TestTheFrozenOpening:
    def test_a_measured_run_needs_one(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        (case_dir / "opening-answer.md").write_text("# no fenced block here\n", encoding="utf-8")

        report = prepare(role_dir=role_dir, case_dir=case_dir, require_frozen_opening=True)

        assert any("no frozen opening" in problem.what for problem in report.problems)

    def test_a_pilot_does_not(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        (case_dir / "opening-answer.md").write_text("# no fenced block here\n", encoding="utf-8")

        report = prepare(role_dir=role_dir, case_dir=case_dir, require_frozen_opening=False)

        assert report.ok


class TestMissingInputs:
    def test_a_missing_original_cv_stops_the_run(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        (case_dir / "cv-original.pdf").unlink()

        report = prepare(role_dir=role_dir, case_dir=case_dir)

        assert any("cv-original.pdf is missing" in problem.what for problem in report.problems)

    def test_missing_evidence_stops_the_run(self, tmp_path):
        role_dir, case_dir = build_case(tmp_path)
        (case_dir / "resume-evidence.yaml").unlink()

        report = prepare(role_dir=role_dir, case_dir=case_dir)

        assert any("resume-evidence.yaml is missing" in problem.what for problem in report.problems)
