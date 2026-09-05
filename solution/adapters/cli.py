"""The one entry point. Every command this project has lives here.

    interview --help

Commands are separated by what they are allowed to touch, which is the point rather than
a tidiness preference:

    check          reach the model once, cheaply           reads nothing
    role-extract   draft a slot plan from role.txt          writes a draft for review
    prepare        rebuild the derived inputs               THE ONLY MUTATING COMMAND
    run            conduct one interview                    preflight is READ-ONLY here
    measure        metrics for one or more sessions         writes .metrics.json
    branch         resample a record's turns k times        writes .branch.json
    report         baseline vs solution, the results table  writes report.md
    show           render a session or trajectory record    reads nothing

Only `prepare` rebuilds a derived input; an interview that silently rewrites its own
inputs is a measurement nobody can reason about afterwards, so `run` reports what is out
of step and stops with the command that fixes it.

There is deliberately no `freeze` command and no pilot step for the opening answer: the
baseline run captures one, frozen the moment it is given. A step that can only be
forgotten, never usefully skipped, is a trap rather than a checkpoint.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from solution.adapters.candidate_io import (
    CapturingOpeningIO,
    ConsoleIO,
    FrozenOpeningIO,
    SmokeIO,
)
from solution.adapters.prompt_files import fill, load_fenced_blocks, load_prompt_pair
from solution.adapters.providers import TracingProvider, build_provider
from solution.adapters.providers.base import LlmProvider, LlmRequest
from solution.adapters.resume_evidence import load_resume_evidence
from solution.adapters.resume_pdf import read_resume_text
from solution.adapters.role_text import read_role_text
from solution.adapters.session_store import SessionStore
from solution.adapters.slot_plan import SlotPlanError, load_slot_plan
from solution.application import experiment as exp
from solution.application.ingest_resume import refresh as refresh_evidence
from solution.application.ingest_resume import render as render_evidence
from solution.application.interviewers.scheduled import ScheduledInterviewer
from solution.application.interviewers.single_prompt import SinglePromptInterviewer
from solution.application.preflight import prepare as run_preflight
from solution.application.preflight import render as render_preflight
from solution.application.runner import Interviewer, run_interview
from solution.domain.models import TimeBudget

ROOT = Path(__file__).resolve().parents[2]

CHECK_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {"ready": {"type": "boolean"}, "model_name": {"type": "string"}},
    "required": ["ready", "model_name"],
}


def load_config() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


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


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def resolve_paths(config: Mapping[str, Any], args) -> tuple[Path, Path]:
    """Role and case directories, with the command line overriding config.yaml."""
    role = getattr(args, "role", None) or config["role"]
    case = getattr(args, "case", None) or config["case"]
    return ROOT / role, ROOT / case


def lock_path(config: Mapping[str, Any]) -> Path:
    return ROOT / config.get("experiment_lock", "evals/experiment-lock.yaml")


def load_plan_or_none(role_dir: Path):
    try:
        return load_slot_plan(role_dir / "slots.yaml")
    except (OSError, SlotPlanError):
        return None


def budget_from(config: Mapping[str, Any], smoke_seconds: int = 0) -> TimeBudget:
    settings = config["interview"]
    return TimeBudget(
        total_seconds=smoke_seconds or settings["total_seconds"],
        expected_answer_seconds=settings["expected_answer_seconds"],
        turn_overhead_seconds=settings["turn_overhead_seconds"],
    )


def traced(provider: LlmProvider, agent: str, purpose: str, instructions: str) -> LlmProvider:
    """Wrap a provider so its calls land in `trajectories/`.

    Section 9 of the hackathon brief: trajectories are captured as work happens and cannot
    be reconstructed later. Every offline agent gets one from its first run onwards.
    """
    store = SessionStore(ROOT / "trajectories" / f"{agent}-{stamp()}.jsonl")
    store.append(
        "trajectory_started",
        agent=agent,
        purpose=purpose,
        instructions=instructions,
        provider=provider.name,
        model=provider.model,
        commit=current_commit(),
    )
    return TracingProvider(provider, store, context={"agent": agent})


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def command_check(args) -> int:
    """One real model call, so a broken provider surfaces in seconds rather than mid-interview."""
    config = load_config()
    provider = build_provider(config, args.provider)
    response = provider.complete_json(
        LlmRequest(
            call="smoke_check",
            system="You reply with JSON only. No prose, no explanation.",
            prompt='Reply with {"ready": true, "model_name": "<the model you are>"}.',
            schema=CHECK_SCHEMA,
        )
    )
    print(f"\n  provider   {response.provider}")
    print(f"  model      {response.model}")
    print(f"  latency    {response.duration_ms} ms")
    print(f"  payload    {dict(response.payload)}\n")
    return 0


def command_role_extract(args) -> int:
    """Draft a slot plan. It writes slots.draft.yaml, never slots.yaml - a person reviews
    and renames it, and that manual step is the human checkpoint, not a formality."""
    from solution.application.ingest_role import extract, render_draft, split_by_budget

    config = load_config()
    role_dir, _ = resolve_paths(config, args)
    provider = traced(
        build_provider(config, args.provider),
        agent="slot-extractor",
        purpose="extract the competencies a job description requires",
        instructions="solution/agent_instructions/slot_extractor.md",
    )

    competencies = extract(read_role_text(role_dir / "role.txt"), provider)
    max_slots = int(config["interview"].get("max_slots", 6))
    plan = split_by_budget(
        competencies,
        max_slots,
        f"beyond the top {max_slots} competencies that fit the "
        f"{config['interview']['total_seconds'] // 60}-minute budget",
    )
    path = render_draft(role_dir, role_dir.name, "see role.txt header", "", plan)

    print(f"\n  wrote {relative(path)}")
    print(f"    kept      {[s['id'] for s in plan.kept]}")
    print(f"    excluded  {[s['name'] for s in plan.excluded]}")
    print("\n  Review it, fill frozen_at, rename to slots.yaml, and commit.\n")
    return 0


def command_prepare(args) -> int:
    """Rebuild the derived inputs. The only command in this project that mutates them.

    Its own guardrail is the experiment lock: once measured runs exist, regenerating an
    input the lock covers would split the ladder into halves run against different inputs,
    so it refuses and says which run already depends on the current value.
    """
    config = load_config()
    role_dir, case_dir = resolve_paths(config, args)
    lock = exp.load_lock(lock_path(config))

    measured: tuple[str, ...] = ()
    if lock is not None:
        measured = exp.measured_runs_for(lock.lock_id, ROOT / "evals" / "results")

    if measured:
        print(_locked_prepare_refusal(lock, measured))
        return 2

    report = run_preflight(
        role_dir=role_dir, case_dir=case_dir, require_frozen_opening=False
    )
    print(render_preflight(report))

    if report.needs_evidence_refresh:
        print("\n  the résumé evidence is out of step - resolving it against the CV\n")
        plan = load_plan_or_none(role_dir)
        if plan is None:
            print("  cannot resolve evidence without a loadable slot plan; fix that first\n")
            return 2
        provider = traced(
            build_provider(config, args.provider),
            agent="resume-matcher",
            purpose="resolve what the CV evidences about each competency",
            instructions="solution/application/ingest_resume.py (SYSTEM)",
        )
        print(render_evidence(refresh_evidence(case_dir=case_dir, plan=plan, provider=provider)))
        report = run_preflight(
            role_dir=role_dir, case_dir=case_dir, require_frozen_opening=False
        )

    print()
    if not report.ok:
        print(render_preflight(report))
        return 2

    print("  inputs are in step.")
    if lock is None:
        print(
            "  next: interview run --baseline   (the first measured run records the\n"
            "        experiment every later rung is compared against)\n"
        )
    else:
        print(
            f"  experiment {lock.lock_id} is recorded but no measured run depends on it\n"
            "  yet, so the next  interview run --baseline  records what you just rebuilt\n"
            "  afresh.\n"
        )
    return 0


def _locked_prepare_refusal(lock: exp.ExperimentLock, measured: Sequence[str]) -> str:
    return "\n".join(
        [
            "",
            "  BLOCKED  this experiment already has measured runs",
            "",
            f"           experiment {lock.lock_id}, frozen {lock.frozen_at}",
            f"           measured runs: {', '.join(measured)}",
            "",
            "           Rebuilding an input now would mean the runs before and after ran",
            "           against different inputs, which PREREGISTRATION.md section 4 lists",
            "           as invalidating the result.",
            "",
            "     fix:  leave the inputs alone, or accept that changing them starts a",
            "           different experiment:",
            "",
            "               interview run --baseline --restart",
            "",
            f"           The existing results keep lock {lock.lock_id} and are never mixed",
            "           with the new one.",
            "",
        ]
    )


def resolve_iteration(config: Mapping[str, Any], args) -> int:
    iterations = config.get("iterations", {})
    if args.baseline:
        return int(iterations.get("baseline", 0))
    if args.solution:
        return int(iterations.get("solution", 10))
    if args.iteration is None:
        raise SystemExit("say which rung: --iteration N, or --baseline / --solution")
    return int(args.iteration)


RUNGS: Mapping[int, Mapping[str, bool]] = {
    1: {"sees_transcript": True, "gated": False},
    2: {"sees_transcript": False, "gated": False},
    3: {"sees_transcript": False, "gated": True},
}


def build_interviewer(
    iteration: int,
    provider: LlmProvider,
    role_text: str,
    resume_text: str,
    budget: TimeBudget,
    *,
    role_dir: Path | None = None,
    case_dir: Path | None = None,
    max_followups_per_slot: int = 1,
    store: SessionStore | None = None,
) -> Interviewer:
    if iteration == 0:
        return SinglePromptInterviewer(
            provider=provider,
            role_text=role_text,
            resume_text=resume_text,
            budget=budget,
            prompt_path=ROOT / "baseline" / "prompt.md",
        )

    if iteration in RUNGS:
        if role_dir is None or case_dir is None:
            raise SystemExit("a scheduled rung needs the role and case directories")
        return ScheduledInterviewer(
            provider=provider,
            plan=load_slot_plan(role_dir / "slots.yaml"),
            evidence=load_resume_evidence(case_dir / "resume-evidence.yaml"),
            budget=budget,
            iteration=iteration,
            max_followups_per_slot=max_followups_per_slot,
            prompt_path=ROOT / "solution" / "agent_instructions" / "interviewer.md",
            store=store,
            **RUNGS[iteration],
        )

    raise SystemExit(
        f"\n  iteration {iteration} does not exist yet.\n"
        f"  built rungs: 0 (baseline), {', '.join(str(r) for r in sorted(RUNGS))}.\n"
        "  CHANGELOG.md records what each one changed.\n"
    )


def command_run(args) -> int:
    config = load_config()
    role_dir, case_dir = resolve_paths(config, args)
    iteration = resolve_iteration(config, args)
    budget = budget_from(config, args.smoke)

    if args.pilot and args.smoke:
        raise SystemExit("--pilot and --smoke are mutually exclusive")

    is_measurement = not (args.pilot or args.smoke)
    is_baseline = iteration == int(config.get("iterations", {}).get("baseline", 0))
    opening_md = case_dir / "opening-answer.md"
    opening_frozen = bool(load_fenced_blocks(opening_md)) if opening_md.exists() else False

    lock = exp.load_lock(lock_path(config))
    current = exp.compute_inputs(
        root=ROOT,
        role_dir=role_dir,
        case_dir=case_dir,
        plan=load_plan_or_none(role_dir),
        settings=config["interview"],
    )
    measured = exp.measured_runs_for(lock.lock_id, ROOT / "evals" / "results") if lock else ()

    restarting = is_measurement and is_baseline and args.restart
    if is_measurement and lock is not None:
        drifts = exp.compare(lock, current)
        if drifts and not restarting:
            print(exp.render_drift(lock, drifts, measured, current))
            return 2
    elif is_measurement and lock is None and not is_baseline:
        print(_ladder_starts_at_baseline(iteration, current))
        return 2

    recording = is_measurement and (lock is None or restarting)
    capturing = recording and is_baseline and (not opening_frozen or restarting)

    report = run_preflight(
        role_dir=role_dir,
        case_dir=case_dir,
        require_frozen_opening=not (args.pilot or capturing),
        rebuild=False,
    )
    if not report.ok:
        print(render_preflight(report))
        print("\n  nothing was rebuilt. To fix the derived inputs:  interview prepare\n")
        return 2

    if recording and not capturing:
        if not current.complete:
            print(f"\n  cannot start: missing {', '.join(current.missing)}\n")
            return 2
        previous = lock
        lock = exp.build_lock(
            current, exp.compute_tracked(case_dir=case_dir), current_commit()
        )
        if previous is None or previous.lock_id != lock.lock_id:
            exp.write_lock(lock_path(config), lock)
            print(_experiment_recorded(lock, previous, lock_path(config)))
        measured = ()

    plan = load_slot_plan(role_dir / "slots.yaml")
    role_text = read_role_text(role_dir / "role.txt")
    resume_text = read_resume_text(case_dir / "cv.pdf")

    if args.smoke:
        run_kind, bucket = "smoke", "smoke"
    elif args.pilot:
        run_kind, bucket = "pilot", "pilot"
    else:
        run_kind, bucket = "measurement", f"iteration-{iteration:02d}"

    provider = build_provider(config, args.provider)
    store = SessionStore(ROOT / "evals" / "results" / bucket / f"session-{stamp()}.jsonl")

    tracked = exp.compute_tracked(case_dir=case_dir)
    tracked_drift = exp.compare_tracked(lock, tracked) if lock is not None else ()

    store.append(
        "run_metadata",
        run_kind=run_kind,
        iteration=iteration,
        provider=provider.name,
        model=provider.model,
        commit=current_commit(),
        role=relative(role_dir),
        case=relative(case_dir),
        slot_ids=[slot.id for slot in plan.slots],
        slot_plan_frozen_at=plan.frozen_at,
        total_seconds=budget.total_seconds,
        expected_answer_seconds=budget.expected_answer_seconds,
        max_followups_per_slot=int(config["interview"].get("max_followups_per_slot", 1)),
        experiment=(
            {
                "lock_id": lock.lock_id,
                "frozen_at": lock.frozen_at,
                **dict(lock.inputs.locked),
                "budget": dict(lock.inputs.budget),
                "tracked": dict(tracked),
            }
            if lock is not None
            else None
        ),
    )

    if tracked_drift:
        for drift in tracked_drift:
            store.append(
                "tracked_input_changed",
                field=drift.field,
                frozen=drift.frozen,
                current=drift.current,
            )

    interviewer = build_interviewer(
        iteration,
        TracingProvider(provider, store, context={"agent": f"interviewer-{iteration}"}),
        role_text,
        resume_text,
        budget,
        role_dir=role_dir,
        case_dir=case_dir,
        max_followups_per_slot=int(config["interview"].get("max_followups_per_slot", 1)),
        store=store,
    )

    if capturing:
        io = CapturingOpeningIO(
            inner=ConsoleIO(),
            target=opening_md,
            iteration=iteration,
            store=store,
            replacing=opening_frozen,
        )
    elif args.pilot:
        io = ConsoleIO()
        store.append("pilot_run", note="rehearsal; nothing frozen and not a measurement")
    else:
        io = FrozenOpeningIO(
            inner=SmokeIO() if args.smoke else ConsoleIO(),
            opening_text=load_fenced_blocks(opening_md)[0],
            opening_seconds=lock.opening_answer_seconds if lock else 0.0,
            store=store,
        )
        if args.smoke:
            store.append("smoke_run", note="canned candidate; not a measurement")

    print(f"\n  {run_kind}  |  iteration {iteration}  |  {provider.name}:{provider.model}")
    if lock is not None:
        print(f"  experiment {lock.lock_id}")
    print(f"  {budget.total_seconds // 60} minutes total - answers are not timed")
    if capturing:
        print("  no opening answer is frozen yet - your first answer becomes it, and every")
        print("  later rung of the ladder replays exactly that text")
    if args.pilot:
        print("  rehearsal: nothing is frozen and nothing is measured")
    if tracked_drift:
        print("  note: the response brief has changed since the lock; recorded, not blocked")
    print(f"  recording to {relative(store.path)}\n")

    interrupted = False
    outcome = None
    try:
        outcome = run_interview(interviewer=interviewer, io=io, store=store, budget=budget)
    except KeyboardInterrupt:
        interrupted = True
        asked = [e for e in store.events() if e.type == "question_asked"]
        answered = [e for e in store.events() if e.type == "answer_received"]
        spent = sum(float(e.data.get("generation_seconds") or 0) for e in asked)
        spent += sum(float(e.data.get("seconds_used") or 0) for e in answered)
        store.append(
            "interview_ended",
            reason="interrupted_by_candidate",
            elapsed_seconds=round(spent, 2),
            questions_asked=len(asked),
        )
        print("\n\n  interrupted - the partial session record was kept\n")

    if outcome is not None:
        print(f"\n{'=' * 72}")
        print(f"  ended: {outcome.end_reason}")
        print(f"  questions asked: {len(outcome.transcript.questions)}")
        print(f"  elapsed: {outcome.transcript.elapsed_seconds / 60:.1f} min")
        print(f"  record: {relative(store.path)}")
        print(f"{'=' * 72}\n")

    if capturing:
        if not getattr(io, "captured", False):
            print(
                "  no opening answer was given, so no experiment was recorded - the next"
                "\n  interview run --baseline will try again.\n"
            )
            return 130 if interrupted else 0
        if getattr(io, "replaced", None):
            print(_opening_discarded(io.replaced, opening_md))
        recorded = exp.compute_inputs(
            root=ROOT,
            role_dir=role_dir,
            case_dir=case_dir,
            plan=load_plan_or_none(role_dir),
            settings=config["interview"],
        )
        previous = lock
        lock = exp.build_lock(
            recorded,
            exp.compute_tracked(case_dir=case_dir),
            current_commit(),
            opening_answer_seconds=_opening_duration(store),
        )
        exp.write_lock(lock_path(config), lock)
        store.append("experiment_recorded", lock_id=lock.lock_id, frozen_at=lock.frozen_at)
        print(_experiment_recorded(lock, previous, lock_path(config)))

    return 130 if interrupted else 0


def _inputs_table(current: exp.ExperimentInputs, indent: str = "             ") -> list[str]:
    width = max(len(label) for label in exp.LOCKED_LABELS.values())
    rows = []
    for field, label in exp.LOCKED_LABELS.items():
        value = current.locked[field]
        shown = value if field in ("role_path", "case_path") else exp.digest_column(value)
        rows.append(f"{indent}{label:<{width}}  {shown}")
    return rows


def _opening_duration(store: SessionStore) -> float:
    """How long the opening answer took, read back from the record that just captured it."""
    for event in store.events():
        if event.type == "answer_received":
            return float(event.data.get("seconds_used") or 0.0)
    return 0.0


def _opening_discarded(answer: str, path: Path) -> str:
    """Said out loud, because discarding a stimulus is the thing section 4 watches for.

    A retake before any result has been seen is legitimate. A retake *after* seeing a
    result, repeated until the prediction confirms, is the offence the pre-registration
    exists to prevent - and the only thing separating the two is that this leaves a trace.
    """
    preview = answer.strip().splitlines()[0][:66]
    return "\n".join(
        [
            "",
            f"  discarded the opening answer frozen in {relative(path)}",
            f'    "{preview}..."',
            "",
            "  It stays readable in the session record of the run that captured it, which is",
            "  append-only. Nothing was deleted from evals/results/, and PREREGISTRATION.md",
            "  section 4 requires it to stay there.",
            "",
            "  Record this retake in CHANGELOG.md. A retake before any result has been seen is",
            "  a legitimate do-over; re-running until the prediction confirms is not, and the",
            "  record is the only thing that tells the two apart.",
            "",
        ]
    )


def _ladder_starts_at_baseline(iteration: int, current: exp.ExperimentInputs) -> str:
    """No experiment recorded, and this is not the rung that would record one.

    The baseline is what fixes the inputs the rest of the ladder is compared against, so
    starting anywhere else would leave every later rung with nothing to be measured
    against - and the comparison the whole project rests on could never be made.
    """
    lines = [
        "",
        f"  BLOCKED  iteration {iteration} has nothing to be measured against",
        "",
        "           No experiment has been recorded yet, and the baseline is what records",
        "           one: it fixes the inputs every later rung is compared against.",
        "           PREREGISTRATION.md section 4 depends on that comparison holding.",
        "",
        "           These inputs would be recorded as experiment",
        f"           {current.lock_id}:",
        "",
    ]
    lines += _inputs_table(current)
    lines += [
        "",
        "     fix:  interview run --baseline",
        "",
    ]
    return "\n".join(lines)


def _experiment_recorded(
    lock: exp.ExperimentLock, previous: exp.ExperimentLock | None, path: Path
) -> str:
    """Printed by the run that recorded the experiment, which is the first measured one."""
    lines = [
        "",
        f"  recorded experiment {lock.lock_id}  ->  {relative(path)}",
        "",
        "  Every later rung is compared against these inputs and will refuse to start if",
        "  one of them moves.",
        exp.render_lock(lock),
    ]
    if previous is not None:
        lines += [
            f"  This is a different experiment from {previous.lock_id}. The results already",
            "  recorded keep that lock and are never mixed with the new one - "
            "PREREGISTRATION.md",
            "  section 4 requires them to stay reported, not deleted. The ladder restarts here,",
            "  at the baseline.",
            "",
        ]
    return "\n".join(lines)


def assemble_prompt(iteration: int, role_dir: Path, case_dir: Path) -> tuple[str, str]:
    """Build the prompts a run would send, from the same files and the same code.

    Shared with the contamination test rather than reimplemented there, because a check
    that assembles the prompt its own way can only prove something about its own way.
    """
    if iteration == 0:
        system_template, user_template = load_prompt_pair(ROOT / "baseline" / "prompt.md")
        system = fill(
            system_template,
            role=read_role_text(role_dir / "role.txt"),
            resume=read_resume_text(case_dir / "cv.pdf"),
        )
        return system, user_template

    if iteration in RUNGS:
        return load_prompt_pair(ROOT / "solution" / "agent_instructions" / "interviewer.md")

    raise SystemExit(f"iteration {iteration} has no prompt to show yet")


def command_show_prompt(args) -> int:
    """Print exactly what the interviewer is sent, assembled from the real files.

    This exists because of the `role.txt` leak: its comment header, which told the model it
    was the subject of a study, reached every system prompt and was invisible without
    archaeology through a session record. Checking should take one command, so now it does.
    """
    config = load_config()
    role_dir, case_dir = resolve_paths(config, args)
    iteration = resolve_iteration(config, args)
    system, user_template = assemble_prompt(iteration, role_dir, case_dir)

    rule = "=" * 78
    print(f"\n{rule}\n  SYSTEM PROMPT - iteration {iteration}, {len(system)} characters")
    print("  Identical on every turn.")
    print(f"{rule}\n")
    print(system)
    print(f"\n{rule}\n  USER PROMPT TEMPLATE - {len(user_template)} characters")
    if iteration == 0:
        print("  Rebuilt every turn; <<TRANSCRIPT>> grows as the interview goes.")
    else:
        transcript_block = "filled" if RUNGS[iteration]["sees_transcript"] else "empty"
        print("  Rebuilt every turn from the competency the scheduler picked.")
        print(f"  <<TRANSCRIPT_BLOCK>> is {transcript_block} at this rung; "
              "<<FOLLOWUP_BLOCK>> is filled only on a follow-up.")
    print(f"{rule}\n")
    print(user_template)
    print()
    return 0


def command_measure(args) -> int:
    from evals.metrics import measure as measure_module

    arguments = list(args.sessions)
    if args.no_judge:
        arguments.append("--no-judge")
    return measure_module.main(arguments)


def command_branch(args) -> int:
    """Sample the next question k times at every turn boundary of a recorded interview.

    The variance measurement that costs no extra sitting: one real transcript is rewound
    to each decision point and the interviewer asked, repeatedly, what it would say next.
    A scheduler answers with one competency every time; a prompt answers with a spread.
    """
    import json as _json

    from evals.metrics import branching

    config = load_config()
    role_dir, case_dir = resolve_paths(config, args)
    session_path = Path(args.session)
    events = SessionStore(session_path).events()

    metadata = next((e.data for e in events if e.type == "run_metadata"), {})
    iteration = args.iteration if args.iteration is not None else int(metadata.get("iteration", 0))

    provider = build_provider(config, args.provider)
    try:
        branching.guard_sampling_provider(provider)
    except branching.NotSampling as error:
        import textwrap

        body = textwrap.fill(str(error), width=76, initial_indent="", subsequent_indent="")
        print("\n  BLOCKED  the provider would not actually sample\n")
        for line in body.splitlines():
            print(f"           {line}")
        print()
        return 2

    plan = load_slot_plan(role_dir / "slots.yaml")
    role_text = read_role_text(role_dir / "role.txt")
    resume_text = read_resume_text(case_dir / "cv.pdf")
    budget = budget_from(config)

    store = SessionStore(ROOT / "trajectories" / f"branch-{stamp()}.jsonl")
    store.append(
        "trajectory_started",
        agent="branch",
        purpose="sample the next question k times at each decision point",
        instructions="evals/metrics/branching.py",
        provider=provider.name,
        model=provider.model,
        commit=current_commit(),
        session=relative(session_path),
        iteration=iteration,
        samples=args.samples,
    )
    traced_provider = TracingProvider(store=store, inner=provider, context={"agent": "branch"})

    judge_provider = None
    if not args.no_judge:
        from evals.metrics.measure import build_judge

        judge_provider = build_judge(config)

    points = len(branching.decision_points(branching.transcript_from_record(events)))
    print(f"\n  branching  {relative(session_path)}  |  iteration {iteration}")
    print(f"  {points} decision points x {args.samples} samples "
          f"= {points * args.samples} model calls on {provider.name}:{provider.model}")
    print(f"  recording to {relative(store.path)}\n")

    result = branching.branch_session(
        events=events,
        plan=plan,
        build_interviewer=lambda: build_interviewer(
            iteration,
            traced_provider,
            role_text,
            resume_text,
            budget,
            role_dir=role_dir,
            case_dir=case_dir,
            max_followups_per_slot=int(config["interview"].get("max_followups_per_slot", 1)),
        ),
        samples=args.samples,
        judge_provider=judge_provider,
        store=store,
        on_progress=lambda at, total: print(f"    decision point {at}/{total}", flush=True),
    )

    print(branching.render(result))
    target = session_path.with_suffix(".branch.json")
    target.write_text(_json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  written to {target}\n")
    return 0


def command_report(args) -> int:
    from evals.metrics.report import main as report_main

    return report_main([])


def command_show(args) -> int:
    from solution.adapters.show import render_record

    print(render_record(Path(args.record)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="interview",
        description="A technical interviewer whose topic coverage is guaranteed by code.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def with_provider(sub):
        sub.add_argument("--provider", default=None, help="override the provider in config.yaml")
        return sub

    def with_paths(sub):
        sub.add_argument("--role", default=None, help="override the role directory")
        sub.add_argument("--case", default=None, help="override the case directory")
        return sub

    check = commands.add_parser("check", help="reach the configured model once")
    with_provider(check).set_defaults(handler=command_check)

    extract = commands.add_parser(
        "role-extract", help="draft a slot plan from role.txt for a human to review"
    )
    with_paths(with_provider(extract)).set_defaults(handler=command_role_extract)

    prepare = commands.add_parser(
        "prepare", help="rebuild the derived inputs (the only mutating command)"
    )
    with_paths(with_provider(prepare)).set_defaults(handler=command_prepare)

    run = commands.add_parser("run", help="conduct one interview")
    rung = run.add_mutually_exclusive_group()
    rung.add_argument("--iteration", type=int, default=None, help="which rung of the ladder")
    rung.add_argument("--baseline", action="store_true", help="the baseline rung")
    rung.add_argument("--solution", action="store_true", help="the finished system")
    run.add_argument(
        "--pilot",
        action="store_true",
        help=(
            "the opening answer is typed live rather than replayed, and the record goes to "
            "evals/results/pilot/. Never a measurement - it exists to produce the frozen "
            "opening answer and the response brief"
        ),
    )
    run.add_argument(
        "--restart",
        action="store_true",
        help=(
            "accept that an input changed and start a different experiment. Only valid "
            "with --baseline: a changed input means the ladder restarts from the "
            "beginning, since rungs measured against different inputs do not compare"
        ),
    )
    run.add_argument(
        "--smoke",
        type=int,
        default=0,
        metavar="SECONDS",
        help="verify the pipeline with a canned candidate over a short budget; never a measurement",
    )
    with_paths(with_provider(run)).set_defaults(handler=command_run)

    measure = commands.add_parser("measure", help="compute the metrics for one or more sessions")
    measure.add_argument("sessions", nargs="+", help="session record paths")
    measure.add_argument(
        "--no-judge", action="store_true", help="skip the judge; every question is left unresolved"
    )
    measure.set_defaults(handler=command_measure)

    branch = commands.add_parser(
        "branch",
        help="sample the next question k times at each decision point of a recorded interview",
    )
    branch.add_argument("session", help="path to a session record")
    branch.add_argument(
        "--samples", type=int, default=5, metavar="K", help="samples per decision point"
    )
    branch.add_argument(
        "--iteration",
        type=int,
        default=None,
        help="which interviewer to sample; defaults to the one the record was made with",
    )
    branch.add_argument(
        "--no-judge", action="store_true", help="skip the judge; every question is left unresolved"
    )
    with_paths(with_provider(branch)).set_defaults(handler=command_branch)

    report = commands.add_parser("report", help="baseline vs solution, as the results table")
    report.set_defaults(handler=command_report)

    show_prompt = commands.add_parser(
        "show-prompt", help="print exactly what the interviewer is sent"
    )
    rung_for_prompt = show_prompt.add_mutually_exclusive_group()
    rung_for_prompt.add_argument("--iteration", type=int, default=None)
    rung_for_prompt.add_argument("--baseline", action="store_true")
    rung_for_prompt.add_argument("--solution", action="store_true")
    with_paths(show_prompt).set_defaults(handler=command_show_prompt)

    show = commands.add_parser("show", help="render a session or trajectory record")
    show.add_argument("record", help="path to a .jsonl record")
    show.set_defaults(handler=command_show)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(arguments)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
