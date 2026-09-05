# Improvement Changelog

The baseline comparison shows the *size* of the improvement. This file shows *where it came from*.

**How this file is kept**, following agentic-workflows.md §5:

- One entry per **meaningful experiment**, never per commit.
- Every entry is appended **at the moment of the experiment**, not reconstructed at the end.
  Reconstructed evidence is vague evidence.
- Every entry re-measures with the **same evaluation method** — `interview measure` over the
  session record, with the metric definitions frozen in `PREREGISTRATION.md` §2.
- **Experiments that were removed stay in the table**, with what their removal taught. A change
  that made things worse is evidence about the problem.
- Every figure quoted here points at a file under `evals/results/`. No claim without evidence.

The evidence column links the session record and its `.metrics.json`. `interview report` regenerates
the full table from those files at any time, so nothing here is hand-computed.

---

## Not rungs of the ladder

Changes to the machinery rather than to the interviewer: they are not part of the measured
comparison, but several of them changed what the repository is allowed to do once the ladder
starts. In date order within each group; the entries about rung 1's defects sit at the end,
where they were written.

### 2026-08-30 — commands separated, and the experiment made mechanical

| | |
| --- | --- |
| **What** | One entry point (`interview`) with commands separated by what they may touch. `prepare` is the only command that rebuilds a derived input; `run` is read-only and stops with the command that fixes what it found. |
| **Why** | `run` used to rebuild the redacted CV and regenerate the résumé evidence on its way past. An interview that silently rewrites its own inputs produces a measurement nobody can reason about afterwards. |
| **Also** | `evals/experiment-lock.yaml` — the digests of every input `PREREGISTRATION.md` §1 fixes. The baseline run writes it; every run after it compares against it and refuses to start if an input moved, the recovery being `interview run --baseline --restart`, which begins the ladder again; every session record stamps the lock it ran under; `interview report` refuses to build a table spanning two experiments. Recorded as `PREREGISTRATION.md` §4a. |
| **Evidence** | `tests/application/test_experiment.py` — one test per item §4 lists as invalidating. `tests/adapters/test_cli.py` — `run` never rebuilds, and a measured run without a lock stops. |
| **Learning** | §4 was a list of promises. Three of the six were mechanisable, and the two that were not (a respondent who answers differently; someone deleting the lock) are now the *only* two, which is a much smaller thing to ask a reader to take on trust. A separate `freeze` command was built first and then removed: there is no case in which one would measure without recording what was measured against, so it could only ever have been a step to forget. Recording belongs to the run that needs it. |

### 2026-08-30 — trajectory capture, before it is needed

| | |
| --- | --- |
| **What** | `TracingProvider` wraps any provider and records every model call — system prompt, user prompt, schema, raw reply, and each retry separately — into the session record or a file under `trajectories/`. |
| **Why** | Nothing recorded a prompt. The turn loop stored only how long generation took; the slot extractor, the résumé matcher and the judge stored nothing. agentic-workflows.md §9 is explicit that trajectories are captured as work happens and cannot be reconstructed later, so this had to exist before iteration 0, not after it. |
| **Evidence** | `tests/adapters/test_tracing.py`, including the retry and failure cases — a call that succeeded on its second attempt is a different trace from one that succeeded immediately. |
| **Learning** | The decorator has to wrap the provider rather than sit beside it, because retries happen inside `complete_json` where no caller can see them. A trajectory assembled from the outside would have shown the successful attempt and silently dropped the failed one. |

### 2026-08-31 — the interviewer stops being told it is being studied

| | |
| --- | --- |
| **What** | `role.txt`'s comment header no longer reaches the model. It is stripped on the way out by `solution/adapters/role_text.py`; the file on disk is untouched, so `slots.yaml`'s `role_sha256` provenance and the experiment lock both still match and the slot plan needs no re-freezing. |
| **Why** | The header reached the system prompt: *"This posting is used as the evaluation role precisely because it is a real micro1 opening: candidates who apply to it are screened by the AI interviewer this project examines."* The interviewer would have been told it was the subject of a study. |
| **Evidence** | `tests/adapters/test_role_text.py` (the header goes, the four `##` headings stay, the file keeps its citation) and `tests/application/test_prompt_contamination.py` (assembled through the same function the run uses). |
| **Learning** | The leak was not in the prompt file — it was in an *input* the prompt file interpolates, and nobody thought of a data file as carrying instructions. Worth generalising: a template is only as clean as the things substituted into it, and provenance headers are exactly the kind of well-intentioned metadata that rides along. |

### 2026-08-31 — the interviewer stops being told the time

