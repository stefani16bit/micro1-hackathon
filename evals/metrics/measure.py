"""Measure one session record.

    interview measure evals/results/iteration-00/session-<stamp>.jsonl

Reads a session record and writes the metrics beside it as `<session>.metrics.json`,
with per-question detail so every aggregate can be checked by hand.

**Nothing here reads the interviewer's own slot labels.** Iteration 0 has no slot concept,
so measuring the later rungs by self-report would apply a different instrument to each end
of the ladder. Every question is labelled from its text alone, by a judge blind to which
system produced it.
"""

from __future__ import annotations

import json
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import yaml

from evals.metrics import allocation as allocation_metrics
from evals.metrics.judge import judge_question
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
    resolved_by: str
    carry_over: bool
    grounded: bool


def schedule_ceiling_of(events: Sequence, metadata: dict) -> int | None:
    """The longest chain on one competency the run's schedule *permitted*.

    What turns `longest_chain` from a number into a comparison: a chain of 4 means nothing
    on its own and a great deal beside a ceiling of 2. Read off the record rather than off
    config, so a run measured months later is compared against the budget it actually ran
    under. A run with no `scheduler_decided` event had no schedule and gets None - nothing
    in a single prompt counts what it has asked.
    """
    if not any(event.type == "scheduler_decided" for event in events):
        return None
    return 1 + int(metadata.get("max_followups_per_slot", 1))


def measure_session(
    session_path: Path,
    plan: SlotPlan,
    resume_text: str,
    judge_provider=None,
) -> dict:
    """Measure one record."""
    events = SessionStore(session_path).events()
    metadata = next((e.data for e in events if e.type == "run_metadata"), {})
    lock_id = (metadata.get("experiment") or {}).get("lock_id") or next(
        (e.data.get("lock_id") for e in events if e.type == "experiment_recorded"), None
    )
    ended = next((e.data for e in events if e.type == "interview_ended"), {})
    interrupted = ended.get("reason") == "interrupted_by_candidate"

    run_kind = metadata.get("run_kind") or next(
        (e.type.removesuffix("_run") for e in events if e.type in ("smoke_run", "pilot_run")),
        "measurement",
    )

    lexicon = build_lexicon(plan.keywords)
    resume_terms = extract_terms(resume_text, lexicon)
    slots_by_id = {slot.id: slot for slot in plan.slots}

    measurements: list[QuestionMeasurement] = []
    prior_answer_terms: set[str] = set()
    answer_seconds: list[float] = []
    answering_a_measured_question = False
    index = 0

    for event in events:
        if event.type == "answer_received":
            prior_answer_terms |= extract_terms(event.data.get("text", ""), lexicon)
            if answering_a_measured_question:
                answer_seconds.append(float(event.data.get("seconds_used", 0.0)))
                answering_a_measured_question = False
            continue
        if event.type != "question_asked":
            continue

        if event.data.get("kind") in ("opening", "clarification"):
            continue

        answering_a_measured_question = True
        index += 1
        question = event.data.get("text", "")
        if judge_provider is not None:
            slot_id = judge_question(question, plan.slots, judge_provider)
            resolved_by = "judge"
        else:
            slot_id = None
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
        for layer in ("judge", "unresolved")
    }

    return {
        "session": session_path.name,
        "run_kind": run_kind,
        "experiment_lock_id": lock_id,
        "interrupted": interrupted,
        "metadata": metadata,
        "denominator": plan.denominator,
        "coverage": {
            "covered_slots": sorted(covered),
            "missed_slots": sorted({s.id for s in plan.slots} - covered),
            "value": round(len(covered) / plan.denominator, 3) if plan.denominator else 0.0,
        },
        "carry_over_rate": (
            round(sum(m.carry_over for m in measurements) / asked, 3) if asked else 0.0
        ),
        "grounding_rate": (
            round(sum(m.grounded for m in measurements) / asked, 3) if asked else 0.0
        ),
        "allocation": allocation_metrics.describe(
            [m.slot_id for m in measurements], plan.denominator
        ),
        "schedule_ceiling": schedule_ceiling_of(events, dict(metadata)),
        "questions_measured": asked,
        "answer_seconds": describe(answer_seconds),
        "resolved_by": by_layer,
        "questions": [asdict(m) for m in measurements],
    }


def describe(values: Sequence[float]) -> dict:
    """Enough of the distribution to spot drift, not so much that nobody reads it."""
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "total": 0.0}
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 1),
        "median": round(statistics.median(values), 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "total": round(sum(values), 1),
    }


def render(result: dict) -> str:
    coverage = result["coverage"]
    seconds = result["answer_seconds"]
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
    ]
    lines += allocation_metrics.render(
        result.get("allocation") or {}, ceiling=result.get("schedule_ceiling")
    )
    lines += [
        "",
        f"  carry-over rate  {result['carry_over_rate']:.0%}",
        f"  grounding rate   {result['grounding_rate']:.0%}",
        "",
        f"  questions        {result['questions_measured']}",
        f"  answer time      {seconds['mean']:.0f}s mean"
        f"   {seconds['median']:.0f}s median"
        f"   {seconds['min']:.0f}-{seconds['max']:.0f}s range"
        f"   {seconds['total'] / 60:.1f} min answering",
        f"  labelled by      judge {layers['judge'] / total:.0%}"
        f"   unresolved {layers['unresolved'] / total:.0%}",
    ]
    warning = {
        "smoke": "** SMOKE RUN - canned candidate, not a measurement **",
        "pilot": "** PILOT RUN - unrehearsed respondent, opening typed live; not a measurement **",
    }.get(result["run_kind"])
    if warning:
        lines += ["", f"  {warning}"]
    return "\n".join(lines) + "\n"


def build_judge(config, *, trace: bool = True):
    """The judge, wrapped so every classification it makes lands in a trajectory.

    The judge labels every question, so it decides the whole of the coverage figure - the
    keyword layer that used to precede it resolved nothing and was removed. agentic-
    workflows.md section 8 asks for a trace per agent, and this is the agent whose reasoning
    a sceptical reader will most want to inspect.
    """
    provider = build_provider(config, config["judge"]["provider"])
    if not trace:
        return provider

    from datetime import datetime, timezone

    from solution.adapters.providers import TracingProvider

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    store = SessionStore(ROOT / "trajectories" / f"judge-{stamp}.jsonl")
    store.append(
        "trajectory_started",
        agent="judge",
        purpose="label which competency a question asked about",
        instructions="evals/metrics/judge.py",
        provider=provider.name,
        model=provider.model,
    )
    return TracingProvider(provider, store, context={"agent": "judge"})


def main(argv: Sequence[str] | None = None) -> int:
    """Kept so the module runs on its own; `interview measure` is the documented path."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print(__doc__)
        return 2

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    plan = load_slot_plan(ROOT / config["role"] / "slots.yaml")
    resume_text = read_resume_text(ROOT / config["case"] / "cv.pdf")

    use_judge = "--no-judge" not in arguments
    judge_provider = build_judge(config) if use_judge else None

    for raw_path in arguments:
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
    raise SystemExit(main())
