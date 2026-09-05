# A technical interviewer that cannot tunnel

An AI screening interviewer whose topic coverage is guaranteed by code rather than asked for in a
prompt.

> **Status, 2026-08-31.** The baseline (iteration 0) is measured and the pre-registered prediction
> **failed**: it beat the prediction on coverage, which [`PREREGISTRATION.md`](PREREGISTRATION.md) §3
> defines as a failure — recorded as one in [`CHANGELOG.md`](CHANGELOG.md), not reframed. Auditing
> that run found two defects in the measuring instrument, corrected in §2b; every figure below
> carries the correction and its before-value.
>
> All three rungs above the baseline are **built**. Rung 1 has been run and is awaiting measurement.
> **Rung 2 was never run because of time left** — each rung costs a 25-minute human sitting and there was time for one
> more, which went to rung 3, the system this project claims. Rung 3 therefore switches on context
> isolation and the gate together, so a rung-1-to-rung-3 difference cannot be attributed to either
> alone. That is a gap in the evidence and it is reported as one, in
> [`CHANGELOG.md`](CHANGELOG.md), rather than renumbered away.

---

## The problem

### Who has it

Two people, and only one of them chose to be here.

**The hiring team** buying an AI screen. They are replacing a 25-minute human phone screen at a
volume no human team can staff, and what they get back is supposed to be evidence about whether a
candidate can do the job the posting describes.

**The candidate**, who bears the cost. They get one 25-minute window to show they can do a job that
lists six competencies, and no say in which of them they are asked about.

The evaluation role in this repository is a real micro1 posting —
[Full Stack Developer](roles/fullstack/role.txt), 50 openings, retrieved 2026-08-29 — chosen because
candidates applying to it are screened by exactly this kind of system.

### The bottleneck

A well-written prompt does not produce a well-*allocated* interview.

Give a capable model the job description, the candidate's CV, and an instruction to *dynamically
adjust questions based on the candidate's responses*, and it will do precisely that: the candidate
names a technology in their opening answer, and the model — being good at conversation — follows
it. Question two goes deeper on that technology. So does question three, and question four.

The obvious way to describe what goes wrong is "it never reaches the other competencies", and that
is the wrong description. A capable model usually does reach them, eventually. What it does not do
is decide *how much of the 25 minutes each one gets*. Four questions go to whatever the candidate
raised first; the remaining competencies get one apiece, at the end, shallow. The interview returns
one deep answer and five drive-by ones, and which competency got the deep treatment was decided by
the candidate's opening sentence rather than by the job.

Candidates describe exactly this shape. From a thread of people who sat the interview — *"she builds
on the answers and turns it into the same question with an additional detail or rebranded phrases
added to it"*; *"every question seemed to one-up the last"*; *"almost half the interview was about
technical specs that no one knows by heart"*; and, from someone applying to annotate videos,
*"mention something tangentially math related and soon she will be asking you to solve The Riemann
Hypothesis"*. Nobody in that thread says a competency went unasked. They say the interview kept
going deeper into one.

Four self-selected posts are motivation, not measurement, and
[`research/evidence/candidate-reports.md`](research/evidence/candidate-reports.md) reproduces them
in full with that limit stated rather than implied — including the two complaints this project
does *not* address.

That is not a bug in the model. It is what "adjust to the candidate's responses" means when nothing
counts what has been asked. Depth and breadth are in tension, and a system with no representation of
breadth resolves the tension in favour of whatever is in front of it.

Two consequences, and both land on the candidate:

- **They are rated on evidence of uneven quality**, deep in one place and thin everywhere else,
  without knowing which competency drew the depth or why.
- **It is not the same interview twice.** The allocation depends on what the candidate happened to
  say first, so two equally qualified people get differently shaped screens — and so does the same
  person on a different day. A screen that is thorough on average is still a lottery for the
  individual, and at the volume these run, the losing tickets are numerous.

### Why it is worth solving

micro1's own published account of its interviewer, Zara ([arXiv:2507.02869](https://arxiv.org/abs/2507.02869)),
gives the scale and — unintentionally — the gap.

