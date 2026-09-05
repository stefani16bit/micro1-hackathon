"""The report is where a rung's runs become one row, and where the interesting property
is easiest to lose.

Keeping only the newest run of a rung reads as tidying up and is not: it discards the
spread, which is the only evidence for whether a coverage figure was reliable or lucky.
These tests pin the behaviour that replaced it - every run kept, the rung reported by its
worst one - and the conflict guard that must still fire before any of that happens.
"""

import json

from evals.metrics import report


def metrics(
    *,
    iteration=0,
    coverage=1.0,
    missed=(),
    longest_chain=1,
    lock="aaaaaaaaaaaa",
    run_kind="measurement",
    questions=6,
    interrupted=False,
):
    """A `.metrics.json` document, in the shape `measure` writes one."""
    return {
        "run_kind": run_kind,
        "experiment_lock_id": lock,
        "interrupted": interrupted,
        "metadata": {"iteration": iteration, "provider": "demo", "model": "demo"},
        "denominator": 6,
        "coverage": {
            "covered_slots": [],
            "missed_slots": list(missed),
            "value": coverage,
        },
        "carry_over_rate": 0.0,
        "grounding_rate": 0.0,
        "allocation": {"longest_chain": longest_chain, "slot_histogram": {}},
        "questions_measured": questions,
        "answer_seconds": {"mean": 90.0, "total": 540.0},
        "resolved_by": {"judge": questions, "unresolved": 0},
        "path": f"evals/results/iteration-{iteration:02d}/session-x.metrics.json",
    }


def write(results_dir, iteration, name, document):
    directory = results_dir / f"iteration-{iteration:02d}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.metrics.json").write_text(json.dumps(document), encoding="utf-8")


class TestCollect:
    def test_keeps_every_run_of_a_rung(self, tmp_path):
        """The older run is the whole point: without it there is no spread."""
        write(tmp_path, 0, "session-a", metrics(coverage=0.5))
        write(tmp_path, 0, "session-b", metrics(coverage=1.0))
        assert len(report.collect(tmp_path)) == 2

    def test_leaves_out_runs_that_were_never_measurements(self, tmp_path):
        write(tmp_path, 0, "session-a", metrics())
        write(tmp_path, 0, "session-b", metrics(run_kind="smoke"))
        assert len(report.collect(tmp_path)) == 1

    def test_an_empty_results_directory_is_no_runs_rather_than_an_error(self, tmp_path):
        assert report.collect(tmp_path) == []


class TestSummarise:
    def test_the_rung_is_reported_by_its_worst_run(self, tmp_path):
        rows = report.by_iteration([metrics(coverage=1.0), metrics(coverage=0.5)])
        assert rows[0]["coverage_floor"] == 0.5
        assert rows[0]["coverage_ceiling"] == 1.0

    def test_carries_the_mean_so_the_spread_is_visible(self, tmp_path):
        rows = report.by_iteration([metrics(coverage=1.0), metrics(coverage=0.5)])
        assert rows[0]["coverage_mean"] == 0.75

    def test_counts_the_runs(self, tmp_path):
        rows = report.by_iteration([metrics(), metrics(), metrics()])
        assert rows[0]["runs"] == 3

    def test_reports_the_worst_chain_seen_across_the_runs(self, tmp_path):
        """A rung that drilled one competency four deep even once has done so."""
        rows = report.by_iteration([metrics(longest_chain=1), metrics(longest_chain=4)])
        assert rows[0]["longest_chain"] == 4

    def test_rungs_come_back_in_ladder_order(self, tmp_path):
        rows = report.by_iteration(
            [metrics(iteration=10), metrics(iteration=0), metrics(iteration=4)]
        )
        assert [r["iteration"] for r in rows] == [0, 4, 10]

    def test_a_rung_run_once_has_no_spread(self, tmp_path):
        rows = report.by_iteration([metrics(coverage=0.83)])
        assert rows[0]["runs"] == 1
        assert rows[0]["coverage_floor"] == rows[0]["coverage_ceiling"] == 0.83