| | |
| --- | --- |
| **What** | The system block no longer says *"The interview lasts 25 minutes in total. Pace yourself…"*, and the per-turn `Elapsed: N of 25 minutes` is gone. `<<TRANSCRIPT>>` is the only placeholder the user prompt still has. The candidate's own console countdown is unchanged — that one is for the person answering. |
| **Why** | Two reasons, and the second is the one that makes this defensible on its own. First: a model told how much time is left can pace its own coverage against the clock, which is the thing being measured. Second, and decisive: `baseline/prompt.md` already listed *"Time-aware scheduling"* as something a later rung adds. A baseline that paced itself against a clock made that row false and left that rung with nothing to contribute. Removing it makes a claim that was already written become true. |
| **Evidence** | `tests/application/test_prompt_contamination.py::test_no_time_information_at_all`, over the real assembled prompt. |
| **On baseline fairness** | §4 of the hackathon brief warns that a strawman baseline invalidates the Measured Improvement score, so removing a capability from the baseline needs a reason that is not "it scored too well". The ladder table is that reason: *time-aware scheduling* was written down as a later rung's contribution before iteration 0 existed, and a baseline that paced itself against a clock made that row false. A reader who does not find it sufficient has everything needed to say so. |

### 2026-08-31 — `interview show-prompt`, and why it exists

| | |
| --- | --- |
| **What** | A command that assembles and prints the exact system prompt and user template, through the same `assemble_prompt` the run and the contamination test use. |
| **Why** | The `role.txt` leak went unnoticed because answering "what does the model actually know" required digging through a session record for a `model_call` event. It should have been one command, and now it is. |
| **Learning** | When a property matters and is invisible, the fix is not to be more careful. It is to make it cheap to look. |

### 2026-08-31 — interrupted runs record what they did

| | |
| --- | --- |
| **What** | The `interview_ended` event on the Ctrl-C path now carries `elapsed_seconds` and `questions_asked`, read back from the record. |
| **Why** | It carried only `reason`, so an interrupted run reported `elapsed=0.0min` and no questions however far it had got, and any measurement of it would inherit the zeros. |

### 2026-08-31 — the per-answer clock is removed

| | |
| --- | --- |
| **What** | No limit on an answer. The interview advances when the candidate submits; only the 25-minute total is enforced, checked at the turn boundary so an answer already under way is never truncated. `answer_deadline_seconds` becomes `expected_answer_seconds` — a forecast the scheduler plans with, which nothing measures an answer against. `over_deadline` is gone from the domain, the records and the metrics. |
| **Why** | The interview being modelled is **spoken**: a real candidate talks until the answer is done. Translating that into a 120-second typed window added a pressure the original does not have. |
| **Evidence** | `tests/adapters/test_console_io.py` — the console has no per-answer clock and no argument by which one could be passed. `tests/application/test_runner.py` — an answer may run past the budget; no question is asked after it. |
| **Cost, stated** | This is the confound the deadline existed to prevent: answers can lengthen between runs, shortening the interviews and depressing coverage for a reason that is not the interviewer. It is no longer prevented — it is measured. Each run reports count, mean, median, range and total of its answer durations, and `interview report` puts mean answer time and total answering time beside coverage so the two explanations are distinguishable. Recorded as `PREREGISTRATION.md` §1b. |
| **Also** | The replayed opening is charged the duration it actually took when given, recorded in the lock. A configured constant made the stimulus cost one thing in the run that captured it and another in the ten that replay it — an asymmetry at the exact point the frozen opening exists to remove. |
| **Learning** | The deadline was never a design choice; it was an artefact of translating a spoken protocol into a typed one, and it survived because it had a good local justification (removing a confound) that nobody weighed against what it distorted. Worth watching for: a guard that solves a measurement problem by changing the thing being measured. |

### 2026-08-30 — the baseline captures its own opening answer

| | |
| --- | --- |
| **What** | The pilot-then-paste flow for producing the opening answer is gone. The baseline run of an experiment that has none captures it: the candidate answers the first question the way they answer any other, and it is frozen into `opening-answer.md` in code, at the moment it is given. The experiment lock moves to the end of that run, since the opening it is identified by does not exist until then. |
| **Why** | The old flow was: run a pilot, Ctrl-C it, copy the printed block, paste it into a file, then run the real interview. Four steps and two files to get one answer, and the first attempt at it was broken on the interrupted path — which was the *documented* path. |
| **Evidence** | `tests/adapters/test_cli.py::TestTheBaselineRecordsTheExperiment` — capture, replay by a later rung, the empty-answer case, and that a pilot freezes nothing. |
| **Cost, stated** | `PREREGISTRATION.md` §1 had the response brief frozen *before* iteration 0. It is now built from iteration 0's own transcript, so that rung is answered from memory and 1–10 from the brief. Recorded as §1a; it is a real asymmetry and it is disclosed rather than absorbed. |
| **Learning** | Twice now the same shape: a step justified as "a decision needs a person" turned out to be a step that could only be forgotten or fumbled. The real decision was elsewhere — typing the answer, not filing it. Automating the filing made the artifact *more* faithful, not less, because it removed the chance to polish the answer between saying it and freezing it. |

