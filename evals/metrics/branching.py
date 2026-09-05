"""Where the interview could have gone, measured without asking anyone to sit it again.

`Interviewer.next_utterance` is a pure function of the transcript, so a recorded interview
can be rewound to every turn boundary and the interviewer asked, k times, what it would say
next. The answers are a real person's, given once and replayed; nothing simulates a
candidate. What comes out is how many *different* competencies it would reach for at each
point: a scheduler answers with one every time, a prompt answers with a spread, and the
width of that spread is how much of the candidate's screen was a draw.

**This needs a provider that samples.** Pinned to `temperature: 0` or a fixed seed, k
samples are k copies and the number would describe the seed. `guard_sampling_provider`
refuses that rather than producing a confident wrong answer.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from evals.metrics.judge import judge_question
from solution.adapters.providers.base import LlmProvider
from solution.adapters.session_store import SessionEvent, SessionStore
from solution.adapters.slot_plan import SlotPlan
from solution.application.runner import Interviewer
from solution.domain.transcript import Answer, Transcript, Utterance


class NotSampling(RuntimeError):
    """The provider is pinned to a deterministic setting, so k samples would be one."""


def guard_sampling_provider(provider: LlmProvider) -> None:
    """Refuse a provider whose k samples would be k copies.

    Checked by attribute rather than by provider name, so a new adapter that grows a seed
    is caught without this module having to learn about it.
    """
    seed = getattr(provider, "seed", None)
    temperature = getattr(provider, "temperature", None)

    pinned = []
    if seed is not None:
        pinned.append(f"seed={seed}")
    if temperature is not None and float(temperature) == 0.0:
        pinned.append(f"temperature={temperature}")

    if pinned:
        raise NotSampling(
            f"{provider.name}:{provider.model} is pinned to {', '.join(pinned)}, so "
            "sampling it k times returns the same answer k times and this would measure "
            "the seed rather than the interviewer. Either run against a provider that "
            "samples, or clear the seed and raise the temperature in config.yaml - and "
            "record in CHANGELOG.md that you did, because it changes what every other "
            "run of that provider means."
        )


def transcript_from_record(events: Sequence[SessionEvent]) -> Transcript:
    """Rebuild the transcript a recorded interview actually had.

    Rebuilt through the same `with_question` / `with_answer` the runner uses, so what is
    replayed to the interviewer is assembled exactly the way it was assembled live. A
    transcript stitched together some other way would measure a conversation that never
    happened.
    """
    transcript = Transcript()
    for event in events:
        if event.type == "question_asked":
            transcript = transcript.with_question(
                Utterance(
                    text=event.data.get("text", ""),
                    kind=event.data.get("kind", "question"),
                    slot_id=event.data.get("slot_id"),
                ),
                float(event.data.get("generation_seconds") or 0.0),
            )
        elif event.type == "answer_received":
            transcript = transcript.with_answer(
                Answer(
                    text=event.data.get("text", ""),
                    seconds_used=float(event.data.get("seconds_used") or 0.0),
                )
            )
    return transcript


def decision_points(transcript: Transcript) -> list[Transcript]:
    """Every prefix the interviewer would have been asked to continue from.

    One per answer, since that is when the interviewer chooses again. The empty prefix -
    the opening - is excluded for the same reason every rate excludes it: it is identical
    by construction, so there is nothing there to vary.
    """
    prefixes: list[Transcript] = []
    running = Transcript()
    for entry in transcript.entries:
        running = Transcript(entries=running.entries + (entry,))
        if entry.speaker.value == "candidate" and len(running.entries) > 1:
            prefixes.append(running)
    return prefixes


def label(
    question: str, plan: SlotPlan, judge_provider: LlmProvider | None
) -> tuple[str | None, str]:
    """The same instrument the metrics use, so a sampled question and a real one are
    labelled identically. The blind judge, or nothing - see `measure.py` for why the
    keyword layer that used to precede it was removed."""
    if judge_provider is None:
        return None, "unresolved"
    return judge_question(question, plan.slots, judge_provider), "judge"


def branch_session(
    *,
    events: Sequence[SessionEvent],
    plan: SlotPlan,
    build_interviewer: Callable[[], Interviewer],
    samples: int,
    judge_provider: LlmProvider | None = None,
    store: SessionStore | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Sample the next question k times at every decision point of a recorded interview.

    `build_interviewer` is a factory rather than an instance so each sample starts from
    the same state as the live run did, whatever state a future rung's interviewer keeps.
    """
    transcript = transcript_from_record(events)
    prefixes = decision_points(transcript)

    points: list[dict[str, Any]] = []
    layers = {"judge": 0, "unresolved": 0}

    for index, prefix in enumerate(prefixes, start=1):
        if on_progress is not None:
            on_progress(index, len(prefixes))

        sampled: list[dict[str, Any]] = []
        for sample in range(1, samples + 1):
            utterance = build_interviewer().next_utterance(prefix)
            if utterance is None:
                sampled.append({"sample": sample, "text": None, "slot_id": None,
                                "resolved_by": "finished"})
                continue

            slot_id, resolved_by = label(utterance.text, plan, judge_provider)
            layers[resolved_by] = layers.get(resolved_by, 0) + 1
            sampled.append({"sample": sample, "text": utterance.text,
                            "slot_id": slot_id, "resolved_by": resolved_by})
            if store is not None:
                store.append(
                    "branch_sample",
                    decision_point=index,
                    sample=sample,
                    slot_id=slot_id,
                    resolved_by=resolved_by,
                    text=utterance.text,
                )

        distinct = sorted({s["slot_id"] for s in sampled if s["slot_id"]})
        points.append(
            {
                "decision_point": index,
                "after_answer": prefix.entries[-1].text[:120],
                "distinct_slots": distinct,
                "distinct_count": len(distinct),
                "samples": sampled,
            }
        )

    counts = [p["distinct_count"] for p in points]
    return {
        "decision_points": len(points),
        "samples_per_point": samples,
        "mean_distinct_slots": round(sum(counts) / len(counts), 2) if counts else 0.0,
        "max_distinct_slots": max(counts) if counts else 0,
        "fully_consistent_points": sum(1 for c in counts if c <= 1),
        "resolved_by": layers,
        "points": points,
    }


def render(result: Mapping[str, Any]) -> str:
    total = max(int(result.get("decision_points") or 0), 1)
    consistent = int(result.get("fully_consistent_points") or 0)
    lines = [
        "",
        f"  decision points  {result.get('decision_points')}"
        f"   x {result.get('samples_per_point')} samples each",
        "",
        f"  MEAN DISTINCT    {result.get('mean_distinct_slots')}"
        "   competencies the interviewer would reach for, per decision",
        f"    worst point    {result.get('max_distinct_slots')}",
        f"    consistent     {consistent}/{total}  ({consistent / total:.0%} of decisions"
        " gave the same competency every time)",
        "",
    ]
    for point in result.get("points") or []:
        named = ", ".join(point["distinct_slots"]) or "-"
        lines.append(f"    {point['decision_point']:>2}.  {point['distinct_count']}  {named}")
    layers = result.get("resolved_by") or {}
    labelled = sum(layers.values()) or 1
    lines += [
        "",
        f"  labelled by      judge {layers.get('judge', 0) / labelled:.0%}"
        f"   unresolved {layers.get('unresolved', 0) / labelled:.0%}",
        "",
    ]
    return "\n".join(lines)