class TestTheExperimentGuard:
    def test_runs_from_two_experiments_are_grouped_apart(self):
        grouped = report.group_by_experiment(
            [metrics(lock="aaaaaaaaaaaa"), metrics(lock="bbbbbbbbbbbb")]
        )
        assert len(grouped) == 2

    def test_the_refusal_names_both_experiments_and_their_rungs(self):
        grouped = report.group_by_experiment(
            [metrics(lock="aaaaaaaaaaaa"), metrics(iteration=2, lock="bbbbbbbbbbbb")]
        )
        rendered = report.render_conflict(grouped)
        assert "aaaaaaaaaaaa" in rendered and "bbbbbbbbbbbb" in rendered
        assert "more than one experiment" in rendered

    def test_the_refusal_does_not_suggest_deleting_the_abandoned_runs(self):
        """Section 4 requires them to stay reported, so the fix must say move, not delete."""
        grouped = report.group_by_experiment(
            [metrics(lock="aaaaaaaaaaaa"), metrics(lock="bbbbbbbbbbbb")]
        )
        assert "move" in report.render_conflict(grouped)


class TestRenderMarkdown:
    def render(self, runs):
        return report.render_markdown(
            report.by_iteration(runs), baseline_iteration=0, solution_iteration=3, lock=None
        )

    def test_shows_how_many_times_a_rung_was_run(self):
        assert "| 0 | 2 |" in self.render([metrics(coverage=1.0), metrics(coverage=0.5)])

    def test_shows_the_spread_rather_than_a_single_figure(self):
        assert "50% – 100%" in self.render([metrics(coverage=1.0), metrics(coverage=0.5)])

    def test_the_headline_coverage_is_the_worst_run(self):
        rendered = self.render([metrics(coverage=1.0), metrics(coverage=0.5)])
        assert "| Coverage, worst run (primary) | 50%" in rendered

    def test_says_plainly_that_the_headline_is_the_worst_run(self):
        assert "worst run, not the mean" in self.render([metrics()])

    def test_missed_competencies_come_from_the_worst_run(self):
        """Averaging them would report a candidate nobody actually interviewed."""
        rendered = self.render(
            [metrics(coverage=1.0, missed=()), metrics(coverage=0.5, missed=("backend",))]
        )
        assert "missed: backend" in rendered

    def test_names_the_rungs_still_missing(self):
        rendered = self.render([metrics(iteration=0)])
        assert "iteration 3 (solution)" in rendered

    def test_no_runs_at_all_renders_the_empty_table(self):
        rendered = report.render_markdown(
            [], baseline_iteration=0, solution_iteration=3, lock=None
        )
        assert "no measured run yet" in rendered


class TestInterruptedRunsAreNotMeasurements:
    """A sitting abandoned for a tooling reason is not a measurement of the rung.

    The hazard is a glob: after a retake both records sit in `iteration-01/`, and
    `interview measure .../session-*.jsonl` writes metrics for both. The rung would then
    be reported as two runs, one of them two questions long, in the headline table.
    """

    def test_an_interrupted_run_is_left_out(self, tmp_path):
        write(tmp_path, 1, "session-a", metrics(iteration=1, interrupted=True))
        write(tmp_path, 1, "session-b", metrics(iteration=1))
        assert len(report.collect(tmp_path)) == 1

    def test_a_rung_whose_only_run_was_interrupted_has_no_row(self, tmp_path):
        write(tmp_path, 1, "session-a", metrics(iteration=1, interrupted=True))
        assert report.by_iteration(report.collect(tmp_path)) == []

    def test_the_retake_alone_decides_the_rung(self, tmp_path):
        write(tmp_path, 1, "session-a", metrics(iteration=1, coverage=0.2, interrupted=True))
        write(tmp_path, 1, "session-b", metrics(iteration=1, coverage=1.0))
        row = report.by_iteration(report.collect(tmp_path))[0]
        assert row["runs"] == 1 and row["coverage_floor"] == 1.0