### 2026-08-30 — a fumbled opening answer can be retaken

| | |
| --- | --- |
| **What** | `interview run --baseline --restart` now re-captures the opening answer. It replaces the frozen one **at the moment a new one is given**, never before, so a restart abandoned before answering leaves the previous experiment byte-identical. |
| **Why** | A fumbled opening answer had no way back. `--restart` looked like the way and silently was not — it only fired when an *input had drifted*, and a wrong opening answer is not drift, it is just wrong, so the run would replay it instead of refusing. |
| **Evidence** | `tests/adapters/test_cli.py::TestRetakingTheOpeningAnswer` — re-capture with nothing drifted, the discarded answer still readable in its own record, and an abandoned restart changing nothing. |
| **Learning** | The guard was written for the case I imagined (someone swaps the CV) and was blind to the case that actually happens (someone misspeaks). Worth stating in the write-up: a guardrail tested only against its designer's imagined misuse will pass every test and still fail the first real user. |

### 2026-08-31 — the terminal that looked frozen, and the sitting it cost

| | |
| --- | --- |
| **What** | `CandidateIO.waiting`, a context manager the shared turn loop holds open while the interviewer composes. `ConsoleIO` fills it with a spinner carrying the time left in the interview; it does nothing by default, so the canned and scripted implementations are untouched. |
| **Why** | The first sitting of iteration 1 was abandoned 35 seconds in. The record says why: `Q [opening] gen=0.01s`, the frozen opening replayed instantly, then `Q [frontend] gen=34.8s` with nothing on screen at all. The countdown lives in the answer prompt, which only exists while an answer is being read — so during generation there was never anything to see. That was true of the baseline too; it went unnoticed there because that run *captured* the opening, so the candidate was typing, and the toolbar was up from the first second. |
| **Evidence** | `tests/adapters/test_console_io.py` — the clock arithmetic, and that **both** IO wrappers delegate rather than inheriting the no-op. That last one is the test that matters: `FrozenOpeningIO` and `CapturingOpeningIO` forward `present` and `note_progress` and would have silently swallowed this, leaving a live run with no indicator while every test passed. |
| **Also** | A run the candidate interrupted is no longer a measurement. `measure` records `interrupted`, `report.collect` skips it. The hazard was a glob: after a retake both records sit in `iteration-01/`, and `interview measure .../session-*.jsonl` would have measured both and reported the rung as two runs, one of them two questions long — in the headline table, silently. |
| **The abandoned record** | Kept, at `evals/results/aborted/session-20260831-145052.jsonl`, rather than deleted. §4 lists selective reporting as invalidating and a record that vanishes without trace is the exact shape of that; it is also the evidence for this entry. |
| **Learning** | The indicator is presentation and the countdown is presentation, so neither had a test asserting a candidate could *see* them at each moment of a turn — only that the console could render them when asked. The gap was between two components that each worked: a prompt that shows a clock, and a loop that spends thirty seconds not using it. Worth watching for: the states a user sits through that no component owns. |

### 2026-08-31 — the instrument was measuring the domain, not the drift

