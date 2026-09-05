"""The CLI is where the separation of concerns is actually enforced.

Three properties are worth a test rather than a docstring: `run` never rebuilds anything,
the baseline run records the experiment the rest of the ladder is compared against, and a
changed input restarts the ladder rather than continuing it. All three are the sort of
thing that decays silently the moment someone adds a convenience.
"""

import pymupdf
import pytest
import yaml

from solution.adapters import cli
from solution.adapters.candidate_io import ConsoleIO, FrozenOpeningIO
from solution.adapters.prompt_files import load_fenced_blocks
from solution.adapters.session_store import SessionStore
from solution.application import experiment as exp
from solution.application.runner import Interviewer
from solution.domain.transcript import Answer, Utterance


class OneQuestionInterviewer(Interviewer):
    """Asks the opening, then has nothing more to say."""

    label = "one-question"

    def __init__(self):
        self._asked = False

    def next_utterance(self, transcript):
        if self._asked:
            return None
        self._asked = True
        return Utterance(text="Tell me about yourself.", kind="opening", slot_id=None)

SLOTS = {
    "role": "fullstack",
    "source": "test",
    "frozen_at": "2026-08-30",
    "slots": [
        {"id": "frontend", "name": "frontend", "kind": "language_framework", "rank": 1,
         "keywords": ["react", "frontend"]},
        {"id": "cloud", "name": "cloud", "kind": "infra_ops", "rank": 2,
         "keywords": ["aws", "cloud"]},
    ],
}

CONFIG = {
    "provider": {
        "name": "ollama",
        "ollama": {"base_url": "http://localhost:11434", "model": "test-model"},
        "claude_cli": {"binary": "claude", "model": "test-model"},
    },
    "judge": {"provider": "ollama"},
    "interview": {
        "total_seconds": 1500,
        "expected_answer_seconds": 120,
        "turn_overhead_seconds": 15,
        "max_followups_per_slot": 1,
        "max_slots": 6,
    },
    "iterations": {"baseline": 0, "solution": 10},
    "role": "roles/fullstack",
    "case": "evals/cases/case-01",
    "experiment_lock": "evals/experiment-lock.yaml",
}


