"""Measure one session record.

    python -m evals.metrics.measure evals/results/iteration-00/session-20260829-205109.jsonl

Reads a session record and writes the metrics beside it as `<session>.metrics.json`,
with per-question detail so every aggregate can be checked by hand. Nothing here reads
the interviewer's own slot labels: see evals/metrics/labelling.py for why.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import yaml

from evals.metrics.judge import judge_question
from evals.metrics.labelling import label_by_rule
from evals.metrics.rates import is_carry_over, is_grounded
from solution.adapters.providers import build_provider
from solution.adapters.resume_pdf import read_resume_text
from solution.adapters.session_store import SessionStore
from solution.adapters.slot_plan import SlotPlan, load_slot_plan
from solution.domain.lexicon import build_lexicon, extract_terms

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class QuestionMeasurement:
    index: int
    text: str
    slot_id: str | None
    resolved_by: str  # rule | judge | unresolved
    carry_over: bool
    grounded: bool


def measure_session(
    session_path: Path,
    plan: SlotPlan,
    resume_text: str,
    judge_provider=None,
) -> dict:
    events = SessionStore(session_path).events()
    metadata = next((e.data for e in events if e.type == "run_metadata"), {})
    is_smoke = any(e.type == "smoke_run" for e in events)

    lexicon = build_lexicon(plan.keywords)
    resume_terms = extract_terms(resume_text, lexicon)
    slots_by_id = {slot.id: slot for slot in plan.slots}

    measurements: list[QuestionMeasurement] = []
    prior_answer_terms: set[str] = set()
    index = 0

    for event in events:
        if event.type == "answer_received":
            prior_answer_terms |= extract_terms(event.data.get("text", ""), lexicon)
            continue
        if event.type != "question_asked":
            continue

        # The opening turn is identical by construction, so it is excluded from every rate.
        if event.data.get("kind") == "opening":
            continue

        index += 1
        question = event.data.get("text", "")
        slot_id = label_by_rule(question, plan.slots)
        resolved_by = "rule"

        if slot_id is None:
            if judge_provider is not None:
                slot_id = judge_question(question, plan.slots, judge_provider)
                resolved_by = "judge"
            else:
                resolved_by = "unresolved"

        slot = slots_by_id.get(slot_id) if slot_id else None
        measurements.append(
            QuestionMeasurement(
                index=index,
                text=question,
                slot_id=slot_id,
                resolved_by=resolved_by,
                carry_over=is_carry_over(
                    question,
                    slot=slot,
                    prior_answer_terms=frozenset(prior_answer_terms),
                    lexicon=lexicon,
                ),
                grounded=is_grounded(
                    question,
                    slot=slot,
                    resume_terms=resume_terms,
                    prior_answer_terms=frozenset(prior_answer_terms),
                    lexicon=lexicon,
                ),
            )
        )

    asked = len(measurements)
    covered = {m.slot_id for m in measurements if m.slot_id}
    by_layer = {
        layer: sum(1 for m in measurements if m.resolved_by == layer)
        for layer in ("rule", "judge", "unresolved")
    }

    return {
        "session": session_path.name,
        "is_smoke_run": is_smoke,
        "metadata": metadata,
        "denominator": plan.denominator,
        "coverage": {
            "covered_slots": sorted(covered),
            "missed_slots": sorted({s.id for s in plan.slots} - covered),
            "value": round(len(covered) / plan.denominator, 3) if plan.denominator else 0.0,
        },
        "carry_over_rate": round(sum(m.carry_over for m in measurements) / asked, 3) if asked else 0.0,
        "grounding_rate": round(sum(m.grounded for m in measurements) / asked, 3) if asked else 0.0,
        "questions_measured": asked,
        "resolved_by": by_layer,
        "questions": [asdict(m) for m in measurements],
    }


def render(result: dict) -> str:
    coverage = result["coverage"]
    layers = result["resolved_by"]
    total = max(result["questions_measured"], 1)
    lines = [
        "",
        f"  session          {result['session']}",
        f"  iteration        {result['metadata'].get('iteration', '?')}"
        f"   provider {result['metadata'].get('provider', '?')}"
        f":{result['metadata'].get('model', '?')}",
        "",
        f"  COVERAGE         {len(coverage['covered_slots'])}/{result['denominator']}"
        f"   ({coverage['value']:.0%})",
        f"    covered        {', '.join(coverage['covered_slots']) or '-'}",
        f"    missed         {', '.join(coverage['missed_slots']) or '-'}",
        "",
        f"  carry-over rate  {result['carry_over_rate']:.0%}",
        f"  grounding rate   {result['grounding_rate']:.0%}",
        "",
        f"  questions        {result['questions_measured']}",
        f"  labelled by      rule {layers['rule'] / total:.0%}"
        f"   judge {layers['judge'] / total:.0%}"
        f"   unresolved {layers['unresolved'] / total:.0%}",
    ]
    if result["is_smoke_run"]:
        lines += ["", "  ** SMOKE RUN - canned candidate, not a measurement **"]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    plan = load_slot_plan(ROOT / config["role"] / "slots.yaml")
    resume_text = read_resume_text(ROOT / config["case"] / "cv.pdf")

    use_judge = "--no-judge" not in argv
    judge_provider = build_provider(config, config["judge"]["provider"]) if use_judge else None

    for raw_path in argv[1:]:
        if raw_path.startswith("--"):
            continue
        session_path = Path(raw_path)
        result = measure_session(session_path, plan, resume_text, judge_provider)
        target = session_path.with_suffix(".metrics.json")
        target.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(render(result))
        print(f"  written to {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
