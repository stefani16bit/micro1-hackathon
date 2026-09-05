"""Reading the frozen résumé evidence back off disk.

`ingest_resume.py` writes `resume-evidence.yaml`; `models.ResumeEvidence` describes one
entry; until now nothing read it back, because nothing used it. The scheduled interviewer
does: `has_experience` decides whether a slot is asked behaviourally or situationally, and
the quote is what makes the question about *this* candidate rather than about the role.

Resolved once, before turn 1, and never re-derived mid-interview - which is the point. A
candidate who talks confidently about AWS does not retroactively acquire frontend
experience, and a question type that could drift with the conversation would be one more
thing the transcript decides.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import yaml

from solution.domain.models import ResumeEvidence


class ResumeEvidenceError(ValueError):
    """The evidence file is not usable as the basis of an interview."""


def load_resume_evidence(path: Path | str) -> Mapping[str, ResumeEvidence]:
    """Every slot's evidence, keyed by slot id.

    Strict about shape for the same reason the slot plan loader is: a missing
    `has_experience` silently defaulting to False would ask a candidate to hypothesise
    about work they have actually done, which reads as the interviewer not having looked.
    """
    source = Path(path)
    if not source.exists():
        raise ResumeEvidenceError(f"{source} does not exist - run: interview prepare")

    document = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    entries = document.get("evidence")
    if not isinstance(entries, list) or not entries:
        raise ResumeEvidenceError(f"{source} holds no `evidence` list")

    resolved: dict[str, ResumeEvidence] = {}
    for entry in entries:
        slot_id = entry.get("slot_id")
        if not slot_id:
            raise ResumeEvidenceError(f"{source}: an entry has no slot_id")
        if "has_experience" not in entry:
            raise ResumeEvidenceError(f"{source}: {slot_id} has no has_experience")
        quote = (entry.get("evidence_quote") or "").strip()
        resolved[slot_id] = ResumeEvidence(
            slot_id=slot_id,
            has_experience=bool(entry["has_experience"]),
            quote=quote or None,
        )
    return resolved