| | |
| --- | --- |
| **What** | The keyword layer (`evals/metrics/labelling.py`) is deleted; every question is labelled by the blind judge. A committed stoplist of structural vocabulary — `frontend`, `backend`, `api`, `ui`, `request`, `query` and eighteen others — is subtracted by `is_carry_over` and `is_grounded` and by nothing else. Iteration 0 was re-measured with the corrected instrument; all three measurements are committed. |
| **Why** | The respondent said the interview had not let them show competence — only React and idempotency, no Node/Nest/Go, nothing on code review or documentation. The instrument said coverage **83%**. When the metric and the person disagree that far, the metric is what gets audited, and it did not survive: carry-over counted `backend`, `api`, `ui` and `request` on 11 questions out of 11, and was blind to the five consecutive questions about one idempotency key. §2 defines carry-over as reaching for *"a technology the candidate raised"*. A layer is not a technology. |
| **Why the keyword layer went** | It resolved **0 of 11** and mislabelled two: `React Query` decomposes into `react` + `query`, and `query` belonged to the data layer, so two purely frontend questions read as reaching into it. The cause is structural — `api_contract` and `cross_boundary_debugging` are *relational* competencies defined in the other slots' vocabulary, so no word-matcher separates a question about the boundary from one that merely names both sides. |
| **Evidence** | Removing it changed nothing, verified two ways: `label_by_rule` returned `None` on all 11 questions, so both paths were the same code; and re-measuring reproduced the pre-removal labels exactly. The stoplist moved carry-over **100% → 18%** and grounding **18% → 9%**. `tests/metrics/test_rates.py` holds the cases the run exposed, including the guard that no named technology may sit on the stoplist. |
| **What it costs** | Coverage is now 100% a model's classification with no deterministic layer beneath it, and `interview measure --no-judge` stops being a reproduction path — though it already returned 0/6, so the guide's claim was already false and now says so. And the corrected carry-over is a **lower bound**: `idempotency`, `refetch` and `race condition` stay invisible, being lowercase terms in no curated list. Adding them after seeing them in the transcript is the post-hoc tuning §4 forbids, so they stay uncounted and disclosed. Recorded as `PREREGISTRATION.md` §2b. |
| **The finding underneath both fixes** | **Coverage is not stable.** Three measurements of the same record: two returned 5/6 with identical labels, one returned 4/6 because the judge moved two idempotency questions from `api_contract` to `backend`. The primary metric carries ±1/6 of measurement error from the judge alone, on identical input — so any baseline-versus-solution difference smaller than that is noise, and §3's 6/6 target has to clear it rather than land inside it. The 4/6 measurement is committed beside the others; §4 forbids reporting only the flattering one. |
| **Learning** | Two metrics were built on one vocabulary serving three purposes — classifying a competency, defining what belongs to it, and deciding what counts as drift. Those need opposite properties: classification wants *discriminative* terms, drift detection wants *specific* ones, and the slot keywords are neither. The tell was there before the run and nobody read it: a guardrail whose keyword list is also the thing it measures against cannot be wrong in a way that shows up as an error. It shows up as a confident number. |

### 2026-08-31 — candidate reports, and what they changed

| | |
| --- | --- |
| **What** | `research/evidence/candidate-reports.md` — four accounts from candidates who sat the interview, transcribed verbatim, with `research/sources.md` §4 pointing at them. The README's bottleneck section is rewritten around them: the failure is described as *allocation* rather than as missed topics. |
| **Why** | The bottleneck was written from a hypothesis about what a conversational model does. These are people describing what it actually did to them, and they describe something narrower and more specific: *"turns it into the same question with an additional detail added"*, *"every question seemed to one-up the last"*, *"almost half the interview was about technical specs"*. Not one of them says a competency went unasked. |
| **Evidence** | The file itself, with the thread permalink. **It is motivation, not measurement**, and says so in its own terms rather than in a footnote: self-selected posters, n = 4, roles other than this project's evaluation role, and quotes transcribed from screenshots because Reddit blocks automated fetching and its JSON API returns 404 — verified against a control subreddit, so it is the route rather than the subreddit. No rate or proportion is derived from them anywhere. |
| **Also** | The file names the two complaints this project does **not** address — conversational manner, which the Zara paper already scores well (§5.1), and broken post-interview feedback, which is the published part of the system. A gap that is written down is a gap; one that is quietly omitted is a claim. |
| **Learning** | Three of the four reports are from non-technical roles — voice coaching, video editing, annotation — and describe the same shape. That is consistent with the behaviour being a property of the interviewing policy rather than of any one domain, which is the premise being tested. Consistent with; four self-selected reports cannot establish it, and the file says so. |

### 2026-08-31 — measuring what coverage cannot see

| | |
| --- | --- |
| **What** | Three additions, none of which redefines an existing metric. `evals/metrics/allocation.py` counts how the question budget was divided — `longest_chain` (consecutive questions on one competency), `max_slot_share`, normalised entropy. `evals/metrics/branching.py` and `interview branch` rewind a recorded interview to each turn boundary and sample the next question k times, reporting how many distinct competencies the interviewer would reach for. `interview report` stops keeping only the newest run of a rung and reports the **worst** run with the spread beside it. |
| **Why** | Coverage is a set, so it scores an evenly allocated interview and one that spent four of ten questions on a single situation identically. The second is what a prompt-driven interviewer actually does, and it is what the scheduler's follow-up budget exists to prevent — but nothing measured it, so the ladder had no way to show its own contribution. |
| **Evidence** | `tests/metrics/test_allocation.py` (a chain broken by an unlabelled question; the denominators that decide whether an unresolved question flatters the interviewer), `tests/metrics/test_branching.py` (the sampling guard, and the transcript rebuilt through the same `with_question` the runner uses), `tests/metrics/test_report.py` — `report.py` had no tests at all before this. |
| **Also** | Two defects found on the way. `report.collect` crashed on a results directory outside the repository, because `relative_to` raises rather than falling back — `experiment.py` already had the fallback pattern and it is now used in both. And `interview branch` refuses a provider pinned to `temperature: 0` or a fixed seed: k identical samples would have read as a perfectly consistent interviewer when they measured the seed. |
| **Cost, stated** | Declared before any measured run, but *informed by* exploratory runs that were not retained as results. That is piloting rather than measurement, and `PREREGISTRATION.md` §2a discloses it rather than leaving a reader to wonder. §2a also states plainly what this is not: it does not rescue the §3 prediction, and no new metric is promoted to primary. |
| **Learning** | The metric was chosen to catch the failure that was imagined — an interviewer that never reaches five of six competencies — and it is blind to the failure that happens, which is one that reaches all six and allocates them 4:1:1:1:1:1. Worth generalising: a metric shaped like the hypothesis will confirm or refute *that*, and stay silent about whatever is actually going on. Coverage was not wrong; it was answering a smaller question than the one the candidate cares about. |

