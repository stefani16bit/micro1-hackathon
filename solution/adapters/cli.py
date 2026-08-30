"""Run one interview.

    python -m solution.adapters.cli --iteration 0
    python -m solution.adapters.cli --iteration 0 --provider claude_cli

Writes a complete session record to evals/results/iteration-NN/. That file is the only
input to both the metrics and the trajectories, so the run stamps everything needed to
reproduce it - provider, model, git commit, and the slot plan and case in force.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import yaml

from solution.adapters.candidate_io import ConsoleIO, FrozenOpeningIO, SmokeIO
from solution.adapters.prompt_files import load_fenced_blocks
from solution.adapters.providers import build_provider
from solution.adapters.providers.base import LlmProvider
from solution.adapters.resume_pdf import read_resume_text
from solution.adapters.session_store import SessionStore
from solution.adapters.slot_plan import load_slot_plan
from solution.application.interviewers.single_prompt import SinglePromptInterviewer
from solution.application.ingest_resume import main as refresh_evidence
from solution.application.preflight import prepare, render
from solution.application.runner import Interviewer, run_interview
from solution.domain.models import TimeBudget

ROOT = Path(__file__).resolve().parents[2]


def current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def measured_runs_exist() -> bool:
    """Has any iteration been measured yet? Decides whether inputs may still be rebuilt."""
    results = ROOT / "evals" / "results"
    if not results.exists():
        return False
    return any(
        any(directory.glob("session-*.jsonl"))
        for directory in results.glob("iteration-*")
        if directory.is_dir()
    )


def build_interviewer(
    iteration: int,
    provider: LlmProvider,
    role_text: str,
    resume_text: str,
    budget: TimeBudget,
) -> Interviewer:
    if iteration == 0:
        return SinglePromptInterviewer(
            provider=provider,
            role_text=role_text,
            resume_text=resume_text,
            budget=budget,
            prompt_path=ROOT / "baseline" / "prompt.md",
        )
    raise SystemExit(
        f"iteration {iteration} is not implemented yet - see the ladder in the plan"
    )


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Run one interview session.")
    parser.add_argument("--iteration", type=int, required=True, help="which rung of the ladder")
    parser.add_argument("--provider", default=None, help="override the provider in config.yaml")
    parser.add_argument(
        "--smoke",
        type=int,
        default=0,
        metavar="SECONDS",
        help="verify the pipeline with a canned candidate over a short budget; never a measurement",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help=(
            "pilot run: the opening answer is typed live rather than replayed, and the "
            "record is written to evals/results/pilot/. Never a measurement - its purpose "
            "is to produce the frozen opening answer and the response brief"
        ),
    )
    args = parser.parse_args(argv[1:])

    if args.pilot and args.smoke:
        raise SystemExit("--pilot and --smoke are mutually exclusive")

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    settings = config["interview"]
    budget = TimeBudget(
        total_seconds=args.smoke or settings["total_seconds"],
        answer_deadline_seconds=settings["answer_deadline_seconds"],
        turn_overhead_seconds=settings["turn_overhead_seconds"],
    )

    role_dir = ROOT / config["role"]
    case_dir = ROOT / config["case"]

    # Nothing starts until the derived artifacts are in step with their inputs.
    report = prepare(
        role_dir=role_dir, case_dir=case_dir, require_frozen_opening=not args.pilot
    )

    # Résumé evidence is regenerated automatically only while no measured run exists.
    # Before the first measurement, swapping the CV simply means a different case and
    # rebuilding is the obvious thing to do. Afterwards the evidence is an input held
    # constant across the eleven iterations, so changing it would split the ladder into
    # two halves run against different inputs - and that is a decision for a person.
    if report.needs_evidence_refresh and not measured_runs_exist():
        print(render(report))
        print("\n  no measured run exists yet - regenerating the résumé evidence\n")
        refresh_evidence(["ingest_resume", str(case_dir.relative_to(ROOT))])
        report = prepare(
            role_dir=role_dir, case_dir=case_dir, require_frozen_opening=not args.pilot
        )

    if report.derived or report.problems:
        print(render(report))
    if not report.ok:
        return 2

    plan = load_slot_plan(role_dir / "slots.yaml")
    role_text = (role_dir / "role.txt").read_text(encoding="utf-8")
    resume_text = read_resume_text(case_dir / "cv.pdf")
    opening_blocks = load_fenced_blocks(case_dir / "opening-answer.md")

    if args.smoke:
        run_kind, bucket = "smoke", "smoke"
    elif args.pilot:
        run_kind, bucket = "pilot", "pilot"
    else:
        run_kind, bucket = "measurement", f"iteration-{args.iteration:02d}"

    provider = build_provider(config, args.provider)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    store = SessionStore(ROOT / "evals" / "results" / bucket / f"session-{stamp}.jsonl")

    store.append(
        "run_metadata",
        run_kind=run_kind,
        iteration=args.iteration,
        provider=provider.name,
        model=provider.model,
        commit=current_commit(),
        role=str(role_dir.relative_to(ROOT)).replace("\\", "/"),
        case=str(case_dir.relative_to(ROOT)).replace("\\", "/"),
        slot_ids=[slot.id for slot in plan.slots],
        slot_plan_frozen_at=plan.frozen_at,
        total_seconds=budget.total_seconds,
        answer_deadline_seconds=budget.answer_deadline_seconds,
    )

    interviewer = build_interviewer(args.iteration, provider, role_text, resume_text, budget)

    if args.pilot:
        # The opening is typed live so the frozen artifact ends up in the candidate's own
        # words rather than in a draft written for them.
        io = ConsoleIO()
        store.append("pilot_run", note="opening typed live; not a measurement")
    else:
        io = FrozenOpeningIO(
            inner=SmokeIO() if args.smoke else ConsoleIO(),
            opening_text=opening_blocks[0],
            opening_seconds=float(settings["opening_answer_seconds"]),
            store=store,
        )
        if args.smoke:
            store.append("smoke_run", note="canned candidate; not a measurement")

    print(f"\n  {run_kind}  |  iteration {args.iteration}  |  {provider.name}:{provider.model}")
    print(f"  {budget.total_seconds // 60} minutes, {budget.answer_deadline_seconds}s per answer")
    if args.pilot:
        print("  the opening answer is typed live and frozen from what you write")
    print(f"  recording to {store.path.relative_to(ROOT)}\n")

    try:
        outcome = run_interview(
            interviewer=interviewer, io=io, store=store, budget=budget
        )
    except KeyboardInterrupt:
        store.append("interview_ended", reason="interrupted_by_candidate")
        print("\n\ninterrupted - the partial session record was kept")
        return 130

    print(f"\n{'=' * 72}")
    print(f"  ended: {outcome.end_reason}")
    print(f"  questions asked: {len(outcome.transcript.questions)}")
    print(f"  elapsed: {outcome.transcript.elapsed_seconds / 60:.1f} min")
    print(f"  record: {store.path.relative_to(ROOT)}")
    print(f"{'=' * 72}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