def write_plan(role_dir, **overrides):
    """The plan records the digest of the role it was frozen against, as the real one does."""
    from solution.adapters.cv_redaction import file_digest

    plan = {
        **SLOTS,
        **overrides,
        "provenance": {"role_sha256": file_digest(role_dir / "role.txt")},
    }
    (role_dir / "slots.yaml").write_text(yaml.safe_dump(plan), encoding="utf-8")


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A miniature copy of the repository, with the CLI pointed at it."""
    (tmp_path / "roles" / "fullstack").mkdir(parents=True)
    (tmp_path / "evals" / "cases" / "case-01").mkdir(parents=True)
    (tmp_path / "baseline").mkdir()

    role_dir = tmp_path / "roles" / "fullstack"
    case_dir = tmp_path / "evals" / "cases" / "case-01"

    (tmp_path / "config.yaml").write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    (role_dir / "role.txt").write_text("A fullstack role. React. AWS.", encoding="utf-8")
    write_plan(role_dir)

    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Alice Example  React and AWS")
    document.save(case_dir / "cv-original.pdf")
    document.close()

    (case_dir / "opening-answer.md").write_text(
        "# opening\n\n```\nI am a software engineer.\n```\n", encoding="utf-8"
    )
    (case_dir / "response-brief.md").write_text("facts by competency\n", encoding="utf-8")
    (tmp_path / "baseline" / "prompt.md").write_text(
        "# prompt\n\n```\nYou interview. <<ROLE>> <<RESUME>>\n```\n\n"
        "```\n<<TRANSCRIPT>> <<ELAPSED_MINUTES>>\n```\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(exp, "ROOT", tmp_path, raising=False)
    return tmp_path, role_dir, case_dir


def write_evidence(role_dir, case_dir):
    from solution.adapters.cv_redaction import file_digest
    from solution.adapters.slot_plan import load_slot_plan

    (case_dir / "resume-evidence.yaml").write_text(
        yaml.safe_dump(
            {
                "provenance": {
                    "cv_source_sha256": file_digest(case_dir / "cv-original.pdf"),
                    "slot_plan_fingerprint": load_slot_plan(role_dir / "slots.yaml").fingerprint,
                },
                "evidence": [
                    {"slot_id": "frontend", "has_experience": False, "evidence_quote": ""}
                ],
            }
        ),
        encoding="utf-8",
    )


def stub_interview(monkeypatch):
    """Let a run reach the interview, then stop it there.

    These tests are about what happens *before* the first question, so the interview
    itself is replaced. KeyboardInterrupt is what the runner already treats as a candidate
    walking out, so the session record is left exactly as a real one would be.
    """
    reached = {}

    def refuse(**kwargs):
        reached["ran"] = True
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_interview", refuse)
    return reached


def stub_any_rung(monkeypatch):
    """Let a rung that is not built yet still be dispatched.

    Only iteration 0 exists so far, and `build_interviewer` says so - correctly. These
    tests are about the experiment machinery that runs before any interviewer is chosen,
    so the choice itself is stubbed out rather than the ladder being faked into existence.
    """
    monkeypatch.setattr(cli, "build_interviewer", lambda *args, **kwargs: object())


def answer_typed(monkeypatch, text, seconds=90.0):
    """Make the console return one typed answer and the interviewer ask one question."""
    answers = iter([text])

    def collect(self):
        return Answer(text=next(answers), seconds_used=seconds)

    monkeypatch.setattr(ConsoleIO, "collect", collect)
    monkeypatch.setattr(ConsoleIO, "present", lambda self, text: None)
    monkeypatch.setattr(cli, "build_interviewer", lambda *a, **k: OneQuestionInterviewer())


def record_replayed_opening(monkeypatch):
    """Capture whatever FrozenOpeningIO serves as the opening answer."""
    seen = {}
    original = FrozenOpeningIO.collect

    def collect(self):
        answer = original(self)
        seen.setdefault("text", answer.text)
        seen.setdefault("seconds", answer.seconds_used)
        return answer

    monkeypatch.setattr(FrozenOpeningIO, "collect", collect)
    monkeypatch.setattr(ConsoleIO, "present", lambda self, text: None)
    monkeypatch.setattr(cli, "build_interviewer", lambda *a, **k: OneQuestionInterviewer())
    return seen


def latest_session(root, bucket):
    return sorted((root / "evals" / "results" / bucket).glob("session-*.jsonl"))[-1]


def record_measured_run(root, bucket, lock_id):
    """A finished measured run of `bucket`, as the runner would have left it."""
    store = SessionStore(root / "evals" / "results" / bucket / f"session-{bucket}.jsonl")
    store.append(
        "run_metadata",
        run_kind="measurement",
        iteration=int(bucket.rsplit("-", 1)[1]),
        experiment={"lock_id": lock_id},
    )
    store.append("interview_ended", reason="all_slots_covered")


def ready(project):
    """A case whose derived inputs are in step, with nothing measured yet."""
    root, role_dir, case_dir = project
    write_evidence(role_dir, case_dir)
    cli.main(["prepare"])
    return root, role_dir, case_dir


def lock_of(root):
    return exp.load_lock(root / "evals" / "experiment-lock.yaml")


class TestTheParser:
    def test_every_command_resolves_to_a_handler(self):
        parser = cli.build_parser()
        for command in ("check", "role-extract", "prepare", "run", "measure", "report", "show"):
            args = parser.parse_args([command] + (["x"] if command in ("measure", "show") else []))
            assert callable(args.handler)

    def test_there_is_no_freeze_command(self):
        """Recording the experiment is what the baseline run does. A step that can only be
        forgotten, never usefully skipped, is a trap rather than a checkpoint."""
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(["freeze"])

    def test_a_rung_can_be_named_or_numbered(self):
        parser = cli.build_parser()
        assert parser.parse_args(["run", "--baseline"]).baseline is True
        assert parser.parse_args(["run", "--iteration", "4"]).iteration == 4

    def test_the_rung_flags_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(["run", "--baseline", "--solution"])

    def test_baseline_and_solution_resolve_from_config(self):
        parser = cli.build_parser()
        config = {"iterations": {"baseline": 0, "solution": 10}}
        assert cli.resolve_iteration(config, parser.parse_args(["run", "--baseline"])) == 0
        assert cli.resolve_iteration(config, parser.parse_args(["run", "--solution"])) == 10

    def test_a_run_without_a_rung_says_so(self):
        args = cli.build_parser().parse_args(["run"])
        with pytest.raises(SystemExit, match="which rung"):
            cli.resolve_iteration({"iterations": {}}, args)


class TestPrepareIsTheOnlyMutatingCommand:
    def test_prepare_builds_the_redacted_cv(self, project, capsys):
        root, role_dir, case_dir = project
        write_evidence(role_dir, case_dir)

        assert cli.main(["prepare"]) == 0
        assert (case_dir / "cv.pdf").exists()
        assert "cv.pdf rebuilt" in capsys.readouterr().out

    def test_run_never_rebuilds_the_cv_it_stops_instead(self, project, capsys):
        """The whole reason `prepare` exists: an interview that rewrites its own inputs is
        a measurement nobody can reason about afterwards.

        Run as a pilot so the experiment machinery is not what stops it - this is about
        the preflight being read-only.
        """
        root, role_dir, case_dir = project
        write_evidence(role_dir, case_dir)

        assert cli.main(["run", "--baseline", "--pilot"]) == 2
        assert not (case_dir / "cv.pdf").exists()
        out = capsys.readouterr().out
        assert "cv.pdf is missing" in out
        assert "interview prepare" in out

    def test_it_refuses_once_the_experiment_has_measured_runs(
        self, project, monkeypatch, capsys
    ):
        root, role_dir, case_dir = ready(project)
        stub_interview(monkeypatch)
        cli.main(["run", "--baseline"])
        record_measured_run(root, "iteration-00", lock_of(root).lock_id)
        capsys.readouterr()

        assert cli.main(["prepare"]) == 2
        out = capsys.readouterr().out
        assert "already has measured runs" in out
        assert "iteration-00" in out
        assert "interview run --baseline --restart" in out


class TestTheBaselineRecordsTheExperiment:
    def test_the_first_measured_run_writes_the_lock(self, project, monkeypatch, capsys):
        root, role_dir, case_dir = ready(project)
        reached = stub_interview(monkeypatch)
        capsys.readouterr()

        assert cli.main(["run", "--baseline"]) == 130
        assert reached["ran"] is True

        lock = lock_of(root)
        assert lock is not None
        assert lock.inputs.complete
        assert lock.tracked["response_brief_sha256"]
        assert "recorded experiment" in capsys.readouterr().out

    def test_a_later_rung_reuses_the_lock_rather_than_rewriting_it(
        self, project, monkeypatch, capsys
    ):
        root, role_dir, case_dir = ready(project)
        stub_interview(monkeypatch)
        stub_any_rung(monkeypatch)
        cli.main(["run", "--baseline"])
        before = (root / "evals" / "experiment-lock.yaml").read_bytes()
        record_measured_run(root, "iteration-00", lock_of(root).lock_id)
        capsys.readouterr()

        assert cli.main(["run", "--iteration", "1"]) == 130
        assert (root / "evals" / "experiment-lock.yaml").read_bytes() == before
        assert "recorded experiment" not in capsys.readouterr().out

    def test_a_rung_other_than_the_baseline_will_not_start_a_ladder(self, project, capsys):
        """The baseline fixes the inputs; starting elsewhere would leave every later rung
        with nothing to be compared against."""
        root, role_dir, case_dir = ready(project)
        capsys.readouterr()

        assert cli.main(["run", "--iteration", "3"]) == 2
        out = capsys.readouterr().out
        assert "nothing to be measured against" in out
        assert "interview run --baseline" in out
        assert not (root / "evals" / "experiment-lock.yaml").exists()

    def test_it_shows_the_tuple_it_would_record(self, project, capsys):
        root, role_dir, case_dir = ready(project)
        capsys.readouterr()

        cli.main(["run", "--iteration", "3"])
        out = capsys.readouterr().out
        for label in exp.LOCKED_LABELS.values():
            assert label in out

    def test_an_incomplete_case_that_is_not_the_opening_still_stops(self, project, capsys):
        """A missing opening is now repaired by capturing one. A missing CV is not."""
        root, role_dir, case_dir = ready(project)
        (case_dir / "cv-original.pdf").unlink()
        capsys.readouterr()

        assert cli.main(["run", "--baseline"]) == 2
        assert not (root / "evals" / "experiment-lock.yaml").exists()

    def test_a_pilot_records_nothing(self, project, monkeypatch):
        """The pilot is what produces the opening answer the experiment is recorded over,
        so it necessarily runs before there is anything to record."""
        root, role_dir, case_dir = ready(project)
        reached = stub_interview(monkeypatch)

        assert cli.main(["run", "--baseline", "--pilot"]) == 130
        assert reached["ran"] is True
        assert not (root / "evals" / "experiment-lock.yaml").exists()

    def test_the_first_answer_becomes_the_frozen_opening(self, project, monkeypatch, capsys):
        """What the candidate types under the clock is what every later rung replays.

        Written in code rather than printed for someone to paste: the gap between the two
        is exactly where an answer gets quietly improved.
        """
        root, role_dir, case_dir = ready(project)
        (case_dir / "opening-answer.md").write_text(
            "# Opening answer\n\n> **STATUS: not frozen.**\n>\n> No block yet.\n\nSome prose.\n",
            encoding="utf-8",
        )
        answer_typed(monkeypatch, "I build payment services in TypeScript on AWS.")
        capsys.readouterr()

        cli.main(["run", "--baseline"])

        assert load_fenced_blocks(case_dir / "opening-answer.md") == (
            "I build payment services in TypeScript on AWS.",
        )
        kept = (case_dir / "opening-answer.md").read_text(encoding="utf-8")
        assert "Some prose." in kept
        assert "STATUS: frozen." in kept

    def test_capturing_the_opening_also_records_the_experiment(
        self, project, monkeypatch, capsys
    ):
        """The lock covers the opening, so it can only be written once one exists."""
        root, role_dir, case_dir = ready(project)
        (case_dir / "opening-answer.md").write_text("# opening\n\nprose only\n", encoding="utf-8")
        answer_typed(monkeypatch, "I build payment services.")
        capsys.readouterr()

        cli.main(["run", "--baseline"])

        lock = lock_of(root)
        assert lock is not None and lock.inputs.complete
        assert "recorded experiment" in capsys.readouterr().out

        kinds = [e.type for e in SessionStore(latest_session(root, "iteration-00")).events()]
        assert "opening_answer_frozen" in kinds
        assert "experiment_recorded" in kinds

    def test_the_replay_is_charged_what_the_answer_actually_took(
        self, project, monkeypatch, capsys
    ):
        """The opening costs the same at every rung, and that cost is the real one.

        A configured constant would make the stimulus cost one thing in the run that
        produced it and another in the ten that replay it - which is the exact asymmetry
        the frozen opening exists to prevent.
        """
        root, role_dir, case_dir = ready(project)
        (case_dir / "opening-answer.md").write_text(
            "# opening\n\nprose only\n", encoding="utf-8"
        )
        answer_typed(monkeypatch, "I build payment services.", seconds=137.0)
        cli.main(["run", "--baseline"])

        assert lock_of(root).opening_answer_seconds == 137.0

        replayed = record_replayed_opening(monkeypatch)
        cli.main(["run", "--iteration", "1"])
        assert replayed["seconds"] == 137.0

    def test_a_later_rung_replays_what_the_baseline_captured(
        self, project, monkeypatch, capsys
    ):
        root, role_dir, case_dir = ready(project)
        (case_dir / "opening-answer.md").write_text("# opening\n\nprose only\n", encoding="utf-8")
        answer_typed(monkeypatch, "I build payment services.")
        cli.main(["run", "--baseline"])

        replayed = record_replayed_opening(monkeypatch)
        capsys.readouterr()

        cli.main(["run", "--iteration", "1"])
        assert replayed["text"] == "I build payment services."

    def test_an_empty_first_answer_freezes_nothing(self, project, monkeypatch, capsys):
        """Fixing an empty string as the stimulus for the whole ladder is worse than retrying."""
        root, role_dir, case_dir = ready(project)
        (case_dir / "opening-answer.md").write_text("# opening\n\nprose only\n", encoding="utf-8")
        answer_typed(monkeypatch, "   ")
        capsys.readouterr()

        cli.main(["run", "--baseline"])

        assert load_fenced_blocks(case_dir / "opening-answer.md") == ()
        assert lock_of(root) is None
        assert "no opening answer was given" in capsys.readouterr().out

    def test_the_opening_is_never_silently_replaced(self, project, monkeypatch):
        """A second opening answer would become the stimulus for every run after it, so
        replacing one takes a deliberate restart rather than just happening."""
        from solution.application.opening_answer import freeze

        root, role_dir, case_dir = ready(project)
        target = case_dir / "opening-answer.md"
        target.write_text("# opening\n\nprose\n", encoding="utf-8")
        freeze(target, "the first", iteration=0, captured_at="2026-08-30")

        with pytest.raises(ValueError, match="already holds a fenced block"):
            freeze(target, "another one", iteration=0, captured_at="2026-08-30")

        _, replaced = freeze(
            target, "another one", iteration=0, captured_at="2026-08-30", replacing=True
        )
        assert replaced == "the first"
        assert load_fenced_blocks(target) == ("another one",)

    def test_a_pilot_freezes_nothing_even_when_an_answer_is_typed(
        self, project, monkeypatch, capsys
    ):
        """The pilot is a rehearsal. Nothing it produces reaches the experiment."""
        root, role_dir, case_dir = ready(project)
        (case_dir / "opening-answer.md").write_text("# opening\n\nprose only\n", encoding="utf-8")
        answer_typed(monkeypatch, "a rehearsal answer")

        cli.main(["run", "--baseline", "--pilot"])

        assert load_fenced_blocks(case_dir / "opening-answer.md") == ()
        assert lock_of(root) is None

    def test_a_smoke_run_records_nothing(self, project, monkeypatch):
        root, role_dir, case_dir = ready(project)
        stub_interview(monkeypatch)

        cli.main(["run", "--baseline", "--smoke", "300"])
        assert not (root / "evals" / "experiment-lock.yaml").exists()


class TestRetakingTheOpeningAnswer:
    """Fumbling the first answer is the commonest reason to restart, and an earlier version
    ignored it silently: `--restart` only fired when an input had drifted, and the opening
    answer had not - it was simply wrong. The run replayed it instead of refusing."""

    def _captured(self, project, monkeypatch, text="A first attempt, fumbled."):
        root, role_dir, case_dir = ready(project)
        (case_dir / "opening-answer.md").write_text("# opening\n\nprose\n", encoding="utf-8")
        answer_typed(monkeypatch, text)
        cli.main(["run", "--baseline"])
        return root, role_dir, case_dir, lock_of(root)

    def test_restart_recaptures_even_when_nothing_drifted(
        self, project, monkeypatch, capsys
    ):
        root, role_dir, case_dir, first = self._captured(project, monkeypatch)
        answer_typed(monkeypatch, "The second attempt, said properly.")
        capsys.readouterr()

        cli.main(["run", "--baseline", "--restart"])

        assert load_fenced_blocks(case_dir / "opening-answer.md") == (
            "The second attempt, said properly.",
        )
        assert lock_of(root).lock_id != first.lock_id

    def test_the_discarded_answer_stays_readable_in_its_own_record(
        self, project, monkeypatch, capsys
    ):
        """Section 4 forbids selective reporting. The retake removes the answer from the
        file the runner reads, never from the evidence."""
        root, role_dir, case_dir, first = self._captured(project, monkeypatch)
        answer_typed(monkeypatch, "The second attempt.")
        cli.main(["run", "--baseline", "--restart"])

        texts = []
        for session in sorted((root / "evals" / "results" / "iteration-00").glob("*.jsonl")):
            texts += [
                event.data.get("text")
                for event in SessionStore(session).events()
                if event.type == "answer_received"
            ]
        assert "A first attempt, fumbled." in texts
        assert "The second attempt." in texts

    def test_it_says_out_loud_that_the_retake_has_to_be_recorded(
        self, project, monkeypatch, capsys
    ):
        """A retake before seeing a result is a do-over; repeating one until the prediction
        confirms is the offence section 4 exists to prevent. The record tells them apart."""
        root, role_dir, case_dir, first = self._captured(project, monkeypatch)
        answer_typed(monkeypatch, "The second attempt.")
        capsys.readouterr()

        cli.main(["run", "--baseline", "--restart"])

        out = capsys.readouterr().out
        assert "discarded the opening answer" in out
        assert "CHANGELOG.md" in out
        assert "A first attempt, fumbled." in out

    def test_without_restart_the_frozen_answer_is_left_alone(
        self, project, monkeypatch, capsys
    ):
        root, role_dir, case_dir, first = self._captured(project, monkeypatch)
        replayed = record_replayed_opening(monkeypatch)
        capsys.readouterr()

        cli.main(["run", "--baseline"])

        assert replayed["text"] == "A first attempt, fumbled."
        assert lock_of(root).lock_id == first.lock_id

    def test_reopening_a_file_that_was_never_frozen_does_nothing(self, project):
        from solution.application.opening_answer import reopen

        root, role_dir, case_dir = ready(project)
        target = case_dir / "opening-answer.md"
        target.write_text("# opening\n\nprose only\n", encoding="utf-8")

        assert reopen(target) is None
        assert target.read_text(encoding="utf-8") == "# opening\n\nprose only\n"

    def test_reopening_keeps_the_prose_and_marks_the_file_unfrozen(self, project, monkeypatch):
        from solution.application.opening_answer import reopen

        root, role_dir, case_dir, first = self._captured(project, monkeypatch)
        target = case_dir / "opening-answer.md"

        assert reopen(target) == "A first attempt, fumbled."
        kept = target.read_text(encoding="utf-8")
        assert "prose" in kept
        assert "STATUS: not frozen." in kept
        assert load_fenced_blocks(target) == ()


class TestAChangedInputRestartsTheLadder:
    def _mid_ladder(self, project, monkeypatch):
        """Baseline and iteration 1 measured, against a recorded experiment."""
        root, role_dir, case_dir = ready(project)
        (case_dir / "opening-answer.md").write_text("# opening\n\nprose\n", encoding="utf-8")
        answer_typed(monkeypatch, "The first opening answer.")
        cli.main(["run", "--baseline"])
        lock = lock_of(root)
        record_measured_run(root, "iteration-00", lock.lock_id)
        record_measured_run(root, "iteration-01", lock.lock_id)
        return root, role_dir, case_dir, lock

    def _swap_the_cv(self, case_dir):
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "Bob Different  Vue and GCP")
        document.save(case_dir / "cv-original.pdf")
        document.close()

    def test_a_later_rung_stops_and_names_what_moved(self, project, monkeypatch, capsys):
        """The scenario in full: measure two rungs, swap the CV, try the third."""
        root, role_dir, case_dir, lock = self._mid_ladder(project, monkeypatch)
        self._swap_the_cv(case_dir)
        capsys.readouterr()

        assert cli.main(["run", "--iteration", "2"]) == 2
        out = capsys.readouterr().out
        assert "cv-original.pdf" in out
        assert "CHANGED" in out
        assert "iteration-00, iteration-01" in out
        assert lock.lock_id in out
        assert "interview run --baseline --restart" in out

    def test_restarting_from_a_later_rung_is_refused(self, project, monkeypatch, capsys):
        """Rungs measured against different inputs do not compare, so there is no way to
        carry on from the middle - a restart has to actually restart."""
        root, role_dir, case_dir, lock = self._mid_ladder(project, monkeypatch)
        self._swap_the_cv(case_dir)
        capsys.readouterr()

        assert cli.main(["run", "--iteration", "2", "--restart"]) == 2
        assert lock_of(root).lock_id == lock.lock_id

    def test_a_restart_still_needs_the_derived_inputs_in_step(
        self, project, monkeypatch, capsys
    ):
        """Restarting is a decision about the experiment, not a licence to skip the
        preflight: the swapped CV leaves cv.pdf and the evidence stale."""
        root, role_dir, case_dir, lock = self._mid_ladder(project, monkeypatch)
        self._swap_the_cv(case_dir)
        capsys.readouterr()

        assert cli.main(["run", "--baseline", "--restart"]) == 2
        assert "interview prepare" in capsys.readouterr().out
        assert lock_of(root).lock_id == lock.lock_id

    def test_the_baseline_with_restart_records_a_new_experiment(
        self, project, monkeypatch, capsys
    ):
        """A restart re-captures the opening, so the new experiment differs by at least
        that even when every other input is untouched."""
        root, role_dir, case_dir, lock = self._mid_ladder(project, monkeypatch)
        answer_typed(monkeypatch, "A different opening entirely.")
        capsys.readouterr()

        cli.main(["run", "--baseline", "--restart"])

        out = capsys.readouterr().out
        assert lock_of(root).lock_id != lock.lock_id
        assert lock.lock_id in out
        assert "never mixed" in out
        assert "restarts here" in out

    def test_a_restart_abandoned_before_answering_changes_nothing(
        self, project, monkeypatch, capsys
    ):
        """The old answer is displaced at the moment a new one is given, never before.
        Walking away from a restart has to leave the previous experiment intact."""
        root, role_dir, case_dir, lock = self._mid_ladder(project, monkeypatch)
        before_lock = (root / "evals" / "experiment-lock.yaml").read_bytes()
        before_opening = (case_dir / "opening-answer.md").read_bytes()
        stub_interview(monkeypatch)
        capsys.readouterr()

        assert cli.main(["run", "--baseline", "--restart"]) == 130

        assert (root / "evals" / "experiment-lock.yaml").read_bytes() == before_lock
        assert (case_dir / "opening-answer.md").read_bytes() == before_opening
        assert "recorded experiment" not in capsys.readouterr().out


class TestTheToolsWorkAboveTheBaseline:
    """Two commands quietly only ever worked on iteration 0. `branch` built its
    interviewer without the role and case directories, so it stopped with a usage error on
    exactly the rungs whose determinism it exists to measure; `show-prompt` refused
    outright. Both are how a reader checks a claim rather than taking it on trust."""

    @pytest.fixture
    def repository(self, tmp_path, monkeypatch):
        """The real inputs, copied, so this exercises the committed prompt and slot plan."""
        import shutil

        from solution.adapters.cli import ROOT as REAL_ROOT

        for relative_path in (
            "config.yaml",
            "roles/fullstack/role.txt",
            "roles/fullstack/slots.yaml",
            "evals/cases/case-01/cv.pdf",
            "evals/cases/case-01/resume-evidence.yaml",
            "solution/agent_instructions/interviewer.md",
            "baseline/prompt.md",
        ):
            target = tmp_path / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REAL_ROOT / relative_path, target)

        monkeypatch.setattr(cli, "ROOT", tmp_path)
        return tmp_path

    def test_branching_a_scheduled_rung_builds_that_rungs_interviewer(
        self, repository, monkeypatch
    ):
        from evals.metrics import branching

        from solution.application.interviewers.scheduled import ScheduledInterviewer

        class Sampling:
            """No seed and no temperature, so the sampling guard lets it through."""

            name, model = "stub", "stub"

            def complete_json(self, request, **_):
                raise AssertionError("no model call should be needed to build one")

        captured = {}

        def capture(**kwargs):
            captured["build"] = kwargs["build_interviewer"]
            return {"decision_points": 0, "samples_per_point": 0, "points": []}

        monkeypatch.setattr(cli, "build_provider", lambda *a, **k: Sampling())
        monkeypatch.setattr(branching, "branch_session", capture)

        record = repository / "evals" / "results" / "iteration-01" / "session-x.jsonl"
        SessionStore(record).append("run_metadata", iteration=1, run_kind="measurement")

        assert cli.main(["branch", str(record), "--samples", "2", "--no-judge"]) == 0
        assert isinstance(captured["build"](), ScheduledInterviewer)

    @pytest.mark.parametrize("iteration", [1, 2, 3])
    def test_show_prompt_renders_a_scheduled_rung(self, repository, capsys, iteration):
        assert cli.main(["show-prompt", "--iteration", str(iteration)]) == 0
        printed = capsys.readouterr().out
        assert "You are a technical interviewer conducting one turn" in printed
        assert "<<SLOT_NAME>>" in printed