### 2026-08-30 — response brief corrected against the current CV

| | |
| --- | --- |
| **What** | `evals/cases/case-01/response-brief.md` said `frontend` had no hands-on CV evidence. Commit `f756b59` resolved the evidence against a new CV and it is `true`, with a verbatim React.js quote. The brief now names `cross_boundary_debugging` as the only unevidenced slot, and uses the anonymised employer names the committed CV uses. |
| **Why** | The respondent answers from the brief. A brief naming an employer the CV does not would put terms in the transcript that the interviewer never saw — counted against grounding and towards carry-over for a reason unrelated to the interviewer. |
| **Learning** | Derived artifacts drifting from their inputs is the same failure the preflight was built for, one layer up: the preflight caught the *machine-readable* copy going stale and had nothing to say about the prose describing it. |

### 2026-08-31 — the response brief exists, two rungs later than planned

| | |
| --- | --- |
| **What** | `response-brief.md` is written, transcribed from the iteration 0 **and iteration 1** transcripts as facts organised by competency. Every line is something the respondent said in a recorded interview. |
| **Why it is late, stated plainly** | §1a planned it as an output of iteration 0, to be used from rung 1 onwards. Nobody produced it, and **rung 1 was answered from memory like rung 0**. It was not skipped as a decision; it was a manual step in a pipeline where every other step is mechanical, and manual steps in mechanical pipelines get forgotten. That is the same failure the removed `freeze` command and the removed pilot step were both fixes for, arriving a third time. |
| **What it costs** | Rungs 0 and 1 unbriefed, rungs 2 and 3 briefed — the asymmetry §1a described, one rung later. Bounded by two things: every fact in the brief was said *unbriefed*, so it cannot add substance to a later answer, and the metrics are computed over the interviewer's questions, never over answer quality, so it can only reach the numbers by changing what gets asked next. Recorded as `PREREGISTRATION.md` §1c. |
| **Also** | One competency is recorded as a **gap rather than filled in**: iteration 0 asked twice for a specific cross-boundary debugging incident and got none, the second attempt running out of time. The brief says so and tells the respondent not to invent one. A brief that quietly supplied the missing story would have manufactured evidence for the one competency the CV marks unevidenced — which is the competency the whole role description turns on. |
| **Learning** | The pipeline is mechanical everywhere the artifact is machine-readable and manual everywhere it is prose, and the prose steps are the ones that get skipped. The lock *tracks* the brief, so it noticed nothing: tracking records what a file's digest was, not whether the file says anything. |

---

### 2026-08-31 — what iteration 1 was like to sit, and the three things it exposed

**Written before rung 2 is run**, from the respondent's account of the rung 1 sitting and from the
record that confirms each complaint. All three are changes to the interviewer, so they are recorded
here and as `PREREGISTRATION.md` §3f before any further measurement.

**Why an account rather than a metric.** None of these three shows up in coverage, carry-over,
grounding or `longest_chain`. Rung 1 measures well on the thing under test and was still an
unpleasant interview to sit, and the only instrument that caught that was the person sitting it.

| | |
| --- | --- |
| **1. 27% of the interview was a frozen terminal** | The record: 409 of 1491 seconds went on composing questions, one turn taking 82 s. The candidate watches a spinner for a quarter of their screen. |
| **What fixes it** | From rung 2 the transcript is withheld, so the next question does not depend on the answer being given — and it is composed while it is given. `Interviewer.may_compose_ahead` states the capability; the baseline and rung 1 cannot have it, because they are handed the transcript and asked to react to it. |
| **How it stays honest** | Speculative and validated: the schedule is consulted again once the answer's real duration is known, and a question composed for a competency it no longer wants is discarded and regenerated live. `composed_ahead`, `speculation_used` and `speculation_discarded` land in the record, so the hit rate is a count. Only primaries are composed ahead — a follow-up needs the answer. |
| **What it costs, stated** | With the wait off the clock, more questions fit in 25 minutes. **Rungs 2–3 are not comparable with rungs 0–1 on question count** — only on the rates, which are per-question. Measured offline: a 3 s-per-question model charged 15 s of thinking to rung 1 and 0 s to rung 2, on the same six-competency schedule. |
| **A limit, not hidden** | The opening answer is *replayed* instantly, so there is no typing to hide the first question behind. Turn 1 is charged in full; every turn after it is free. |

