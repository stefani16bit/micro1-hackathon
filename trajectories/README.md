# Agent trajectories

One record per agent, per representative run: what it was asked, what it answered, what came back
when that answer was wrong, and what a person decided afterwards.

agentic-workflows.md §8 asks for these to be followable *from the agent's instructions through to
its final result*. §9 adds the part that decides how this directory works: **they are captured as
work happens and cannot be reconstructed later**. So capture is not a step anyone remembers to
take — every model call in this project goes through `TracingProvider`
(`solution/adapters/providers/tracing.py`), and recording is the default rather than a flag.

## Reading one

```
interview show trajectories/judge-<stamp>.jsonl
```

Records are append-only JSONL, the same format as a session record — because a trajectory *is* a
session, of an agent rather than of a candidate. `interview show` renders either.

Each `model_call` event holds the system prompt, the user prompt, the JSON Schema the call demanded,
and the raw reply. **Attempts are numbered rather than collapsed**: a call that succeeded on its
second try shows both, and a call that failed outright is recorded before the error propagates, so a
trajectory that ends says why.

## The agents

| Agent | When it runs | Its instructions | Where the trace lands |
| --- | --- | --- | --- |
| `slot-extractor` | once per role, offline | [`solution/agent_instructions/slot_extractor.md`](../solution/agent_instructions/slot_extractor.md) | `trajectories/slot-extractor-<stamp>.jsonl` |
| `resume-matcher` | once per case, before turn 1 | `SYSTEM` in [`solution/application/ingest_resume.py`](../solution/application/ingest_resume.py) | `trajectories/resume-matcher-<stamp>.jsonl` |
| `interviewer-<N>` | every turn of an interview | rung 0: [`baseline/prompt.md`](../baseline/prompt.md) — rungs 1–3: [`interviewer.md`](../solution/agent_instructions/interviewer.md) | inside the session record itself |
| `judge` | per question the rule layer cannot label | `SYSTEM` in [`evals/metrics/judge.py`](../evals/metrics/judge.py) | `trajectories/judge-<stamp>.jsonl` |
| `branch` | k times per turn boundary, when `interview branch` runs | the interviewer's own, replayed — see [`evals/metrics/branching.py`](../evals/metrics/branching.py) | `trajectories/branch-<stamp>.jsonl` |

The `branch` trace carries its own `branch_sample` events beside the `model_call` ones. That is not
duplication: k samples of one decision point send an identical prompt, so they share a request
fingerprint and the tracing provider numbers them as *attempts* — which reads as retries. The
`branch_sample` events say which decision point and which sample each call actually was.

The interviewer's calls go into the session record rather than a separate file on purpose: its
prompts and the candidate's answers interleave, and splitting them would break the one thing a
reader wants to follow — how what the candidate said changed what was asked next.

## The human checkpoints

Two decisions in this pipeline are deliberately not the agent's, and both leave a trace outside the
model calls:

- **The slot plan.** `interview role-extract` writes `slots.draft.yaml`, never `slots.yaml`. A
  person reviews it, edits it, and renames it. The raw model output is kept beside the reviewed
  version as [`roles/fullstack/slots.l1-raw.yaml`](../roles/fullstack/slots.l1-raw.yaml), and the
  header of `slots.yaml` records the four defects that were corrected — so what the model proposed
  and what a human decided are both readable, separately.
- **The opening answer.** Given live by the candidate during the baseline interview and frozen
  in code at the moment it is spoken, into `opening-answer.md`, then replayed verbatim by every
  later rung. The `opening_answer_frozen` event in the session record marks when it happened. This
  one is deliberately *not* a review checkpoint: a step between saying it and freezing it is where
  an answer gets improved, which would make the runs incomparable.

## What is verified rather than trusted

Two agent outputs are checked in code before anything downstream uses them, and both checks are
visible in the trace:

- **Evidence quotes** are compared against the CV text character for character
  (`solution/domain/quotes.py`). A fluent paraphrase is discarded and the slot recorded as
  unevidenced. A model asked for a verbatim quote will sometimes produce a plausible one instead,
  and every per-slot rating rests on the quote being real.
- **Generated questions** pass the gate (`solution/domain/gate.py`) before the candidate sees them:
  a question naming a technology the candidate raised, outside the competency being asked about, is
  rejected as drift. Set comparison, not judgement — an anti-tunneling property that depends on a
  model behaving well is a hope.

## Status

Four judge traces are here, one per measurement of the baseline record — including the two that
disagreed with each other, which is where the ±1/6 of coverage instability in `PREREGISTRATION.md`
§2b is visible turn by turn. The interviewer's own calls live inside the session records under
`evals/results/`. `interview branch` writes a `branch-<stamp>.jsonl` the first time it is run.
