"""Reading a job description out of `role.txt`, without the repository's notes on it.

The file starts with a comment header recording where the posting came from and why it is
in this repository. That header belongs here - ground rule 9 asks every claim to point at
its source, and the source of the evaluation role is exactly the kind of thing a reviewer
should be able to check. What it does not belong in is the interviewer's context.

Without this, the interviewer would read:

    # Reproduced for evaluation purposes with the source cited...
    # This posting is used as the evaluation role precisely because it is a real micro1
    # opening: candidates who apply to it are screened by the AI interviewer this project
    # examines.

which tells the model it is the subject of a study. An interviewer that knows it is being
examined is not the interviewer the experiment is about.

**Stripped on the way out, never from the file.** The digest of `role.txt` is recorded in
`slots.yaml` as provenance and in the experiment lock as a frozen input; editing the file
would move both and force the slot plan to be re-frozen. The header is repository metadata,
so the repository keeps it and the model does not see it.
"""

from __future__ import annotations

from pathlib import Path


def strip_leading_comments(text: str) -> str:
    """Drop the contiguous run of `#` lines at the top, and the blank lines after it.

    Only the leading run. The posting's own markdown headings - `## About the role`,
    `## Scope of Work`, `## Required Skills` - also begin with `#`, and they come after
    real content, so stopping at the first non-comment line leaves them alone.
    """
    lines = text.splitlines()
    start = 0
    while start < len(lines) and lines[start].lstrip().startswith("#"):
        start += 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    return "\n".join(lines[start:])


def read_role_text(path: Path | str) -> str:
    """The job description as the interviewer should see it: the posting, and nothing else."""
    return strip_leading_comments(Path(path).read_text(encoding="utf-8"))