| | |
| --- | --- |
| **2. The follow-up did not follow anything up** | The respondent: *"ele não gerou uma nova pergunta de acordo com a minha resposta"*. Correct, and the cause was plain — `_generate` received identical arguments for a primary and a follow-up, so the model was never told it was deepening and wrote a second standalone question. Every turn opened *"Describe a time…"*. |
| **What fixes it** | The prompt is told, and is given **the candidate's answer to that competency's own first question, and nothing else**. A bounded exception to the isolation: the schedule has already chosen the slot and a follow-up cannot leave it, so nothing read here can move the interview. The gate's carry-over allowance is widened by exactly those terms — echoing the candidate is the entire point of a follow-up, and drift is what happens *across* competencies. |
| **Evidence** | `tests/application/test_scheduled_interviewer.py::TestAFollowUpFollowsSomethingUp` — the primary is told nothing, the follow-up gets that one answer and no other, and the same words in a primary about another competency are still rejected as drift. |
| **Also corrected: a wrong mental model, not a defect** | A follow-up is **not** triggered by a thin answer. Nothing reads answer quality. The schedule grants one when the clock affords it after every remaining competency is paid for. That is deliberate, and it is now said where a reader will see it rather than only in `scheduler.py`. |

| | |
| --- | --- |
| **3. It never acknowledged anything the candidate said** | The prompt forbade it outright: *"Do not greet, do not summarise the previous answer"*. The effect is a machine firing questions. |
| **What fixes it** | At most one short, neutral acknowledgment before the question, which may not name anything the candidate said. An isolated interviewer never read the answer, so it can only acknowledge, never summarise — the restriction and the honesty are the same thing. |
| **Evidence** | `tests/domain/test_gate.py::TestAcknowledgingTheAnswer` — a neutral opener passes, an opener that summarises the answer is still carry-over, and one that smuggles in a second question still fails the form rule. |

**Learning.** Three defects, none visible to any metric this project defines, all obvious within
five minutes of sitting the interview. The metrics were built to answer *did the interview cover the
role*, and they answer it — they say nothing about whether a person can stand to be in it. Worth
generalising: an evaluation harness measures the claim under test, and the experience of using the
thing is a separate instrument that only a user provides. Budget a sitting for it, and do not let
the fact that it produces no number make it optional.

### 2026-08-31 — five defects found auditing the tooling against the ladder it now has

Found by reading the code against the rungs that exist rather than the one that did when it was
written. None changes a published number; three were commands that only ever worked on iteration 0.

| Defect | What it did | Fix |
| --- | --- | --- |
| `interview branch` on any scheduled rung | Built its interviewer without the role and case directories, so it exited with a usage error — on exactly the rungs whose determinism it exists to demonstrate. | The directories and the follow-up budget are passed through. `tests/adapters/test_cli.py::TestTheToolsWorkAboveTheBaseline` |
| `schedule_ceiling` never reached the metrics | `measure_session` took the parameter and no caller passed it, so the field was `null` on every result and the `(the schedule allows 2)` line never printed. The number that turns `longest_chain` from a figure into a comparison was silently absent. | Derived from the record itself — a run with a `scheduler_decided` event has a schedule, and `run_metadata` now carries the follow-up budget it ran under. Read off the record rather than off config, so a run measured later is judged against its own budget. |
| `interview show-prompt` above the baseline | Refused with *"iteration N has no prompt to show yet"*, which stopped being true when the scheduled rungs were built. Agent instructions are a graded deliverable; this is how a reader checks them. | Renders any rung, and says which blocks are filled at that one. |
| `interview_ended` recorded the wrong reason | Every stop was logged `interviewer_finished`, even when the scheduler had ended on `time_exhausted`. The true reason existed only in the preceding `scheduler_decided`. | The interviewer reports why it stopped. Confirmed on a real smoke run, which now records `time_exhausted`. |
| `SessionStore.append` was not thread-safe | It also re-read the whole file to number each event. Harmless until the interviewer began composing on a second thread, at which point two writers would collide on a sequence number. | An in-memory counter under a lock. `tests/adapters/test_session_store.py` runs eight threads at 20 appends each and asserts the sequence is exactly 1..160. |

**Learning.** Four of the five are the same shape: a tool written when only iteration 0 existed,
never re-run against the rungs added later, and passing its tests the whole time because the tests
were written against the same assumption. The suite pinned the behaviour; nothing pinned the
*coverage* of the suite over the ladder. Worth watching for: code that is correct for the system as
it was.

