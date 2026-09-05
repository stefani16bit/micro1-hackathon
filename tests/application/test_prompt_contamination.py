"""What the interviewer knows, checked against the real files rather than a fixture.

The leak these guard against: `role.txt`'s comment header reaching the system prompt, which
would tell the model *"candidates who apply to it are screened by the AI interviewer this
project examines"*. An interviewer that knows it is the subject of a study is not the
interviewer the experiment is about, and nothing was watching for it before this file.

These tests assemble the prompt through `cli.assemble_prompt` — the same function the run
and `interview show-prompt` use — so what is checked is what is sent. A test that built the
prompt its own way could only prove something about its own way.
"""

import pytest

from solution.adapters.cli import ROOT, assemble_prompt

ROLE_DIR = ROOT / "roles" / "fullstack"
CASE_DIR = ROOT / "evals" / "cases" / "case-01"


@pytest.fixture(scope="module")
def prompts():
    return assemble_prompt(0, ROLE_DIR, CASE_DIR)


PROJECT_VOCABULARY = [
    "evaluation purposes",
    "this project examines",
    "the AI interviewer this project",
    "slot plan",
    "competencies coverage",
    "carry-over",
    "carry over",
    "the ladder",
    "iteration 0",
    "pre-registration",
    "preregistration",
    "experiment",
    "measured run",
    "baseline",
]


@pytest.mark.parametrize("phrase", PROJECT_VOCABULARY)
def test_the_system_prompt_never_mentions_the_project(prompts, phrase):
    system, _ = prompts
    assert phrase.lower() not in system.lower(), (
        f"{phrase!r} reached the interviewer. Run `interview show-prompt` to see the "
        "assembled prompt and find where it came from."
    )


class TestWhatTheModelDoesNotGet:
    def test_no_comment_header_from_role_txt(self, prompts):
        """The header is repository metadata. It stays in the file and out of the context."""
        system, _ = prompts
        assert "# SOURCE" not in system
        assert "jobs.micro1.ai/post" not in system
        assert "retrieved 2026-08-29" not in system

    def test_no_time_information_at_all(self, prompts):
        """Time-aware scheduling is what rung 1 adds. A baseline told the elapsed
        minutes every turn made that claim false and paced its own coverage against it."""
        system, user_template = prompts
        for text in (system, user_template):
            lowered = text.lower()
            assert "25 minutes" not in lowered
            assert "elapsed" not in lowered
            assert "pace yourself" not in lowered
            assert "time is up" not in lowered

    def test_no_competency_list(self, prompts):
        """The six slots are the denominator of the primary metric. A model that could see
        them would be told the answer to what is being measured.

        Checked against the *identifiers* rather than the words: `frontend` and `backend`
        are in any full-stack posting and their presence proves nothing, while
        `cross_boundary_debugging` and `api_contract` are this repository's coinages and
        could only arrive from `slots.yaml`.
        """
        from solution.adapters.slot_plan import load_slot_plan

        system, _ = prompts
        plan = load_slot_plan(ROLE_DIR / "slots.yaml")
        coined = [slot.id for slot in plan.slots if "_" in slot.id]
        assert coined, "expected at least one slot id that could not occur in prose"
        for slot_id in coined:
            assert slot_id not in system

    def test_no_trace_of_the_slot_plan_file(self, prompts):
        """Not the ids, not the structure it is written in."""
        system, _ = prompts
        for marker in ("slots:", "keywords:", "excluded:", "frozen_at", "slot_id"):
            assert marker not in system


class TestWhatTheModelDoesGet:
    """The other half. A prompt can be clean by being empty, which would be worse."""

    def test_the_posting_itself_survives_the_stripping(self, prompts):
        system, _ = prompts
        assert "Job Title: Full Stack Developer" in system
        for heading in (
            "## About the role",
            "## Scope of Work",
            "## Preferred Qualifications",
            "## Required Skills",
        ):
            assert heading in system

    def test_the_job_description_starts_at_the_posting(self, prompts):
        system, _ = prompts
        after = system[system.index("JOB DESCRIPTION") + len("JOB DESCRIPTION") :]
        assert after.lstrip().startswith("Job Title:")

    def test_the_candidates_cv_is_there(self, prompts):
        system, _ = prompts
        assert "CANDIDATE CV" in system
        assert "WORK EXPERIENCE" in system

    def test_the_transcript_placeholder_is_the_only_one_left(self, prompts):
        import re

        _, user_template = prompts
        assert re.findall(r"<<[A-Z_]+>>", user_template) == ["<<TRANSCRIPT>>"]
