"""Render an append-only record for a human.

    interview show evals/results/iteration-00/session-<stamp>.jsonl
    interview show trajectories/judge-<stamp>.jsonl

Session records and trajectory records are the same format - a `SessionStore` of typed
events - so one renderer serves both. That is not a coincidence worth hiding: a trajectory
*is* a session, of an agent rather than of a candidate, and the deliverable asks for both
to be followable from the agent's instructions through to its result.

Model calls are rendered with their prompts. They are long, and that is the point: a
reviewer checking whether the interviewer was told something it should not have been needs
to read what was actually sent, not a summary of it.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Mapping

from solution.adapters.session_store import SessionEvent, SessionStore

WIDTH = 88
RULE = "=" * WIDTH


def wrap(text: str, indent: str = "    ") -> str:
    return "\n".join(
        textwrap.fill(paragraph, width=WIDTH, initial_indent=indent, subsequent_indent=indent)
        or indent
        for paragraph in text.split("\n")
    )


def _metadata(data: Mapping[str, Any]) -> list[str]:
    experiment = data.get("experiment") or {}
    lines = [
        "",
        RULE,
        f"  iteration {data.get('iteration')}   {data.get('provider')}:{data.get('model')}"
        f"   commit {data.get('commit')}",
        f"  run kind  {data.get('run_kind', 'measurement')}",
        f"  slots     {', '.join(data.get('slot_ids', []))}",
    ]
    if experiment:
        lines.append(
            f"  experiment {experiment.get('lock_id')}"
            f"  frozen {experiment.get('frozen_at')}"
        )
    else:
        lines.append("  experiment (none - this run predates the lock, or was not a measurement)")
    lines.append(RULE)
    return lines


def _model_call(data: Mapping[str, Any], number: int) -> list[str]:
    header = (
        f"  MODEL CALL {number}  [{data.get('call')}, attempt {data.get('attempt')}, "
        f"{data.get('provider')}:{data.get('model')}]"
    )
    lines = ["", header, "", "    -- system --", wrap(str(data.get("system", "")), "    ")]
    lines += ["", "    -- prompt --", wrap(str(data.get("prompt", "")), "    ")]
    if "error" in data:
        lines += ["", "    -- FAILED --", wrap(str(data["error"]), "    ")]
    else:
        lines += ["", "    -- reply --", wrap(str(data.get("raw", "")), "    ")]
    return lines


def render_event(event: SessionEvent, counters: dict[str, int]) -> list[str]:
    data = event.data

    if event.type == "run_metadata":
        return _metadata(data)

    if event.type == "trajectory_started":
        return [
            "",
            RULE,
            f"  agent      {data.get('agent')}",
            f"  purpose    {data.get('purpose')}",
            f"  instructions {data.get('instructions')}",
            f"  model      {data.get('provider')}:{data.get('model')}"
            f"   commit {data.get('commit')}",
            RULE,
        ]

    if event.type == "model_call":
        counters["call"] += 1
        return _model_call(data, counters["call"])

    if event.type in ("smoke_run", "pilot_run"):
        label = event.type.removesuffix("_run").upper()
        return ["", f"  ** {label} RUN - {data.get('note', '')} **"]

    if event.type == "question_asked":
        counters["question"] += 1
        return [
            "",
            f"  INTERVIEWER  Q{counters['question']}  [{data.get('kind', '')}, "
            f"slot={data.get('slot_id') or '-'}, {data.get('generation_seconds', 0)}s]",
            wrap(str(data.get("text", ""))),
        ]

    if event.type == "answer_received":
        return [
            "",
            f"  CANDIDATE  [{data.get('seconds_used', 0)}s]",
            wrap(str(data.get("text", "")) or "(no answer)"),
        ]

    if event.type == "opening_answer_replayed":
        return ["", f"  [frozen opening answer replayed, {data.get('characters')} characters]"]

    if event.type == "tracked_input_changed":
        return [
            "",
            f"  [tracked input changed: {data.get('field')} "
            f"{str(data.get('frozen'))[:8]} -> {str(data.get('current'))[:8]}; "
            "recorded, not blocked]",
        ]

    if event.type == "interview_ended":
        return [
            "",
            RULE,
            f"  ended: {data.get('reason')}   questions: {data.get('questions_asked')}   "
            f"elapsed: {float(data.get('elapsed_seconds') or 0) / 60:.1f} min",
            RULE,
            "",
        ]

    return ["", f"  [{event.type}] {json.dumps(dict(data), ensure_ascii=False)[:WIDTH * 2]}"]


def render_record(path: Path) -> str:
    events = SessionStore(path).events()
    if not events:
        return f"\n  {path} holds no events.\n"

    counters = {"question": 0, "call": 0}
    lines: list[str] = []
    for event in events:
        lines += render_event(event, counters)
    return "\n".join(lines) + "\n"
