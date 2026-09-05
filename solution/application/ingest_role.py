"""Turn a job description into a draft slot plan for a human to review and freeze.

    interview role-extract

Writes roles/<role>/slots.draft.yaml. It deliberately does not write slots.yaml: the plan
is the denominator of the primary metric, so a person reviews it and renames it. That
manual step is the human checkpoint, not a formality.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from solution.adapters.providers.base import LlmProvider, LlmRequest

SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "competencies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": [
                            "language_framework",
                            "data_storage",
                            "infra_ops",
                            "cross_cutting",
                        ],
                    },
                    "rank": {"type": "integer"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "name", "kind", "rank", "keywords"],
            },
        }
    },
    "required": ["competencies"],
}

SYSTEM = """You extract the competencies a job description requires, so that an interview can be
planned to cover them.

Read the job description and list every distinct technical competency it asks for.

RULES
- A competency is something a candidate could be asked to describe from experience.
  "React" is a competency. "Team player" is not. "5 years of experience" is not.
- Merge near-duplicates. If the description mentions React, Redux and hooks, that is one
  competency (frontend / React), not three.
- Split genuinely different areas. "Backend and databases" is two competencies, because a
  candidate can be strong in one and weak in the other.
- Rank by relevance to the role: rank 1 is the competency the job description leans on
  most heavily, judged by prominence, repetition and whether it is listed as required
  rather than preferred.
- Aim for 6 to 10 competencies. Fewer than 6 usually means you merged too aggressively.
- keywords are the words an interviewer would actually use when asking about this
  competency, including the technology names the description mentions. They are matched
  literally and case-insensitively later, so give lowercase single words or short
  phrases, not sentences.
- kind selects the question template used when generation fails:
    language_framework - a language, framework or library
    data_storage       - databases, caching, storage, data modelling
    infra_ops          - cloud, deployment, CI/CD, monitoring, incidents
    cross_cutting      - testing, code review, architecture, security, collaboration
      practices

Reply with JSON only, no prose."""


@dataclass(frozen=True, slots=True)
class DraftPlan:
    kept: tuple[Mapping[str, Any], ...]
    excluded: tuple[Mapping[str, Any], ...]


def split_by_budget(
    competencies: Sequence[Mapping[str, Any]], max_slots: int, budget_note: str
) -> DraftPlan:
    """Keep the most relevant competencies that fit; document the ones the budget cuts."""
    ordered = sorted(competencies, key=lambda c: int(c["rank"]))
    kept = ordered[:max_slots]
    excluded = [
        {"name": item["name"], "reason": budget_note} for item in ordered[max_slots:]
    ]
    renumbered = [{**item, "rank": index + 1} for index, item in enumerate(kept)]
    return DraftPlan(kept=tuple(renumbered), excluded=tuple(excluded))


def extract(role_text: str, provider: LlmProvider) -> tuple[Mapping[str, Any], ...]:
    request = LlmRequest(
        call="extract_slots",
        system=SYSTEM,
        prompt=f"JOB DESCRIPTION\n\n{role_text}",
        schema=SCHEMA,
    )
    response = provider.complete_json(request)
    return tuple(response.payload["competencies"])


def render_draft(
    role_dir: Path, role_name: str, source: str, frozen_at: str, plan: DraftPlan
) -> Path:
    from solution.adapters.cv_redaction import file_digest

    document = {
        "role": role_name,
        "source": source,
        "frozen_at": frozen_at,
        "provenance": {"role_sha256": file_digest(role_dir / "role.txt")},
        "slots": [dict(slot) for slot in plan.kept],
        "excluded": [dict(item) for item in plan.excluded],
    }
    path = role_dir / "slots.draft.yaml"
    header = (
        "# DRAFT - review every line, then rename to slots.yaml and commit.\n"
        "# This file is the denominator of the primary metric. Once frozen it is read-only.\n"
    )
    path.write_text(header + yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """Kept so the module runs on its own; `interview role-extract` is the documented path."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print(__doc__)
        return 2

    root = Path(__file__).resolve().parents[2]
    role_dir = root / arguments[0]
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))

    from solution.adapters.providers import build_provider

    provider = build_provider(config)
    from solution.adapters.role_text import read_role_text

    role_text = read_role_text(role_dir / "role.txt")

    competencies = extract(role_text, provider)
    max_slots = int(config["interview"].get("max_slots", 6))
    note = (
        f"beyond the top {max_slots} competencies that fit the "
        f"{config['interview']['total_seconds'] // 60}-minute budget"
    )
    plan = split_by_budget(competencies, max_slots, note)

    path = render_draft(
        role_dir,
        role_name=role_dir.name,
        source="see role.txt header",
        frozen_at="",
        plan=plan,
    )
    print(f"wrote {path}")
    print(f"  kept     : {[s['id'] for s in plan.kept]}")
    print(f"  excluded : {[s['name'] for s in plan.excluded]}")
    print("\nReview it, fill frozen_at, rename to slots.yaml, and commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
