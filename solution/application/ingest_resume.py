"""Resolve, once and for all, what the CV says about each slot.

    python -m solution.application.ingest_resume evals/cases/case-01

Writes `resume-evidence.yaml`. This runs at session start and is frozen before turn 1,
which matters more than it looks: `has_experience` decides whether a slot gets a
behavioural or a situational question, and freezing it means the question type cannot
drift with the conversation. A candidate who talks confidently about AWS does not
retroactively acquire frontend experience.

Every evidence quote is checked against the CV text in code. A quote the model invented
is discarded and the slot is recorded as unevidenced, because a claim nobody verified is
not evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from solution.adapters.providers.base import LlmProvider, LlmRequest
from solution.adapters.slot_plan import SlotPlan
from solution.domain.quotes import quote_is_verbatim

SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot_id": {"type": "string"},
                    "has_experience": {"type": "boolean"},
                    "evidence_quote": {"type": "string"},
                },
                "required": ["slot_id", "has_experience", "evidence_quote"],
            },
        }
    },
    "required": ["matches"],
}

SYSTEM = """You decide what a CV evidences about each competency an interview will cover.

For every competency you are given, answer two things:

- has_experience: true only if the CV shows hands-on work with this competency. A
  technology listed in a skills section, with nothing in the work history that uses it,
  is NOT hands-on experience - that is a claim, not evidence. Set false in that case.
- evidence_quote: the exact sentence or clause from the CV that shows the experience,
  copied character for character. Do not paraphrase, do not summarise, do not join
  fragments from different places. If has_experience is false, return an empty string.

Being strict here helps the candidate. A competency marked false is not skipped in the
interview - it is asked as a hypothetical instead of as a past-experience question, which
is the fair way to ask about something someone has not done.

Reply with JSON only, no prose."""


def build_prompt(resume_text: str, plan: SlotPlan) -> str:
    lines = ["COMPETENCIES", ""]
    for slot in plan.slots:
        lines.append(f"- slot_id: {slot.id}")
        lines.append(f"  name: {slot.name}")
        lines.append(f"  keywords: {', '.join(slot.keywords)}")
    lines += ["", "CANDIDATE CV", "", resume_text]
    return "\n".join(lines)


def verify(
    matches: Sequence[Mapping[str, Any]], resume_text: str, plan: SlotPlan
) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep only evidence the CV actually contains; report what was discarded."""
    by_id = {match["slot_id"]: match for match in matches}
    verified: list[dict[str, Any]] = []
    discarded: list[str] = []

    for slot in plan.slots:
        match = by_id.get(slot.id)
        if match is None:
            verified.append(
                {"slot_id": slot.id, "has_experience": False, "evidence_quote": ""}
            )
            discarded.append(f"{slot.id}: the model returned no entry for this slot")
            continue

        quote = str(match.get("evidence_quote", "")).strip()
        claims_experience = bool(match.get("has_experience"))

        if claims_experience and not quote_is_verbatim(quote, resume_text):
            discarded.append(f"{slot.id}: quote is not verbatim in the CV -> {quote[:70]!r}")
            verified.append(
                {"slot_id": slot.id, "has_experience": False, "evidence_quote": ""}
            )
            continue

        verified.append(
            {
                "slot_id": slot.id,
                "has_experience": claims_experience,
                "evidence_quote": quote if claims_experience else "",
            }
        )

    return verified, discarded


def extract(resume_text: str, plan: SlotPlan, provider: LlmProvider) -> Sequence[Mapping[str, Any]]:
    request = LlmRequest(
        call="match_resume_to_slots",
        system=SYSTEM,
        prompt=build_prompt(resume_text, plan),
        schema=SCHEMA,
    )
    return provider.complete_json(request).payload["matches"]


def main(argv: Sequence[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    root = Path(__file__).resolve().parents[2]
    case_dir = root / argv[1]
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))

    from solution.adapters.providers import build_provider
    from solution.adapters.resume_pdf import read_resume_text
    from solution.adapters.slot_plan import load_slot_plan

    plan = load_slot_plan(root / config["role"] / "slots.yaml")
    resume_text = read_resume_text(case_dir / "cv.pdf")
    provider = build_provider(config)

    matches = extract(resume_text, plan, provider)
    verified, discarded = verify(matches, resume_text, plan)

    target = case_dir / "resume-evidence.yaml"
    target.write_text(
        "# Frozen before turn 1. has_experience decides behavioural vs situational\n"
        "# phrasing, so it must not move once the interview starts.\n"
        "# Every quote below was checked against the CV text in code.\n"
        + yaml.safe_dump({"evidence": verified}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    print(f"wrote {target}\n")
    for entry in verified:
        mark = "yes" if entry["has_experience"] else "NO "
        quote = entry["evidence_quote"][:64].replace("\n", " ")
        print(f"  {mark}  {entry['slot_id']:<26} {quote}")
    if discarded:
        print("\nDiscarded, unverifiable against the CV:")
        for item in discarded:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
