"""How often the judge disagrees with itself on identical input.

Needed before `interview branch` means anything: that metric counts how many distinct
competencies the interviewer would reach for, labelling each sample with this judge. If the
judge is itself unstable, a perfectly deterministic interviewer already scores above one,
and the branch figure would report instrument noise as interviewer variance.
"""
import json
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

from evals.metrics.judge import judge_question
from evals.metrics.measure import build_judge
from solution.adapters.session_store import SessionStore
from solution.adapters.slot_plan import load_slot_plan

SAMPLES = 5

config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
plan = load_slot_plan(ROOT / "roles/fullstack/slots.yaml")
d = ROOT / "evals/results/iteration-00"
ev = SessionStore(sorted(d.glob("session-*.jsonl"))[-1]).events()
qs = [e.data["text"] for e in ev if e.type == "question_asked" and e.data.get("kind") != "opening"]

judge = build_judge(config)
rows = []
for i, q in enumerate(qs, 1):
    labels = [judge_question(q, plan.slots, judge) for _ in range(SAMPLES)]
    counts = Counter(labels)
    rows.append({"question": i, "labels": labels, "distinct": len(counts),
                 "modal": counts.most_common(1)[0][0],
                 "modal_share": counts.most_common(1)[0][1] / SAMPLES})
    print(f"  Q{i:<3} distinct={len(counts)}  {dict(counts)}", flush=True)

distinct = [r["distinct"] for r in rows]
out = {
    "samples_per_question": SAMPLES,
    "questions": len(rows),
    "mean_distinct_labels": round(sum(distinct) / len(distinct), 2),
    "max_distinct_labels": max(distinct),
    "unanimous_questions": sum(1 for x in distinct if x == 1),
    "detail": rows,
}
(d / "judge-stability.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"\n  mean distinct labels per question: {out['mean_distinct_labels']}")
print(f"  unanimous: {out['unanimous_questions']}/{out['questions']}")
print(f"  written to {d/'judge-stability.json'}")
