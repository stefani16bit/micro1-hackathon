# structured-interviewer

An AI screening interviewer that decides what to ask from the job description, not from whatever the
candidate happened to say last.

Built for the [micro1 Frontier Engineering Challenge 2026](https://www.hackerearth.com/community/challenges/hackathon/micro1-frontier-engineering-challenge-2026/).

> **Status.** The baseline is built, run and measured. The full solution is built and tested but has
> not been sat yet, because every rung of the ladder costs a real person 25 minutes of typing. The
> numbers below are the ones that exist. See [Results](#results) for what that means for the claim.

---

## The problem

Give a good model a job description, a CV, and an instruction to "adapt your questions to the
candidate's answers", and it does exactly that. The candidate mentions Redis in their opening answer,
so question two goes deeper on Redis. So does question three. So does question four.

The usual way to describe this is "it never reaches the other topics", and that turns out to be
wrong. A capable model does reach them, eventually. What it does not do is decide *how much of the 25
minutes each one gets*. Four questions go to whatever the candidate raised first, the rest get one
each at the end, shallow. You end up with one deep answer and five drive-by ones, and the thing that
decided which topic got the depth was the candidate's opening sentence rather than the job.

Two things follow, and both land on the candidate:

* They get rated on evidence of uneven quality, deep in one spot and thin everywhere else.
* It is not the same interview twice. Two equally qualified people get differently shaped screens, and
  so does the same person on a different day.

This is not a model bug. It is what "adapt to the answers" means when nothing in the loop counts what
has already been asked. Depth and breadth pull against each other, and a system with no
representation of breadth resolves that in favour of whatever is in front of it.

Candidates describe this shape in their own words, collected in
[`research/evidence/candidate-reports.md`](research/evidence/candidate-reports.md). Four self selected
posts are motivation, not measurement, and that file says so.

### Why it matters

micro1's paper on its interviewer Zara ([arXiv:2507.02869](https://arxiv.org/abs/2507.02869)) reports
4,820 unsuccessful interviews in a three day window, and that 89.3% of those candidates never asked
for feedback. It also reports the metrics it scores well on:

| Metric (paper §5.1) | Human led | Previous system | Zara |
| --- | ---: | ---: | ---: |
| Technical question quality | 7.78 | 8.38 | **8.60** |
| Conversational dynamics | 5.49 | 7.77 | **8.27** |

Both are per turn properties. Every question can be excellent and the conversation can flow, turn
after turn, while the session as a whole never leaves one topic, and neither number would move.

That is the gap here: **coverage is a session level property, and per turn quality cannot see it.**

No claim is made about how Zara actually works. The paper does not publish the interview conduct
policy, so [`baseline/prompt.md`](baseline/prompt.md) is labelled as *the obvious way to build this*,
written in good faith, not as a reconstruction. Quotes are reproduced in
[`research/sources.md`](research/sources.md).

---

## How it works

**Coverage comes from the job description. Answers fill slots, they never define them.**

The posting is turned once, offline, into a frozen plan of six competencies
([`roles/fullstack/slots.yaml`](roles/fullstack/slots.yaml)), reviewed by a human before it is
committed. After that it is read only, because it is the denominator of the primary metric.

Three properties are enforced in code instead of asked for in a prompt:

* **Topic selection never reads the answers.**
  [`scheduler.py`](solution/domain/scheduler.py) picks the next competency from the plan and the clock
  alone. That is the whole anti tunneling mechanism, and it is under eighty lines.
* **Every question is checked before the candidate sees it.**
  [`gate.py`](solution/domain/gate.py) rejects a question that reaches for a technology the candidate
  raised outside the competency being asked about. It is a set comparison, not a judgement call. An
  anti tunneling property that depends on a model behaving well is a hope, not a guarantee.
* **Every claim about the CV is checked against the CV.**
  Ask a model for a verbatim quote and it will sometimes hand back a fluent paraphrase. Quotes are
  compared character for character ([`quotes.py`](solution/domain/quotes.py)); one that fails is
  dropped and the competency is recorded as unevidenced.

Two side effects worth knowing about, because they surprise people:

**Depth is decided by the clock, not by the answer.** One question per competency, plus at most one
follow up when the schedule can still afford everything left. Nothing reads how good an answer was.
That is what makes the ceiling a property of the code rather than of a run, and it is also the price:
six competencies in 25 minutes is one or two questions each, whoever is scheduling.

**Not reading the transcript is also what removes the waiting.** Since the next question does not
depend on the answer, it gets composed *while* the answer is being given. In the rung that still reads
the transcript, 409 of 1491 seconds, 27% of the interview, were the candidate watching a terminal
think. A prompt driven interviewer cannot avoid that: it is handed the transcript and asked to react
to it, so the next question cannot exist before the answer does.

### What gets measured

Coverage alone is a weak claim, since a fixed questionnaire scores 6/6 and is a worse interview. So it
runs against guardrails that pull the other way:

| Metric | What it counts | Good looks like |
| --- | --- | --- |
| **Coverage** (primary) | competencies asked about at least once, out of 6, reported as the *worst* run | high |
| **Longest chain** | consecutive questions on a single competency | at the schedule's ceiling, never above |
| **Carry over** (guardrail) | questions reaching for a term the candidate raised, outside the current competency | near zero |
| **Grounding** (guardrail) | questions reaching into the CV for something specific to this candidate | high |
| **Branching** | distinct competencies the interviewer would reach for at one decision point, sampled k times | exactly one |

Coverage is a *set*, so on its own it scores an evenly spread interview and one that burned four of
ten questions on a single situation exactly the same. **Longest chain** is what separates them. A
scheduled interviewer cannot exceed two by construction. A single prompt has no ceiling, because
nothing counts what it already asked.

**Branching** covers the other half, whether the topic was determined at all. It rewinds a recorded
interview to each turn boundary and asks the interviewer k times what it would say next. The scheduler
answers with one competency every time. A prompt answers with a spread, and the width of that spread
is how much of the candidate's screen was a coin flip. It costs one sitting rather than k, since the
answers are a real person's, given once and replayed.

Both guardrails are set comparisons with no model in the loop. Coverage does need a model, and it is
not stable: three measurements of the *same* record came back 5/6 twice and 4/6 once, because the
judge moved two labels. That is ±1/6 of instrument error before any interviewer change, and it is
recorded in [`PREREGISTRATION.md`](PREREGISTRATION.md) §2b rather than quietly dropped.

---

## Results

The prediction was registered in [`PREREGISTRATION.md`](PREREGISTRATION.md) before any run, along with
the result that would prove the premise wrong. **It was proved wrong.**

| | Iteration 0 (baseline) | Iteration 3 (solution) |
| --- | --- | --- |
| **Predicted** | coverage ≤ 2/6, carry over ≥ 50% | coverage ≥ 6/6, carry over ≤ 10%, grounding materially higher |
| **Measured** | coverage **4/6 to 5/6**, carry over **18%** | not run |

The falsification clause was the part that cost something: if the baseline reaches coverage ≥ 3/6, the
prediction has failed. It reached 5/6. That is logged as a failed prediction, not reframed into a
weaker claim and not re-run with a different opening answer until it tunnels.

Three caveats, none of them comfortable:

* **Coverage is a range because the instrument is not stable**, ±1/6 before any interviewer change.
* **The 18% carry over was first measured as 100%**, and the 100% was wrong. It was counting
  `backend`, `api` and `request`, which are layer names rather than technologies, while missing five
  consecutive questions about one idempotency key. §2b records the correction and both numbers.
* **Coverage 5/6 overstates what that interview did.** Eleven questions covered three subjects, and
  one continuous conversation about an idempotency key got credited to four different competencies.
  The candidate's own verdict was that they never got to show the breadth the role asks for. On that,
  the metric and the person disagree.

Every figure points at a file under [`evals/results/`](evals/results/), generated by `interview report`
from the raw session records. Nothing is typed in by hand.

### Where the ladder stands

| Rung | What it turns on | State |
| ---: | --- | --- |
| **0** baseline | one prompt, full transcript every turn | run and measured |
| **1** | scheduler picks the competency, model still sees the transcript | run, not yet measured |
| **2** | context isolation on its own | built, never run |
| **3** = `--solution` | isolation plus the gate | built, not yet run |

Rung 2 is the one there was no time for, so rung 3 turns on two mechanisms at once and a rung 1 to
rung 3 difference cannot be pinned on either alone. That is a gap in the evidence and
[`CHANGELOG.md`](CHANGELOG.md) reports it as one instead of renumbering it away.

---

## Getting started

Python 3.12+ (developed on 3.12.6).

```bash
git clone https://github.com/stefani16bit/micro1-hackathon.git
cd micro1-hackathon

python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -e ".[dev]"
interview --help
```

Everything also runs as `python -m solution.adapters.cli <command>` if you would rather not install
anything.

### Run the tests

```bash
pytest
```

A few seconds, no network and no model calls. Most of this project's claims are pinned there:
`tests/domain/test_scheduler.py` (breadth is never traded for depth), `tests/domain/test_gate.py` (a
question carrying the last answer forward never reaches the candidate),
`tests/application/test_prompt_contamination.py` (the interviewer is told nothing about the project,
the slots, or the clock).

### Reproduce the published numbers

No model needed except for coverage, and it takes seconds.

```bash
interview measure evals/results/iteration-00/session-*.jsonl   # coverage, guardrails, allocation
interview report                                               # writes evals/results/report.md
interview show evals/results/iteration-01/session-*.jsonl      # transcript with every prompt
interview show-prompt --solution                               # exactly what the interviewer is sent
```

`measure` will not always give you the same coverage figure, and that is the instrument rather than a
bug. All three of the baseline measurements are committed side by side so you can see the spread.

### Sit the interview yourself

This is the part with a real cost: **there is no simulated candidate.** That is deliberate, since a
model playing the candidate would be a second system tangled up with the one being measured. So an
interview needs a person typing for about 25 minutes.

You need the Claude Code CLI logged in (the model is pinned to `claude-sonnet-4-5-20250929` in
`config.yaml`, a dated snapshot rather than an alias) and your CV as a PDF with a real text layer. A
scan will not work, because quotes get verified against extracted text character for character.

```bash
cp your-cv.pdf evals/cases/case-01/cv-original.pdf
interview check                    # one cheap call, so a broken provider shows up now
interview prepare                  # rebuilds the derived inputs
interview run --baseline           # 25 minutes
interview run --solution           # 25 minutes
interview measure evals/results/iteration-03/session-*.jsonl
interview report
```

Calls go through your Claude Code subscription. There is no API key anywhere in this repo.
`interview run --provider ollama` is free and local, but it is not what the ladder is measured on.

Full walkthrough, including the failure modes and what each command is allowed to touch:
[REPRODUCTION-GUIDE.md](REPRODUCTION-GUIDE.md).

### Commands

| Command | What it does |
| --- | --- |
| `interview check` | one cheap model call, so a broken provider surfaces in seconds |
| `interview role-extract` | drafts a slot plan from `role.txt` for a human to review |
| `interview prepare` | rebuilds the derived inputs. The only command that writes to them |
| `interview run --baseline` | conducts one interview at the baseline rung and records the experiment |
| `interview run --solution` | the same interview, conducted by the finished system |
| `interview measure <session>` | metrics for one or more session records |
| `interview branch <session>` | resamples a recorded interview's turns to see what else it might have asked |
| `interview report` | baseline against solution, as a table |
| `interview show <record>` | renders a session or trajectory, prompts included |
| `interview show-prompt` | prints exactly what the interviewer at a given rung is sent |

---

## Layout

```
solution/                 the system, split domain / application / adapters
  domain/                 scheduler, gate, quote verification. No IO, no model
  application/            the turn loop, the interviewer rungs, preflight
  adapters/               CLI, console IO, providers, session store
  agent_instructions/     the instructions that shape each agent, as readable files
baseline/prompt.md        iteration 0, the fair floor
roles/fullstack/          the job posting and its frozen six competency plan
evals/cases/case-01/      frozen opening answer and response brief
evals/metrics/            coverage, guardrails, allocation, branching, the report table
evals/results/            raw run records, one file per run, never hand edited
trajectories/             agent traces with full prompts, see its README for the map
tests/                    mirrors solution/ and evals/
```

Two things about this layout are load bearing rather than tidy:

**Agent instructions are files, not string literals.** The prompt you read *is* the prompt that runs.
[`prompt_files.py`](solution/adapters/prompt_files.py) parses the fenced blocks straight out of the
markdown that documents them, so there is no second copy to drift.

**Session records are append only and never rewritten.** Metrics and trajectories are derived from
them and from nothing else. A record you could tidy up afterwards would not be evidence.

### Docs

| File | What is in it |
| --- | --- |
| [PREREGISTRATION.md](PREREGISTRATION.md) | the prediction and the metric definitions, fixed before any run |
| [CHANGELOG.md](CHANGELOG.md) | one entry per experiment, including the ones that were removed |
| [REPRODUCTION-GUIDE.md](REPRODUCTION-GUIDE.md) | clean machine setup, exact commands, expected output |
| [research/sources.md](research/sources.md) | every external quotation, reproduced in full |
| [research/interview-guidance.md](research/interview-guidance.md) | the structured interview literature the rules come from |

---

## Notes

Everything here was written for this hackathon. What is used rather than written: Python and its
standard library, PyMuPDF for PDF text extraction, prompt_toolkit and rich for the console, PyYAML,
httpx, pytest. Models are reached through the Claude Code CLI or a local Ollama server, so no hosted
AI API is called anywhere.

**No CV is committed, redacted or not.** `evals/cases/case-01/cv.pdf` is a derived artifact:
`interview prepare` rebuilds it from a `cv-original.pdf` that never enters the repository, deleting
contact details from the PDF's text layer rather than covering them with a rectangle.

**No claim of model independence is made anywhere in this project.** The cross model check was dropped
when the judge moved onto the interviewer's model (`PREREGISTRATION.md` §3d), so whether this result
is about the architecture or about one model is deferred, not demonstrated.