**Scale.** The paper reports 4,820 **unsuccessful** interviews over a three-day window — on the
order of 1,600 a day that did not succeed, with the total screening volume higher and unpublished.
Of those unsuccessful candidates, 89.3% never requested the feedback that would have told them why.

**The gap.** Zara measures well on what it measures:

| Metric (paper §5.1) | Human-led | Previous system | Zara |
| --- | ---: | ---: | ---: |
| Technical question quality | 7.78 | 8.38 | **8.60** |
| Conversational dynamics | 5.49 | 7.77 | **8.27** |

Both are **per-turn** properties. A question can be excellent and the conversation can flow, turn
after turn, while the session as a whole never leaves one topic. Neither number would move. Nothing
published measures whether an interview covered the role.

That is the gap this project addresses: **coverage is a session-level property, and per-turn quality
cannot see it.**

No claim is made here about how Zara is actually implemented. The paper states it *"briefly touch[es]
on phase (1) and (2) but focus[es] specifically on phases (3) and (4)"* — the interview-conduct policy
is not published. [`baseline/prompt.md`](baseline/prompt.md) is therefore labelled as *the obvious way
to build this*, written in good faith, not as a reconstruction of theirs. All quotations are
reproduced in [`research/sources.md`](research/sources.md) so they can be checked without leaving the
repository.

---

## The approach

**Coverage comes from the job description. Candidate answers fill slots; they never define them.**

The job description is turned once, offline, into a frozen plan of six competencies
([`roles/fullstack/slots.yaml`](roles/fullstack/slots.yaml)), reviewed and edited by a human before it
is committed. From that point it is read-only: it is the denominator of the primary metric, so a plan
that moved would silently invalidate every comparison.

Three properties are then enforced in code rather than requested in a prompt:

- **Topic selection never reads the candidate's answers.**
  [`scheduler.py`](solution/domain/scheduler.py) decides what is asked next from the plan and the
  clock alone. That is the whole anti-tunneling mechanism, and the module is under eighty lines.
- **Every question is verified before the candidate sees it.**
  [`gate.py`](solution/domain/gate.py) rejects a question that reaches for a technology the candidate
  raised outside the competency being asked about. It is a set comparison, not a judgement: an
  anti-tunneling property that depends on a model behaving well is a hope, not a guarantee.
- **Every claim the model makes about the CV is checked against the CV.**
  A model asked for a verbatim quote will sometimes return a fluent paraphrase instead. Quotes are
  compared character for character ([`quotes.py`](solution/domain/quotes.py)); one that fails is
  discarded and the competency recorded as unevidenced, because a claim nobody verified is not
  evidence.

Two consequences of that design are worth stating, because both surprise people:

**Depth is decided by the clock, not by the answer.** A competency gets one question, plus at most
one follow-up when the schedule can still afford every competency that has not been asked yet.
Nothing reads how good an answer was. That is what makes the ceiling a property of the code rather
than of a run — and it is also the cost: six competencies in 25 minutes is one or two questions
each, whoever schedules them.

**Withholding the transcript is also what removes the waiting.** Because the next question does not
depend on the answer being given, it is composed *while* it is given. In the rung that still reads
the transcript, 409 of 1491 seconds — 27% of the interview — were the candidate watching a terminal
think ([`session-20260831-153049.jsonl`](evals/results/iteration-01/session-20260831-153049.jsonl)).
A prompt-driven interviewer cannot avoid that: it is handed the transcript and asked to react to it,
so its next question cannot exist before the answer does.

The operational rules the interviewer follows are in
[`research/interview-guidance.md`](research/interview-guidance.md), grounded in the
structured-interview literature — including the finding that *restricting* improvised follow-up
improves psychometric quality, which is the opposite of what a conversational model does by default.
That file carries its own caveat about which figures come from full readings and which from indexed
excerpts; per [`research/sources.md`](research/sources.md), no figure from it is quoted here until it
has been re-verified against the primary source.

### What is measured

Coverage on its own is a weak claim — a fixed questionnaire scores 6/6 and is a worse interview. So
it is measured against two guardrails that pull in opposite directions:

| Metric | What it counts | Good looks like |
| --- | --- | --- |
| **Coverage** (primary) | competencies asked about at least once, out of 6 — reported as the **worst** run, not the mean | high |
| **Longest chain** | consecutive questions spent on a single competency | at the schedule's ceiling, never above |
| **Carry-over** (guardrail) | questions reaching for a term the candidate raised, outside the competency being asked | near zero |
| **Grounding** (guardrail) | questions reaching into the CV for something specific to this candidate | high |
| **Branching** | distinct competencies the interviewer would reach for at one decision point, sampled k times | exactly one |

Coverage is a *set*, so on its own it scores an evenly allocated interview and one that spent four
of its ten questions on a single situation identically. **Longest chain** is what separates them,
and its ceiling is a property of the code rather than of the run: a scheduled interviewer asks one
primary question per competency plus at most one follow-up, so it cannot exceed two. A single
prompt has no ceiling, because nothing in it counts what it has asked.

**Branching** measures the other half — whether the topic was determined at all. It rewinds a
recorded interview to each turn boundary and asks the interviewer k times what it would say next.
The scheduler answers with one competency every time, because `decide_next` never reads the
transcript's content. A prompt answers with a spread, and the width of that spread is how much of
the candidate's screen was a draw. It costs one human sitting rather than k: the answers are a real
respondent's, given once and replayed.

The pair is what separates a *personalised* interview from a *tunneled* one. A fixed questionnaire
scores zero on both guardrails. A tunneling interviewer scores high on carry-over and low on
grounding. Neither is what we want, and no single number could say so.

Both guardrails are set comparisons with no model involved: they ask whether a technology the
candidate raised, or one from their CV, appears in the question. A layer name like *backend* does
not count — that correction is [`PREREGISTRATION.md`](PREREGISTRATION.md) §2b, made after the first
run showed the guardrail reporting 100% on the strength of `backend`, `api` and `request` while
missing five consecutive questions about one idempotency key.

**Coverage rests entirely on a model, and it is not stable.** A keyword layer used to precede the
judge; measured over the first run it resolved 0 of 11 questions, and it was removed rather than
kept as decoration. Worse, three measurements of the *same record* returned 5/6 twice and 4/6 once,
because the judge moved two labels. That is ±1/6 of measurement error before any interviewer
changes, and §2b records it rather than reporting the flattering run. It is the reason a
hand-labelled agreement sample is not optional here.

---

## Results

The prediction below was registered in [`PREREGISTRATION.md`](PREREGISTRATION.md) before any run,
together with the result that would prove the premise of this project wrong. **It was proved
wrong.**

| | Iteration 0 (baseline) | Iteration 3 (the solution) |
| --- | --- | --- |
| **Predicted** | coverage ≤ 2/6, carry-over ≥ 50% | coverage ≥ 6/6, carry-over ≤ 10%, grounding materially higher |
| **Measured** | coverage **4/6–5/6**, carry-over **18%** | not run |

The falsification clause was the part that cost something: **if iteration 0 reaches coverage ≥ 3/6,
the prediction has failed.** It reached 5/6. That is recorded as a failed prediction and the premise
is being re-examined — not quietly reframed as a weaker claim, and not re-run with a different
opening answer until it tunnels.

Three things about that row, none of them comfortable:

- **Coverage is a range because the instrument is not stable.** Three measurements of the same
  record returned 5/6 twice and 4/6 once — the judge moved two labels. ±1/6 of error before any
  interviewer changes.
- **The 18% carry-over was first measured as 100%**, and the 100% was wrong: it counted `backend`,
  `api` and `request` — layer names, not technologies — while missing the five consecutive questions
  about one idempotency key. §2b records the correction and both numbers.
- **Coverage 5/6 overstates what the interview did.** Eleven questions covered three subjects; one
  continuous conversation about an idempotency key was credited to four different competencies. The
  candidate's own verdict was that the interview never let them show the breadth the role asks for,
  and on that the metric and the person disagree.