### 2026-08-31 — the gate is stricter than the interview it guards, recorded before rung 3

**Declared before rung 3 is run**, so what follows is a prediction rather than an excuse.

`check_question` rejects a question that does not literally contain one of its slot's keywords, and
one that does not contain exactly one `?`. Both are stricter than the property they stand for, and a
smoke run showed both firing on good questions:

- **`off_slot` on relational competencies.** Two questions about `cross_boundary_debugging` were
  rejected and fell back to the generic template, because a question can be entirely about debugging
  across the boundary without using the words *debugging*, *bug* or *root cause*. The best question
  of the rung 1 sitting — *"Imagine the operations dashboard is displaying incorrect payment counts
  for Pix transactions compared to what you see when querying the database directly…"* — would be
  rejected on the same rule. This is the structural problem `PREREGISTRATION.md` §2b already found in
  the keyword labeller, arriving in the gate: `api_contract` and `cross_boundary_debugging` are
  defined in the other slots' vocabulary.
- **`form` on an imperative.** *"Walk me through one of those operational dashboards you built in
  React - what drove the need for it, what you implemented, and how it turned out."* was rejected for
  having zero question marks. The rule exists to stop compound questions and also catches a perfectly
  good behavioural prompt.

**It is being left as it is, deliberately.** §3e names a zero rejection rate as the outcome most
worth reporting, and tuning the gate after seeing which questions it rejects is the post-hoc
adjustment §4 forbids. **The prediction: rung 3 will show a non-zero fallback rate concentrated on
`cross_boundary_debugging`, and its grounding will be lower than rung 2's for that reason.** If that
happens it is a finding about deterministic verification of a relational property — that the
guarantee costs question quality — not a bug discovered afterwards.

### 2026-08-31 — rung 2 is not run, and rung 3 is therefore two mechanisms at once

**Written before the rung 3 sitting**, so that what follows is a stated limitation and not an
explanation produced after seeing a number.

**What happened.** Each rung costs a 25-minute human sitting and there was time for one more before
the deadline. Rung 3 was chosen over rung 2, because rung 3 is the system this project claims —
`interview run --solution` — and a ladder whose top rung was never sat would have no result at all.

**What it costs, precisely.** §3e predicted one mechanism per rung, so that a change in carry-over
could be attributed to isolation and a change in the gate's rejection rate to the gate. With rung 2
missing, **rung 3 switches on context isolation and the gate together**, on top of the three
corrections in §3f. Any difference between rung 1 and rung 3 is the sum of all of them, and this
project cannot say which one produced it.

**What survives, and it is the claim under test.** The primary comparison is baseline against
solution — coverage and allocation, whether the job decides what gets asked or the candidate's
opening sentence does. That comparison needs rungs 0 and 3, and both exist. What is lost is the
attribution *between* rungs, which was always the secondary question.

**One thing is still separately readable.** The gate logs every verdict, so its rejection rate and
fallback count come out of the rung 3 record on their own, without needing rung 2 to compare
against. §3e named a rejection rate of zero as the outcome most worth reporting; that reading is
unaffected.

Rung 2 stays in the ladder table as **not run**. It is a gap in the evidence, and reporting it as
one is the only honest option — `PREREGISTRATION.md` §4 lists selective reporting as invalidating,
and quietly renumbering rung 3 as rung 2 would be exactly that.

## The ladder

Three rungs above the baseline (`PREREGISTRATION.md` §3e). **Rung 2 was not run** — see the entry
directly above. Each row is appended at the moment
of its experiment, with its evidence column pointing at a `.metrics.json` under
`evals/results/` — never reconstructed afterwards, and never written ahead of the run it
describes.

| Stage | What was tried and why | Evidence | Decision |
| --- | --- | --- | --- |
| **Baseline** — iteration 0 | The obvious way to build this: one prompt, the job description, the CV, the full transcript every turn, and the instruction to *dynamically adjust questions based on the candidate's responses*. | [`session-20260831-120601.metrics.json`](evals/results/iteration-00/session-20260831-120601.metrics.json) — coverage **4/6–5/6**, carry-over **18%**, grounding **9%**, longest chain **4**, 11 questions, 25.5 min, ended `time_exhausted`, labelled **100% judge**. Corrected instrument; the pre-correction figures are in [`.metrics.pre-fix.json`](evals/results/iteration-00/session-20260831-120601.metrics.pre-fix.json) | **The prediction failed.** See below. |
| **Iteration 1** — the scheduler decides the topic | `decide_next` chooses the competency from the plan and the clock; the model still sees the transcript and still writes the wording. One mechanism changed against the baseline. | Run recorded 2026-08-31: [`session-20260831-153049.jsonl`](evals/results/iteration-01/session-20260831-153049.jsonl) — 8 questions, all 6 competencies, ended `time_exhausted` at 24.8 min. **Not yet measured**: `interview measure` has not been run on it. | pending measurement |
| **Iteration 2** — context isolation | Built and never run. See the entry below: the sittings ran out before the deadline did. | none | **not run — reported as a gap, not as a result** |
| **Final** — iteration 3, the gate | Isolation *and* the gate, switched on together, because rung 2 was not sat. | | |

