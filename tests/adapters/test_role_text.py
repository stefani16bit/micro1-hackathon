"""The job description reaches the model without the repository's notes on it.

The header this strips would tell the interviewer it was the subject of a study. The
stripping is one function; these tests are about the two ways it could go wrong - taking
too little, and taking too much.
"""

from solution.adapters.role_text import read_role_text, strip_leading_comments

REAL = "roles/fullstack/role.txt"


class TestStripping:
    def test_removes_the_leading_comment_block(self):
        text = strip_leading_comments(
            "# SOURCE\n#   https://example.com\n# notes\n\nJob Title: Engineer\n"
        )
        assert text == "Job Title: Engineer"

    def test_keeps_markdown_headings_that_come_after_content(self):
        """`## About the role` also starts with '#'. Stopping at the first non-comment
        line is what tells the two apart."""
        text = strip_leading_comments(
            "# header\n\nJob Title: Engineer\n\n## About the role\n\nWe build things.\n"
        )
        assert "## About the role" in text
        assert text.startswith("Job Title:")

    def test_leaves_a_file_with_no_header_alone(self):
        assert strip_leading_comments("Job Title: Engineer\n") == "Job Title: Engineer"

    def test_removes_the_blank_lines_the_header_left_behind(self):
        assert strip_leading_comments("# a\n\n\n\nJob Title: X").startswith("Job Title:")

    def test_an_all_comment_file_becomes_empty_rather_than_raising(self):
        assert strip_leading_comments("# only\n# comments\n") == ""


class TestTheRealPosting:
    """Guards the actual file the interview runs against, not a fixture of it."""

    def test_the_header_is_gone(self):
        text = read_role_text(REAL)
        assert "# SOURCE" not in text
        assert "this project" not in text
        assert "evaluation purposes" not in text

    def test_the_posting_is_intact(self):
        text = read_role_text(REAL)
        assert text.startswith("Job Title: Full Stack Developer")
        for heading in (
            "## About the role",
            "## Scope of Work",
            "## Preferred Qualifications",
            "## Required Skills",
        ):
            assert heading in text

    def test_the_file_on_disk_still_carries_its_source_citation(self):
        """Stripped on the way out, never from the file: `slots.yaml` records the digest of
        `role.txt` as provenance and the preflight blocks if it moves. The citation is also
        what ground rule 9 asks for."""
        from pathlib import Path

        raw = Path(REAL).read_text(encoding="utf-8")
        assert raw.startswith("# SOURCE")
        assert "jobs.micro1.ai/post" in raw