Coverage of 6/6 is achievable by construction once the scheduler exists, so on its own it proves
nothing. The claim that carries weight is the pair: full coverage **while** questions stay grounded in
the candidate's own background.

Every figure that appears here will point at a file under [`evals/results/`](evals/results/), produced
by `interview report` from the raw session records. Nothing is hand-entered.

---

## Running it

See **[REPRODUCTION-GUIDE.md](REPRODUCTION-GUIDE.md)** for a clean-environment setup and the exact
commands.

There is an honest constraint worth knowing before you start: **an interview needs a human typing for
25 minutes.** There is no simulated candidate, deliberately — a model playing the candidate would be
a second system entangled with the one being measured, and coverage would stop meaning what it says.
So the guide offers two paths: replay the committed records to reproduce every published number in
seconds, or sit the interview yourself with your own CV to check the claim on a new case.

```
pip install -e ".[dev]"
interview --help
```

| Command | Does |
| --- | --- |
| `interview check` | one cheap model call, so a broken provider surfaces in seconds |
| `interview prepare` | rebuilds the derived inputs — the only command that changes anything |
| `interview run --baseline` | conducts one interview, and records the experiment |
| `interview run --solution` | the same interview, conducted by the finished system |
| `interview measure` | metrics for a session |
| `interview branch` | resamples a recorded interview's turns, to see what else it might have asked |
| `interview report` | baseline vs solution, as a table |
| `interview show` | renders a session or trajectory, prompts included |
| `interview show-prompt` | prints exactly what the interviewer at a given rung is sent |

---

## Repository

```
README.md                 you are here — user, bottleneck, value, results
CHANGELOG.md              the Improvement Changelog: one entry per experiment
REPRODUCTION-GUIDE.md     clean-environment setup, exact commands, expected output
PREREGISTRATION.md        the prediction and the metrics, fixed before any run

baseline/prompt.md        iteration 0 — the fair floor, and the prompt that executes
solution/                 the system; domain / application / adapters
  agent_instructions/     the instructions that shape each agent, as readable files
roles/fullstack/          the job posting and its frozen six-competency plan
evals/cases/case-01/      the candidate's CV, frozen opening answer, response brief
evals/results/            raw run records, one file per run, never hand-edited
trajectories/             agent traces with full prompts — see its README for the map
```

Two things about this layout are load-bearing rather than tidy:

**Agent instructions are files, not string literals.** The prompt a reviewer reads *is* the prompt
that executes — [`prompt_files.py`](solution/adapters/prompt_files.py) parses the fenced blocks out of
the markdown that documents them, so there is no second copy to fall out of date.

**Session records are append-only and never rewritten.** Both the metrics and the trajectories are
derived from them and from nothing else. A record that could be tidied up afterwards would not be
evidence.

---

## What existed before, and what was added

Everything in this repository was written for this hackathon. Nothing here predates it.

What is *used* rather than written: Python and its standard library, PyMuPDF for PDF text extraction,
prompt_toolkit and rich for the console interview, PyYAML, httpx, and pytest. The models are reached
through the Claude Code CLI or a local Ollama server; no hosted AI API is called anywhere, and there
is no API key in this project.

No CV is committed, redacted or not. `evals/cases/case-01/cv.pdf` is derived: `interview prepare`
rebuilds it from a `cv-original.pdf` that never enters the repository, deleting contact details from
the PDF's text layer rather than covering them with a rectangle.

---

## Main failure mode and the hot take

**Written once the ladder has run.** It belongs to the evidence, not to the plan, and writing it now
would mean inventing a lesson before the experiment that teaches it.

What can be said in advance is what this project is set up to find out, and the answer is not
guaranteed to be flattering: it is entirely possible that a frontier model given a good prompt does
*not* tunnel, in which case the premise fails and that becomes the finding. The pre-registration says
so, in writing, from before the first run.

One thing is already deferred rather than demonstrated: whether this result is about the architecture
or about one model. The cross-model check was dropped when the judge moved onto the interviewer's
model (`PREREGISTRATION.md` §3d), so **no claim of model independence is made anywhere in this
project** until a second model has actually been run.
