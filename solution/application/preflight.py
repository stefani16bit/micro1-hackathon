"""Everything that must hold before an interview starts.

    interview run   (the preflight is read-only there)
    interview prepare   (the only command that rebuilds anything)

Three artifacts are derived from inputs a person edits: the redacted CV, the frozen slot
plan, and the résumé evidence. When they fall out of step the failure is silence rather
than a crash - swap the CV and the evidence file goes on describing the previous one, so
the interviewer asks situational questions about experience the candidate now has.

The rule is not "regenerate everything", because regenerating the slot plan would move the
denominator of the primary metric:

- **Derived and safe** - the redacted CV. Deterministic, carries no experimental meaning,
  rebuilt whenever the original changes.
- **Frozen** - the slot plan and the résumé evidence. Staleness is *detected* and the run
  stops with the command that fixes it. Re-freezing is a decision, and a decision needs a
  person.

Identity is by content, never by timestamp. `rebuild` decides whether this may touch
anything at all: `prepare` passes True, `run` passes False and stops instead.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import yaml

from solution.adapters.cv_redaction import file_digest, recorded_source_digest, redact
from solution.adapters.prompt_files import load_fenced_blocks
from solution.adapters.slot_plan import SlotPlanError, load_slot_plan


EVIDENCE_STALE = "evidence_stale"
DERIVED_STALE = "derived_stale"


@dataclass(frozen=True, slots=True)
class Problem:
    what: str
    why: str
    fix: str
    kind: str = ""


@dataclass(frozen=True, slots=True)
class Preflight:
    derived: tuple[str, ...] = ()
    problems: tuple[Problem, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def needs_evidence_refresh(self) -> bool:
        """True when only the résumé evidence is out of step.

        Regenerating it is safe *before* the first measured run and destructive after one:
        the evidence is an input held constant across every rung, so changing
        it midway would mean two halves of the ladder ran against different inputs. The
        caller decides which situation it is in; this only reports the shape.
        """
        return bool(self.problems) and all(p.kind == EVIDENCE_STALE for p in self.problems)


def prepare(
    *,
    role_dir: Path,
    case_dir: Path,
    require_frozen_opening: bool = True,
    rebuild: bool = True,
) -> Preflight:
    """Check the inputs; rebuild what is safe to rebuild, report what is not.

    With `rebuild=True` the redacted CV is regenerated here rather than reported as a
    problem, because regenerating it is deterministic and changes nothing about the
    experiment. With `rebuild=False` nothing on disk is touched and the same condition is
    reported instead - that is how `interview run` stays read-only.
    """
    derived: list[str] = []
    problems: list[Problem] = []

    role_txt = role_dir / "role.txt"
    slots_yaml = role_dir / "slots.yaml"
    original_cv = case_dir / "cv-original.pdf"
    redacted_cv = case_dir / "cv.pdf"
    evidence_yaml = case_dir / "resume-evidence.yaml"
    opening_md = case_dir / "opening-answer.md"

    role_digest: str | None = None
    plan = None

    if not role_txt.exists():
        problems.append(
            Problem(
                what=f"{role_txt} is missing",
                why="the interview has no job description to be about",
                fix="add the job description at that path",
            )
        )
    else:
        role_digest = file_digest(role_txt)

    if not slots_yaml.exists():
        problems.append(
            Problem(
                what=f"{slots_yaml} is missing",
                why="the slot plan is the denominator of the primary metric",
                fix=(
                    "interview role-extract   then review slots.draft.yaml and "
                    "rename it to slots.yaml"
                ),
            )
        )
    else:
        try:
            plan = load_slot_plan(slots_yaml)
        except SlotPlanError as error:
            problems.append(
                Problem(
                    what=f"{slots_yaml} is not usable",
                    why=str(error),
                    fix="correct the file; the loader is strict because a malformed plan "
                    "would distort every number that follows",
                )
            )

    if plan is not None and role_digest is not None:
        recorded = plan.provenance.get("role_sha256")
        if recorded is None:
            problems.append(
                Problem(
                    what=f"{slots_yaml} records no provenance",
                    why="there is no way to tell which job description it was frozen against",
                    fix=f"add  provenance: {{role_sha256: {role_digest}}}  after confirming "
                    "the plan really was built from the current role.txt",
                )
            )
        elif recorded != role_digest:
            problems.append(
                Problem(
                    what="the slot plan was frozen against a different role.txt",
                    why=(
                        "role.txt has changed since the plan was frozen. Re-extracting the "
                        "plan would change the competencies coverage is measured over, so "
                        "results from before and after would not be comparable - this is "
                        "not something to fix silently"
                    ),
                    fix=(
                        "either restore the original role.txt, or re-extract "
                        "(interview role-extract), review, re-freeze, and record the "
                        "change in PREREGISTRATION.md and CHANGELOG.md before running "
                        "anything"
                    ),
                )
            )

    cv_digest: str | None = None

    if not original_cv.exists():
        problems.append(
            Problem(
                what=f"{original_cv} is missing",
                why="the redacted CV is derived from it, and it is never committed",
                fix=f"put the candidate's CV at {original_cv}",
            )
        )
    else:
        cv_digest = file_digest(original_cv)
        if recorded_source_digest(redacted_cv) != cv_digest and not rebuild:
            problems.append(
                Problem(
                    what=(
                        f"{redacted_cv.name} is missing"
                        if not redacted_cv.exists()
                        else f"{redacted_cv.name} was derived from a different original"
                    ),
                    why=(
                        "the interview reads the redacted CV, so running now would put a "
                        "different CV in front of the interviewer than the one on disk"
                    ),
                    fix="interview prepare",
                    kind=DERIVED_STALE,
                )
            )
        elif recorded_source_digest(redacted_cv) != cv_digest:
            result = redact(original_cv, redacted_cv)
            still_readable = tuple(
                item for item in result.removed if item in _text_of(redacted_cv)
            )
            if still_readable:
                problems.append(
                    Problem(
                        what="redaction did not remove everything it found",
                        why=f"still readable in cv.pdf: {list(still_readable)}",
                        fix="do not commit cv.pdf; investigate solution/adapters/cv_redaction.py",
                    )
                )
            else:
                removed = ", ".join(result.removed) or "nothing matched"
                derived.append(f"cv.pdf rebuilt from cv-original.pdf (removed: {removed})")

    if not evidence_yaml.exists():
        problems.append(
            Problem(
                what=f"{evidence_yaml} is missing",
                why="has_experience per slot decides behavioural vs situational phrasing",
                fix="interview prepare",
                kind=EVIDENCE_STALE,
            )
        )
    else:
        document = yaml.safe_load(evidence_yaml.read_text(encoding="utf-8")) or {}
        provenance = document.get("provenance") or {}
        recorded_cv = provenance.get("cv_source_sha256")
        recorded_plan = provenance.get("slot_plan_fingerprint")

        if cv_digest is not None and recorded_cv != cv_digest:
            problems.append(
                Problem(
                    what="the résumé evidence describes a different CV",
                    why=(
                        "it was resolved against another version of cv-original.pdf. Running "
                        "on it would ask situational questions about experience this "
                        "candidate has, and behavioural ones about experience they do not"
                    ),
                    fix="interview prepare",
                    kind=EVIDENCE_STALE,
                )
            )
        if plan is not None and recorded_plan != plan.fingerprint:
            problems.append(
                Problem(
                    what="the résumé evidence was resolved against a different slot plan",
                    why="its slots no longer match the frozen plan the interview will use",
                    fix="interview prepare",
                    kind=EVIDENCE_STALE,
                )
            )

    if require_frozen_opening:
        frozen = opening_md.exists() and bool(load_fenced_blocks(opening_md))
        if not frozen:
            problems.append(
                Problem(
                    what=f"{opening_md} holds no frozen opening answer",
                    why="the opening answer is the controlled stimulus; it must be "
                    "identical in every measured run",
                    fix="interview run --baseline   captures it: the candidate answers "
                    "the first question as they answer any other, and it is frozen at "
                    "the moment it is given. Nothing to paste, and nothing to run first.",
                )
            )

    return Preflight(derived=tuple(derived), problems=tuple(problems))


def _text_of(pdf: Path) -> str:
    import pymupdf

    with pymupdf.open(pdf) as document:
        return "\n".join(page.get_text() for page in document)


def render(report: Preflight) -> str:
    lines: list[str] = []
    for item in report.derived:
        lines.append(f"  regenerated  {item}")
    for problem in report.problems:
        lines += [
            "",
            f"  BLOCKED  {problem.what}",
            f"           {problem.why}",
            f"     fix:  {problem.fix}",
        ]
    if report.ok and not report.derived:
        lines.append("  everything is in step")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[2]
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    report = prepare(
        role_dir=root / config["role"],
        case_dir=root / config["case"],
        require_frozen_opening="--pilot" not in arguments,
    )
    print(render(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
