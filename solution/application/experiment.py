"""The identity of the experiment the ladder is measuring.

`preflight.py` asks whether the derived artifacts are in step with their inputs right now.
This asks whether the inputs are still the ones the ladder started with, across every run.

`PREREGISTRATION.md` section 4 lists what would invalidate the result - the slot plan
changing, the opening answer differing between runs, inputs moving mid-ladder. That was a
promise in prose; this is the mechanism. The first measured run hashes the inputs into a
lock file, every run after it compares, and a run whose inputs moved does not start. The
recovery is `interview run --baseline --restart`, which begins again at the first rung,
because rungs measured against different inputs do not form a comparison.

**Locked versus tracked.** Locked inputs stop a run. Exactly one input is tracked instead -
the response brief, whose own rule 1 lets it grow when a question reaches a fact it does
not hold. Locking it would forbid a legitimate, documented action; recording it makes the
records and the changelog agree by construction.

The lock id is derived from the locked content, so identical inputs yield the same id.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from solution.adapters.cv_redaction import file_digest
from solution.adapters.prompt_files import load_fenced_blocks
from solution.adapters.session_store import SessionStore
from solution.adapters.slot_plan import SlotPlan

LOCK_HEADER = """\
# The experiment this ladder is measuring. Written by the first measured run, checked by
# every run after it, never edited by hand.
#
# PREREGISTRATION.md section 4 lists what invalidates the result: the slot plan changing,
# the opening answer differing between runs, inputs moving mid-ladder. This file is how
# that promise is enforced rather than remembered.
#
# lock_id is derived from `inputs` and `budget`, so re-freezing identical inputs produces
# the same id, and changing any one of them mints a new experiment on its own.
#
# `tracked` is recorded and reported but never blocks a run - see solution/application/
# experiment.py for why the response brief sits there rather than under `inputs`.
"""

LOCKED_LABELS: Mapping[str, str] = {
    "role_path": "role directory",
    "case_path": "case directory",
    "role_sha256": "role.txt",
    "slot_plan_fingerprint": "slot plan",
    "cv_source_sha256": "cv-original.pdf",
    "resume_evidence_sha256": "resume-evidence.yaml",
    "opening_answer_sha256": "opening answer",
}

BUDGET_LABELS: Mapping[str, str] = {
    "total_seconds": "total_seconds",
    "expected_answer_seconds": "expected_answer_seconds",
    "turn_overhead_seconds": "turn_overhead_seconds",
    "max_slots": "max_slots",
}

CONSEQUENCE: Mapping[str, str] = {
    "role_path": "the interview would be about a different job description",
    "case_path": "the interview would be with a different candidate",
    "role_sha256": "the job description the slot plan was derived from has changed",
    "slot_plan_fingerprint": (
        "the slot plan is the denominator of coverage - changing it means the runs before "
        "and after are measured over different competencies"
    ),
    "cv_source_sha256": "the candidate is not the one the earlier runs interviewed",
    "resume_evidence_sha256": (
        "has_experience decides behavioural versus situational phrasing, so the question "
        "type would differ between runs"
    ),
    "opening_answer_sha256": (
        "the opening answer is the controlled stimulus - if it differs between runs, a "
        "coverage difference can no longer be attributed to the interviewer"
    ),
    "budget": "the time budget is held constant across every rung",
}

MISSING = "(absent)"


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _digest_file_if_present(path: Path) -> str:
    return file_digest(path) if path.exists() else MISSING


def _digest_first_fenced_block(path: Path) -> str:
    """The frozen opening answer is the *block*, not the file that documents it.

    Hashing the file would make a typo in the surrounding prose read as a changed
    stimulus, and the stimulus is the only thing the lock cares about here.
    """
    if not path.exists():
        return MISSING
    blocks = load_fenced_blocks(path)
    return _digest_text(blocks[0]) if blocks else MISSING


@dataclass(frozen=True, slots=True)
class ExperimentInputs:
    """Everything PREREGISTRATION.md section 1 fixes, reduced to digests."""

    role_path: str
    case_path: str
    role_sha256: str
    slot_plan_fingerprint: str
    cv_source_sha256: str
    resume_evidence_sha256: str
    opening_answer_sha256: str
    budget: Mapping[str, int]

    @property
    def locked(self) -> Mapping[str, str]:
        return {field: getattr(self, field) for field in LOCKED_LABELS}

    @property
    def lock_id(self) -> str:
        material = json.dumps(
            {"inputs": dict(self.locked), "budget": dict(sorted(self.budget.items()))},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]

    @property
    def complete(self) -> bool:
        """False when an input the lock covers does not exist yet.

        A lock over an absent opening answer would be a lock over nothing, so `freeze`
        refuses rather than recording `(absent)` as if it were a value.
        """
        return MISSING not in self.locked.values()

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(
            LOCKED_LABELS[field]
            for field, value in self.locked.items()
            if value == MISSING
        )


@dataclass(frozen=True, slots=True)
class ExperimentLock:
    lock_id: str
    frozen_at: str
    commit: str
    inputs: ExperimentInputs
    tracked: Mapping[str, str]
    opening_answer_seconds: float = 0.0

    def to_document(self) -> dict[str, Any]:
        return {
            "lock_id": self.lock_id,
            "frozen_at": self.frozen_at,
            "commit": self.commit,
            "role": self.inputs.role_path,
            "case": self.inputs.case_path,
            "inputs": {
                field: value
                for field, value in self.inputs.locked.items()
                if field not in ("role_path", "case_path")
            },
            "budget": dict(self.inputs.budget),
            "opening_answer_seconds": round(self.opening_answer_seconds, 2),
            "tracked": dict(self.tracked),
        }


@dataclass(frozen=True, slots=True)
class Drift:
    """One input that no longer matches the lock."""

    field: str
    label: str
    frozen: str
    current: str

    @property
    def consequence(self) -> str:
        return CONSEQUENCE.get(self.field, "")


def compute_inputs(
    *,
    root: Path,
    role_dir: Path,
    case_dir: Path,
    plan: SlotPlan | None,
    settings: Mapping[str, Any],
) -> ExperimentInputs:
    """Hash the current state of everything the lock covers.

    `plan` is optional because the caller may not have been able to load it - a malformed
    plan is preflight's problem to report, and this should not raise on the way past.
    """
    return ExperimentInputs(
        role_path=_relative(root, role_dir),
        case_path=_relative(root, case_dir),
        role_sha256=_digest_file_if_present(role_dir / "role.txt"),
        slot_plan_fingerprint=plan.fingerprint if plan is not None else MISSING,
        cv_source_sha256=_digest_file_if_present(case_dir / "cv-original.pdf"),
        resume_evidence_sha256=_digest_file_if_present(case_dir / "resume-evidence.yaml"),
        opening_answer_sha256=_digest_first_fenced_block(case_dir / "opening-answer.md"),
        budget={
            "total_seconds": int(settings["total_seconds"]),
            "expected_answer_seconds": int(settings["expected_answer_seconds"]),
            "turn_overhead_seconds": int(settings["turn_overhead_seconds"]),
            "max_slots": int(settings.get("max_slots", 6)),
        },
    )


def compute_tracked(*, case_dir: Path) -> dict[str, str]:
    """Recorded with every run, never enforced. See the module docstring."""
    return {"response_brief_sha256": _digest_file_if_present(case_dir / "response-brief.md")}


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def build_lock(
    inputs: ExperimentInputs,
    tracked: Mapping[str, str],
    commit: str,
    opening_answer_seconds: float = 0.0,
) -> ExperimentLock:
    return ExperimentLock(
        lock_id=inputs.lock_id,
        frozen_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        commit=commit,
        inputs=inputs,
        tracked=dict(tracked),
        opening_answer_seconds=float(opening_answer_seconds),
    )


def write_lock(path: Path, lock: ExperimentLock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        LOCK_HEADER + yaml.safe_dump(lock.to_document(), sort_keys=False),
        encoding="utf-8",
    )


def load_lock(path: Path) -> ExperimentLock | None:
    if not path.exists():
        return None
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    recorded = document.get("inputs") or {}
    inputs = ExperimentInputs(
        role_path=str(document.get("role", "")),
        case_path=str(document.get("case", "")),
        role_sha256=str(recorded.get("role_sha256", MISSING)),
        slot_plan_fingerprint=str(recorded.get("slot_plan_fingerprint", MISSING)),
        cv_source_sha256=str(recorded.get("cv_source_sha256", MISSING)),
        resume_evidence_sha256=str(recorded.get("resume_evidence_sha256", MISSING)),
        opening_answer_sha256=str(recorded.get("opening_answer_sha256", MISSING)),
        budget={k: int(v) for k, v in (document.get("budget") or {}).items()},
    )
    return ExperimentLock(
        lock_id=str(document.get("lock_id", "")),
        frozen_at=str(document.get("frozen_at", "")),
        commit=str(document.get("commit", "")),
        inputs=inputs,
        tracked=dict(document.get("tracked") or {}),
        opening_answer_seconds=float(document.get("opening_answer_seconds") or 0.0),
    )


def compare(lock: ExperimentLock, current: ExperimentInputs) -> tuple[Drift, ...]:
    """Every locked input that has moved since the lock was written."""
    drifts = [
        Drift(
            field=field,
            label=label,
            frozen=lock.inputs.locked[field],
            current=current.locked[field],
        )
        for field, label in LOCKED_LABELS.items()
        if lock.inputs.locked[field] != current.locked[field]
    ]

    frozen_budget, now_budget = dict(lock.inputs.budget), dict(current.budget)
    if frozen_budget != now_budget:
        drifts.append(
            Drift(
                field="budget",
                label="time budget",
                frozen=_render_budget(frozen_budget),
                current=_render_budget(now_budget),
            )
        )
    return tuple(drifts)


def compare_tracked(
    lock: ExperimentLock, current: Mapping[str, str]
) -> tuple[Drift, ...]:
    return tuple(
        Drift(
            field=field,
            label=field.removesuffix("_sha256").replace("_", " "),
            frozen=lock.tracked.get(field, MISSING),
            current=value,
        )
        for field, value in current.items()
        if lock.tracked.get(field, MISSING) != value
    )


def _render_budget(budget: Mapping[str, int]) -> str:
    return " ".join(f"{BUDGET_LABELS.get(k, k)}={v}" for k, v in sorted(budget.items()))


def measured_runs_for(lock_id: str, results_dir: Path) -> tuple[str, ...]:
    """The iteration buckets holding a measured run of this experiment.

    Identity, not location: each session record stamps the lock it ran under, so a result
    is attributed to the experiment that produced it even if the directory is moved. A run
    that was interrupted still counts - it consumed the candidate and it is in the record,
    so the experiment is under way whether or not that run finished.
    """
    if not results_dir.exists():
        return ()
    found: set[str] = set()
    for directory in sorted(results_dir.glob("iteration-*")):
        if not directory.is_dir():
            continue
        for session in sorted(directory.glob("session-*.jsonl")):
            if _session_lock_id(session) == lock_id:
                found.add(directory.name)
                break
    return tuple(sorted(found))


def _session_lock_id(session: Path) -> str | None:
    """The experiment a session belongs to, from whichever event carries it.

    Two shapes, because of when the lock exists. A run that joins an experiment already
    recorded stamps it into `run_metadata` before the first question. The baseline run that
    *creates* an experiment cannot - the opening answer identifying it does not exist until
    the candidate gives it - so it appends `experiment_recorded` at the end instead.

    Reading only the first shape made exactly the run that starts a ladder invisible to the
    guard meant to protect that ladder, which is the one run it could least afford to miss.
    """
    for event in SessionStore(session).events():
        if event.type == "run_metadata":
            recorded = (event.data.get("experiment") or {}).get("lock_id")
            if recorded:
                return recorded
        elif event.type == "experiment_recorded":
            return event.data.get("lock_id")
    return None


def digest_column(value: str) -> str:
    """A digest shortened for a table, and never an absent value dressed up as one."""
    return value if value == MISSING else f"{value[:8]}…"


def render_drift(
    lock: ExperimentLock,
    drifts: Sequence[Drift],
    measured_runs: Sequence[str],
    current: ExperimentInputs,
) -> str:
    """The block a measured run prints when an input has moved.

    Every locked input is listed, not only the changed ones: a reader checking whether the
    experiment still holds wants to see the whole tuple, and a table with one row is easy
    to mistake for the only thing that was checked.
    """
    changed = {drift.field for drift in drifts}
    runs = ", ".join(measured_runs) or "none yet"
    if len(drifts) == 1:
        headline = f"{drifts[0].label} no longer matches the frozen experiment"
    else:
        named = ", ".join(drift.label for drift in drifts)
        headline = f"{named} no longer match the frozen experiment"

    lines = [
        "",
        f"  BLOCKED  {headline}",
        "",
        f"           experiment {lock.lock_id}, frozen {lock.frozen_at}",
        f"           measured runs: {runs}",
        "",
    ]

    width = max(len(label) for label in LOCKED_LABELS.values())
    for field, label in LOCKED_LABELS.items():
        frozen_value = lock.inputs.locked[field]
        current_value = current.locked[field]
        if field in ("role_path", "case_path"):
            frozen_column, current_column = frozen_value, current_value
        else:
            frozen_column = digest_column(frozen_value)
            current_column = digest_column(current_value)
        mark = "CHANGED" if field in changed else "ok"
        lines.append(
            f"           {label:<{width}}  frozen {frozen_column:<26}"
            f"now {current_column:<26}{mark}"
        )

    budget_mark = "CHANGED" if "budget" in changed else "ok"
    lines.append(
        f"           {'time budget':<{width}}  "
        f"{_render_budget(current.budget)}  {budget_mark}"
    )
    lines.append("")

    for drift in drifts:
        if drift.consequence:
            lines.append(f"           {drift.label}: {drift.consequence}")
    lines += [
        "",
        "           PREREGISTRATION.md section 4 lists this as invalidating: the",
        "           runs must be against identical inputs.",
        "",
        "     fix:  restore what this experiment was frozen against, or accept that this",
        "           is a different experiment and start the ladder again from its",
        "           first rung - rungs measured against different inputs do not",
        "           compare, so there is no way to continue from the middle:",
        "",
        "               interview run --baseline --restart",
        "",
        f"           The existing results keep lock {lock.lock_id} and are never mixed",
        "           with the new one. Section 4 requires them to stay reported, not",
        "           deleted.",
        "",
    ]
    return "\n".join(lines)


def render_lock(lock: ExperimentLock, measured_runs: Sequence[str] = ()) -> str:
    """A human-readable summary of the experiment currently in force."""
    runs = ", ".join(measured_runs) or "none yet"
    width = max(len(label) for label in LOCKED_LABELS.values())
    lines = [
        "",
        f"  experiment  {lock.lock_id}",
        f"  frozen      {lock.frozen_at}  at commit {lock.commit}",
        f"  runs        {runs}",
        "",
    ]
    for field, label in LOCKED_LABELS.items():
        value = lock.inputs.locked[field]
        shown = value if field in ("role_path", "case_path") else digest_column(value)
        lines.append(f"    {label:<{width}}  {shown}")
    lines.append(f"    {'time budget':<{width}}  {_render_budget(lock.inputs.budget)}")
    for field, value in lock.tracked.items():
        label = field.removesuffix("_sha256").replace("_", " ")
        lines.append(f"    {label:<{width}}  {digest_column(value)}  (tracked, not locked)")
    lines.append("")
    return "\n".join(lines)
