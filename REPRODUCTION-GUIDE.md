# Reproduction guide

For someone starting from a clean machine, with nothing from this project installed.

---

## Where the ladder is, and what to run next

| Rung | What it switches on | State |
| ---: | --- | --- |
| **0** baseline | one prompt, the full transcript every turn | run **and measured** |
| **1** | the scheduler picks the competency; the model still sees the transcript | **run, not yet measured** |
| **2** | context isolation on its own | **built, never run** — a gap in the evidence, recorded in `CHANGELOG.md` |
| **3** = `--solution` | isolation *and* the gate that verifies every question before you see it | **built, not yet run** |

Each rung costs a 25-minute human sitting, and rung 2 was the one there was no time for. Rung 3
therefore switches on two mechanisms at once, so a rung-1-to-rung-3 difference cannot be attributed
to either alone. The baseline-against-solution comparison — the claim this project actually makes —
is unaffected.

**The order to run things in:**

```
interview measure evals/results/iteration-01/session-*.jsonl   # the rung already sat
interview run --solution                                       # 25 minutes
interview measure evals/results/iteration-03/session-*.jsonl
interview report
```

---

## The constraint, stated first

**An interview needs a human typing for 25 minutes.** There is no simulated candidate, on purpose: a
model playing the candidate would be a second system entangled with the one being measured. So there
are two paths, answering different questions:

| | Question it answers | Cost | Needs |
| --- | --- | --- | --- |
| **A. Inspect** | *Does the machinery hold the properties it claims?* | seconds to minutes | Python; a model for the coverage figure |
| **B. Live** | *Does it behave as described, on a candidate it has never seen?* | ~25 min per rung | Claude Code CLI, your own CV |

---

## Setup

Python 3.12+ (developed on 3.12.6). Dependencies are pinned by lower bound in `pyproject.toml`.

```
git clone <this repository>
cd hackerearth-micro1-hackathon

python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux

pip install -e ".[dev]"
interview --help
```

Everything below also runs as `python -m solution.adapters.cli <command>` if you would rather not
install anything.

---

## Path A — re-derive the published numbers

### A1. The test suite

```
pytest
```

Every test passes in a few seconds, and nothing touches a network or a model. What it pins is where
most of this project's claims live:

| File | The claim it holds in place |
| --- | --- |
| `tests/domain/test_scheduler.py` | nothing can shorten an answer; breadth is never traded for depth |
| `tests/domain/test_gate.py` | a question carrying the previous answer forward never reaches the candidate |
| `tests/application/test_runner.py` | only an interviewer that cannot read the answers may compose ahead |
| `tests/application/test_scheduled_interviewer.py` | a follow-up sees the answer it follows up on, and nothing else |
| `tests/application/test_experiment.py` | one test per item `PREREGISTRATION.md` §4 calls invalidating |
| `tests/application/test_prompt_contamination.py` | the interviewer is told nothing about the project, the slots, or the clock |
| `tests/metrics/test_rates.py` | carry-over and grounding measure opposite things |
| `tests/metrics/test_allocation.py` | an unlabelled question cannot bridge two runs into one long chain |
| `tests/metrics/test_branching.py` | a provider pinned to a fixed seed is refused rather than reported as consistent |
| `tests/metrics/test_report.py` | a rung's runs are all kept, and the rung is reported by its worst one |

### A2. Measure a session record

```
interview measure evals/results/iteration-00/session-*.jsonl
```

Writes `<session>.metrics.json` beside the record. Per session you get coverage as *n*/6 with the
competencies named, carry-over and grounding, the allocation block, and the answer-time
distribution.

**It will not always produce the same file, and that is the instrument rather than a bug.** The
guardrail rates are deterministic; coverage is not. Three measurements of the committed baseline
record returned 5/6 twice and 4/6 once, because the judge moved two labels — all three are committed
side by side (`.metrics.json`, `.metrics.judge-run-2.json`, and the pre-correction
`.metrics.pre-fix.json`). Expect your re-measure to land in that range.

**Coverage needs the judge.** `--no-judge` leaves every question unresolved and coverage at 0/6: the
keyword layer that used to resolve the easy ones was removed after resolving 0 of 11 on the real run
(`PREREGISTRATION.md` §2b). That flag is a statement about the instrument, not a reproduction path.

### A3. Build the results table

```
interview report
```

Writes `evals/results/report.md` and `report.json`. A rung run more than once is reported by its
**worst** run with the spread beside it. It refuses to build a table spanning two experiments.