### 2026-08-31 — FAILED PREDICTION, recorded as §3 requires

`PREREGISTRATION.md` §3 predicted, before any run: **coverage ≤ 2/6 (33%)** and **carry-over ≥ 50%**,
and named the falsification condition: *"If iteration 0 reaches coverage ≥ 3/6, this prediction has
failed."*

| | Predicted | Measured, corrected instrument | Measured, as first reported | |
| --- | --- | --- | --- | --- |
| Coverage | ≤ 2/6 (33%) | **4/6–5/6** | 5/6 (83%) | **failed** either way |
| Carry-over | ≥ 50% | **18%** | 100% | **failed** on the corrected instrument |

**Both columns are shown because the second one is wrong and was published first.** The
instrument was audited after this run and two defects were corrected — see the entry above and
`PREREGISTRATION.md` §2b. The carry-over figure moves the prediction from *half right* to *wrong
on both clauses*: the 100% was structural vocabulary, not drift.

Coverage is a range rather than a point because three measurements of the same record disagreed —
the judge is stochastic and moved two labels. §3's threshold is cleared at either end, so the
falsification fires regardless.

§3 forbids reframing this as a weaker claim and forbids re-running with a different opening answer
until it tunnels. Neither has been done. The run stands as the baseline.

**What the transcript shows, and why it is not what coverage says.** Eleven questions were asked
about **three** things: an idempotency implementation (5 consecutive questions), React Query retry
configuration (4 consecutive), and cross-boundary debugging (2, the last of which ran out of time
and got an empty answer). Questions 4 and 5 of the idempotency block are the same question
re-asked with more detail — *"where does the idempotency key actually come from"* — which is, almost
verbatim, what candidates describe in `research/evidence/candidate-reports.md`.

Coverage reports 5/6 anyway, and the per-question labels show exactly how:

| The idempotency conversation | Competency the judge assigned |
| --- | --- |
| walk me through a challenge spanning frontend and backend | `cross_boundary_debugging` |
| where did you generate the idempotency key | `api_contract` |
| how did you check for duplicates | `backend` |
| where does the key actually come from | `api_contract` |
| what database, what conditional write | `data_layer` |

**One continuous drill about one implementation detail produced four "covered" competencies.** No
individual label is obviously wrong — asking where a key is generated *is* a question about the
boundary. The defect is in the aggregate: coverage counts competencies-as-labelled, not
competencies-as-evidenced, and a sufficiently detailed conversation about a single topic will walk
through several labels without ever leaving the topic.

**What the guardrails say, after correction.** Carry-over is **18%** and grounding **9%** — one
question in 11 reached into the CV for something the candidate had not already said. The
carry-over that survives is `microservices` and `rest`, two technologies the candidate did raise
and the interviewer did chase.

The pre-correction figure was 100%, and it was wrong: it counted `backend`, `api`, `ui` and
`request` while missing the five consecutive questions about one idempotency key entirely, because
`idempotency` is lowercase and in no curated list. **The corrected 18% is a lower bound for the
same reason** — the conceptual drill that dominates this transcript is still uncounted. The number
that does see it is `longest_chain`, which was 4 in all three measurements.

**What is not known, stated so it is not glossed over:**

- **The rule layer resolved 0%.** Every question escalated to the judge, so the entire coverage
  figure rests on a model's classification. §2 requires that share to be reported; it has never
  been worse. The cause is structural: `label_by_rule` returns nothing when a question matches more
  than one slot, and in a fullstack role every real question mentions a frontend, an API and a
  backend. The hand-labelled agreement sample (§3d, load-bearing since the judge shares the
  interviewer's model) has still not been produced, and at 0% rule coverage it is now the only
  external check on the primary metric.
- **`longest_chain` reports 4, and the real concentration was 5.** The frontend block was caught;
  the idempotency block was not, because the *label* changed four times while the *topic* never
  did. The metric measures consecutive questions on one competency, and the failure is consecutive
  questions on one situation. It undercounts, and it undercounts in the direction that flatters the
  interviewer.
- **n = 1.** One respondent, one run, one model, one role. No variance measurement yet; `interview
  branch` (§2a) has not been run.

`PREREGISTRATION.md` §3 requires the premise to be re-examined before any further rung is built.
That has not been done and no rung 1 exists.

## Main failure mode and hot take

*Written once the ladder has run. It belongs to the evidence, not to the plan.*
