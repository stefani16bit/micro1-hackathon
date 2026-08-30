"""The judge layer of the cascade, for questions the rule cannot resolve.

Blind by construction rather than by procedure: the judge is shown one question and the
list of competencies, and nothing else. No transcript, no iteration number, no indication
of which system produced it, not even the neighbouring questions. There is nothing in the
input it could use to favour one end of the ladder over the other.

It runs on the same model as the interviewer (`judge.provider` in config.yaml), and the
blindness above is why that is acceptable: this is classification, not quality judgement,
and a judge that cannot tell whose output it is labelling has no way to prefer its own.
The external check on it is the hand-labelled agreement sample, which is reported with
every result. See PREREGISTRATION.md 3d.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from solution.adapters.providers.base import LlmProvider, LlmRequest
from solution.domain.models import Slot

SYSTEM = """You decide which competency an interview question is asking about.

You are given a list of competencies and one question. Answer with the id of the
competency the question is asking the candidate to talk about.

RULES
- Judge the question only. You have no transcript and you do not need one.
- If the question is asking about something outside every competency listed, answer
  "none". Opening pleasantries, questions about availability, and questions about the
  role itself are "none".
- If the question touches two competencies, answer the one it is mainly asking the
  candidate to describe.

Reply with JSON only."""

SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "slot_id": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "low"]},
    },
    "required": ["slot_id", "confidence"],
}


def build_prompt(question: str, slots: Sequence[Slot]) -> str:
    lines = ["COMPETENCIES", ""]
    for slot in slots:
        lines.append(f"- {slot.id}: {slot.name} ({', '.join(slot.keywords)})")
    lines += ["- none: the question is about none of the above", "", "QUESTION", "", question]
    return "\n".join(lines)


def judge_question(question: str, slots: Sequence[Slot], provider: LlmProvider) -> str | None:
    response = provider.complete_json(
        LlmRequest(
            call="judge_question",
            system=SYSTEM,
            prompt=build_prompt(question, slots),
            schema=SCHEMA,
        )
    )
    slot_id = str(response.payload["slot_id"]).strip()
    known = {slot.id for slot in slots}
    return slot_id if slot_id in known else None