### A4. Ask what else the interview might have asked

```
interview branch evals/results/iteration-00/session-*.jsonl --samples 5
```

Rewinds the record to every turn boundary and asks the interviewer five times what it would say next,
labelling each with the same judge. One distinct competency per decision point means the topic was
determined; more than one means it was a draw. Costs no extra sitting — the answers are a real
respondent's, replayed.

**It needs a provider that samples**, and refuses one pinned to `temperature: 0` or a fixed seed
rather than reporting the seed as consistency.

### A5. Read a trajectory

```
interview show evals/results/iteration-01/session-*.jsonl
interview show trajectories/judge-*.jsonl
interview show-prompt --solution
```

`show` renders a record as a transcript with every model call's prompts and raw reply, retries
shown separately. `show-prompt` prints exactly what the interviewer at a given rung is sent.

---

## Path B — sit the interview yourself

Role and slot plan stay as they are; the CV is yours.

### B0. What you need

- **Claude Code CLI**, logged in. The model is pinned to `claude-sonnet-4-5-20250929` in
  `config.yaml` — a dated snapshot, not an alias.
- **Your CV as a PDF with a text layer.** A scan will not work: quotes are verified against extracted
  text character for character.
- **~25 minutes per rung.** Roughly, because answers are untimed and the last one may run past.

**Cost.** Calls go through your Claude Code subscription; there is no API key in this repository. One
model call per turn, plus one résumé-matcher call at setup and one judge call per question at
measurement time. Path A costs nothing. `interview run --provider ollama` is free and local, but is
not what the ladder is measured on (`PREREGISTRATION.md` §3c, §3d).

### B1. Check you can reach the model

```
interview check
```

One cheap call, so a broken provider surfaces in seconds rather than in minute nine of an interview.

### B2. Put your CV in place

```
cp your-cv.pdf evals/cases/case-01/cv-original.pdf
```

`cv-original.pdf` is never committed. To keep the author's case intact, make a new directory and pass
`--case evals/cases/case-mine` to every command below.

### B3. Prepare the derived inputs

```
interview prepare
```

The only command that changes anything on disk. It rebuilds `cv.pdf` from your original — deleting
phone numbers and email addresses **from the text layer** rather than covering them — verifies none
of the removed strings are still readable, and resolves what your CV evidences per competency into
`resume-evidence.yaml`, with every quote checked verbatim in code.

Expect a per-slot `yes`/`NO` with the opening words of each quote. `NO` is not a failure: it selects
a situational question instead of a behavioural one, which is the fair way to ask about something you
have not done.

### B4. Run the interviews

```
interview run --baseline      # 25 minutes
interview run --solution      # 25 minutes
```

**The baseline run does two things nothing else does.** It **captures your opening answer** — every
interview opens with *"tell me about yourself"*, and that answer is the controlled stimulus, frozen
in code the moment you give it and replayed verbatim by every later rung. And it **records the
experiment**: `evals/experiment-lock.yaml`, holding the digests of your role, slot plan, CV, résumé
evidence, opening answer and time budget. Every run after it is checked against that file.

**Your answers are not timed.** The toolbar shows how much of the 25 minutes is left. Once the budget
is spent no new question is asked, but an answer already under way is never cut off.

Answer honestly and the same way in both runs. If you sharpen an answer between them, you have
changed the experiment — `evals/cases/case-01/response-brief.md` is the mechanism for keeping the
content constant, and its rule 1 is how it may legitimately grow.

### B5. Measure and compare

```
interview measure evals/results/iteration-00/session-*.jsonl
interview measure evals/results/iteration-03/session-*.jsonl
interview report
```

Your `lock_id` differs from the author's, so `interview report` shows your experiment and refuses to
mix your runs with the committed ones. Coverage measured against your CV is not comparable with
coverage measured against theirs.

**Read the answer-time columns beside coverage.** Answers are uncapped, so a run where you simply
talked longer covers less — and that is not the interviewer changing.

---

## The experiment lock

Coverage is *slots asked / 6*, and the 6 comes from `roles/fullstack/slots.yaml`. If the slot plan,
the CV or the opening answer changed halfway through a ladder, the runs before and after would be
measured over different things, and the comparison would be meaningless in a way that leaves no trace
in the numbers. So the baseline records the digest of every such input and every run after it checks
them:

```
  BLOCKED  cv-original.pdf no longer matches the frozen experiment

           experiment <lock-id>, frozen <timestamp>
           measured runs: iteration-00, iteration-01

           cv-original.pdf       frozen <digest>…   now <other>…    CHANGED
```

Two ways forward: restore what it was frozen against, or accept this is a different experiment —
`interview run --baseline --restart`, which starts again **at the first rung**. There is no way to
carry on from the middle, and `--restart` is refused on any other rung. Already-recorded results keep
the old `lock_id` and are never mixed with the new ones.

One input is **tracked rather than locked**: `response-brief.md` records its digest with every run
but never blocks one, because its own rule 1 allows it to grow. See
[`solution/application/experiment.py`](solution/application/experiment.py).

**Changing the role deliberately** takes five steps, and the review is a real checkpoint: edit
`role.txt`, run `interview role-extract` (which writes `slots.draft.yaml`, never `slots.yaml`),
review and edit the draft by hand, rename it, then `interview prepare` and
`interview run --baseline --restart`.

---

## Command reference

| Command | Does | Changes files? |
| --- | --- | --- |
| `interview check` | one cheap model call | no |
| `interview role-extract` | drafts `slots.draft.yaml` for human review | writes the draft |
| `interview prepare` | rebuilds `cv.pdf` and `resume-evidence.yaml` | **yes — the only one** |
| `interview run` | conducts one interview; the baseline also freezes the opening and records the experiment | writes a session record |
| `interview measure` | metrics for one or more sessions | writes `.metrics.json` |
| `interview branch` | resamples each turn of a record k times | writes `.branch.json` |
| `interview report` | baseline vs solution, as a table | writes `report.md` |
| `interview show` | renders a session or trajectory | no |
| `interview show-prompt` | prints exactly what the interviewer is sent | no |

`--role` and `--case` override `config.yaml`; `--provider` overrides the model. `--smoke SECONDS`
runs any rung end to end with a canned candidate — useful for checking the pipeline without spending
a sitting, and never a measurement.

---

## Data

| Path | What | Committed? |
| --- | --- | --- |
| `roles/fullstack/role.txt` | a real micro1 Full Stack Developer posting, with its source URL | yes |
| `roles/fullstack/slots.yaml` | the frozen six-competency plan, and the raw model output it was reviewed from | yes |
| `evals/cases/case-01/cv-original.pdf` | the candidate's CV | **no** — never committed |
| `evals/cases/case-01/cv.pdf` | the redacted CV the interview reads | **no** — rebuilt by `interview prepare` |
| `evals/cases/case-01/opening-answer.md` | the frozen controlled stimulus | yes |
| `evals/cases/case-01/response-brief.md` | the answer corpus, transcribed from the transcripts | yes |
| `evals/results/` | every run, raw, never hand-edited | yes |
| `trajectories/` | one record per agent, with full prompts | yes |

Neither CV is committed. `cv.pdf` is a derived artifact: `interview prepare` rebuilds it from
`cv-original.pdf`, stripping the phone number and email from the text layer. The author's copy is
anonymised beyond that — employers read *Company X* and *Company Y*, the university *University
Name* — but it is a real CV with real work history, so it stays out of a public repository. Every
digest the experiment lock records is over content, not over a committed file, so nothing about
reproduction changes: supply your own `cv-original.pdf` and run `interview prepare`.

---

## If something goes wrong

| Symptom | What it means |
| --- | --- |
| you fumbled the opening answer | `interview run --baseline --restart` re-captures it. The discarded answer stays in the record of the run that captured it; note the retake in `CHANGELOG.md`. |
| `BLOCKED … nothing to be measured against` | no experiment recorded yet, and this is not the baseline. Start at `--baseline`. |
| `BLOCKED … no longer matches the frozen experiment` | an input moved. The table names which one and the two ways forward. |
| `BLOCKED … cv.pdf was derived from a different original` | run `interview prepare`. `run` will not rebuild it for you. |
| `BLOCKED … this experiment already has measured runs` | `prepare` refuses to rebuild an input the ladder already depends on. |
| `BLOCKED  the provider would not actually sample` | `interview branch` against a pinned seed. Use a sampling provider. |
| `claude CLI exited 1` | `interview check` will say whether the CLI is reachable at all. |
| `iteration N does not exist yet` | that rung is not built. `CHANGELOG.md` says where the ladder stands. |
| a quote is discarded as unverifiable | the model paraphrased instead of quoting. Working as intended — the slot is recorded unevidenced rather than on invented evidence. |
