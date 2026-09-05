"""Freezing the controlled stimulus, at the moment it is spoken.

The opening answer is what every measured run replays verbatim. It has to come from the
candidate, once, and then never move - `PREREGISTRATION.md` section 1 fixes it and section
4 lists it changing between runs as invalidating the result.

**It is written automatically, and that is the stronger choice rather than the convenient
one.** An earlier design printed the typed answer and asked a person to paste it into this
file. That opened a gap between what was said under a 120-second clock and what ended up
frozen, and the gap is exactly where an answer gets quietly improved. Capturing it in code
means the frozen stimulus is character-for-character what was typed during the interview,
with no opportunity to polish it afterwards.

The file keeps its prose. Only the status block is rewritten and the answer appended, so
the document explaining what this artifact is survives the freezing of it.
"""

from __future__ import annotations

import re
from pathlib import Path

_STATUS_BLOCK = re.compile(r"^> \*\*STATUS:.*?(?=\n\n)", re.MULTILINE | re.DOTALL)
_FROZEN_BLOCK = re.compile(
    r"\n?---\n\n## The frozen opening answer\n.*?```\n(.*?)\n```\n", re.DOTALL
)

REOPENED_STATUS = """\
> **STATUS: not frozen.** A previous answer was discarded by
> `interview run --baseline --restart`; it is still readable in the session record of the
> run that captured it. The next baseline run captures a new one."""

FROZEN_STATUS = """\
> **STATUS: frozen.** Captured live during iteration 0 and written by
> `interview run --baseline`, character for character as it was typed. Never edited
> afterwards - editing it would make the runs incomparable, and the run refuses to
> start if its digest moves."""


def _mark_status(text: str, status: str) -> str:
    """Replace the file's status block, or add one if it has none.

    A file with no status block is not an error - a hand-made one, or a case created by
    copying, will not have grown the prose this repository's own file has. It still gets a
    status, so the state of the artifact is legible without reading the whole thing.
    """
    if not text.strip():
        return status
    if _STATUS_BLOCK.search(text):
        return _STATUS_BLOCK.sub(status, text, count=1)
    lines = text.rstrip("\n").split("\n")
    at = 1 if lines and lines[0].startswith("# ") else 0
    return "\n".join(lines[:at] + ["", status] + lines[at:])


def freeze(
    path: Path,
    answer: str,
    *,
    iteration: int,
    captured_at: str,
    replacing: bool = False,
) -> tuple[str, str | None]:
    """Write the answer as the file's only fenced block and mark the file frozen.

    Returns (text written, the answer it replaced or None).

    Without `replacing` a file that already holds a fenced block is refused rather than
    overwritten, because a second opening answer would silently become the stimulus for
    every run after it. With `replacing` - which only a deliberate restart passes - the old
    answer is swapped out **at this moment and not before**: a restart abandoned before an
    answer is given must leave the previous experiment exactly as it was.

    The replaced answer is not lost either way. The run that captured it wrote it into an
    append-only record under `evals/results/`, which is where `PREREGISTRATION.md` section 4
    requires it to stay.
    """
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    previous: str | None = None

    if "```" in text:
        if not replacing:
            raise ValueError(
                f"{path} already holds a fenced block; refusing to add a second opening "
                "answer. A deliberate restart replaces it."
            )
        previous = _existing_answer(text)
        text = _strip_frozen_block(text)

    body = _mark_status(text, FROZEN_STATUS)
    frozen = "\n".join(
        [
            body.rstrip("\n"),
            "",
            "---",
            "",
            f"## The frozen opening answer",
            "",
            f"Captured {captured_at}, during the iteration {iteration} interview. This is the "
            "text every",
            "measured run replays, and the runner reads it from the fenced block below.",
            "",
            "```",
            answer.strip(),
            "```",
            "",
        ]
    )
    path.write_text(frozen, encoding="utf-8")
    return frozen, previous


def _existing_answer(text: str) -> str | None:
    match = _FROZEN_BLOCK.search(text)
    return match.group(1) if match else None


def _strip_frozen_block(text: str) -> str:
    match = _FROZEN_BLOCK.search(text)
    if match is None:
        return text
    return text[: match.start()].rstrip("\n") + "\n"


def reopen(path: Path) -> str | None:
    """Strip the frozen answer without capturing a replacement.

    Returns the answer that was removed, or None if there was nothing frozen. Not used by
    the run - a restart replaces the answer at the moment the new one is given, so that an
    abandoned restart leaves the previous experiment intact. This exists for the case where
    someone genuinely wants the file emptied and no interview is about to happen.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    removed = _existing_answer(text)
    if removed is None:
        return None
    body = _mark_status(_strip_frozen_block(text).rstrip("\n"), REOPENED_STATUS)
    path.write_text(body + "\n", encoding="utf-8")
    return removed
