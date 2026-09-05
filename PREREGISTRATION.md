# Pre-registration

**Written 2026-08-29, before iteration 0 was run.** The git history is the evidence: the frozen
slot plan lands in `c8fc64e`, this document lands immediately after, and the first interview
result lands after that. Nothing below was written with a result in hand.

agentic-workflows.md §6 requires defining what a good result looks like _before_ running the evaluation. This
document does that, and adds the part that costs something: a statement of what would prove the
premise of this project wrong.

---

## 1. What is fixed before any run

|                |                                                                                               |
| -------------- | --------------------------------------------------------------------------------------------- |
| Role           | `roles/fullstack/role.txt` — a real micro1 Full Stack Developer posting, retrieved 2026-08-29 |
| Slot plan      | `roles/fullstack/slots.yaml`, **6 slots**, frozen in commit `c8fc64e`, read-only thereafter   |
| Respondent     | One human (the author), same profile in every run                                             |
| Answer corpus  | `evals/cases/case-01/response-brief.md` — built from the transcripts; see §1a and §1c     |
| Opening answer | `evals/cases/case-01/opening-answer.md`, captured in iteration 0, replayed **verbatim** at every rung |
| Time budget    | 25 minutes total; answers are not timed — see §1b                                            |
| Metrics        | Defined in §2 below and not redefined afterwards                                              |

The opening answer is the controlled stimulus. It is the answer that names a technology early, and
holding it identical across every run is what makes the interviewer's behaviour the only moving
variable.

---

### 1b. Amendment, 2026-08-31 — the per-answer clock is removed

Recorded rather than quietly applied, because §1 fixed a time budget of *"25 minutes total, 120 s
per answer, constant"* and the second half of that is no longer true.

**What changes.** There is no limit on an answer. The interview advances when the candidate submits,
and only the 25-minute total is enforced — checked at the turn boundary, so an answer already under
way may run past the mark and the interview ends after it rather than truncating it.

**Why.** The interview this project models is **spoken**: a real candidate talks for as long as the
answer takes, and the system moves on when they stop. Ours is typed, and translating "spoken turn"
into "120-second window that closes and keeps your draft" added a pressure the original does not
have — and a deadline shows up in exactly one place, in answers written against the clock rather
than to the question.

**What it costs, and it is the reason the deadline existed.** Answers can now lengthen from one
iteration to the next, which shortens the interviews and would depress coverage for a reason that is
not the interviewer. That confound is no longer *prevented*; it is **measured**. Every run reports
the count, mean, median, range and total of its answer durations, and `interview report` places mean
answer time and total answering time beside coverage in the per-rung table — so a reader comparing
two rungs can tell "the interviewer got worse" from "the respondent talked longer" instead of having
to assume.

Rule 3 of the response brief carries the other half: answer naturally, neither padding nor
compressing. That is a promise rather than a mechanism, and it is disclosed as one.

**Two consequential details.** The forecast the scheduler uses to plan how many turns fit is now
named `expected_answer_seconds`, because the old name (`answer_deadline_seconds`) is how a planning
figure quietly becomes a limit. And the replayed opening answer is charged **the duration it
actually took when it was given**, recorded in `evals/experiment-lock.yaml` — a configured constant
would make the stimulus cost one thing in the run that captured it and another in the ten that
replay it.

**On timing.** Like every other amendment in this document, this one was made **before any measured
run**.

---

### 1c. Amendment, 2026-08-31 — the brief arrived a rung late, and rung 1 was unbriefed

**Made after rung 1 was run, and it is a disclosure rather than a design change.** §1a stated that
iteration 0 would be answered from memory and the rungs after it from a brief built out of its
transcript. The brief was never produced, so **rung 1 was also answered from memory**. It exists
now, transcribed from the iteration 0 and iteration 1 transcripts, and rungs 2 and 3 will use it.

**What this changes about the comparison.** The asymmetry §1a disclosed still exists, one rung later
than described: rungs 0–1 unbriefed, rungs 2–3 briefed. Two things bound it, both unchanged from
§1a's reasoning. Every fact in the brief was already given *without* it, so the brief cannot add
substance to a later answer — at most it makes one easier to recall. And the metrics are computed
over the interviewer's **questions**, never over answer quality (§2), so the effect can only reach a
number by changing what gets asked next.

**One thing the brief deliberately does not do.** Iteration 0 asked twice for a specific
cross-boundary debugging incident and received none. The brief records that as a gap and instructs
the respondent not to invent one. Supplying the missing story would have manufactured evidence for
the only competency the CV marks unevidenced, which is the competency the posting's Scope of Work
names outright.

**Why it is disclosed rather than repaired.** Repairing it means re-running rung 1 briefed: another
25-minute sitting, and one whose result could not be compared with rung 0 anyway, since rung 0 stays
unbriefed either way. The asymmetry is real, bounded and stated; the alternative is a cost without a
matching gain.

---

### 1a. Amendment, 2026-08-30 — the opening answer and the brief now come from iteration 0

Made **before any measured run**, and recorded here rather than quietly applied, because it changes
the ordering §1 fixed.

**What changes.** §1 listed the opening answer and the response brief as frozen *before* iteration 0,
produced by a separate pilot run. They are not. The baseline run captures the opening answer live —
the candidate answers the first question as they would answer any other, and it is frozen in code at
the moment it is given — and the response brief is transcribed afterwards from that same transcript.

**Why.** The pilot flow was: run a pilot, interrupt it, copy the printed answer, paste it into a
file, then run the real interview. Four steps to produce one answer, three of them clerical, and the
copy-paste step put a gap between what was said under a 120-second clock and what ended up frozen.
That gap is where an answer gets improved without anyone deciding to improve it. Capturing in code
removes it: the frozen stimulus is character-for-character what was typed during the interview.

**What it costs, and this is a real cost.** Iteration 0 is now answered **from memory**, and the
rungs after it from the brief built out of it — see §1c, which records that rung 1 was unbriefed
too. The runs are therefore not identical in one respect the earlier design did hold constant:
respondent preparation.

The direction of the bias is the uncomfortable part and it is stated rather than buried. A less
rehearsed answer is likelier to be vague, and a vague answer is likelier to draw a follow-up than to
be moved on from — which would *depress iteration 0's coverage*, in the same direction as the
prediction in §3. **The prediction is therefore easier to confirm than it was**, and the falsification
clause is unchanged: if iteration 0 reaches coverage ≥ 3/6 it has failed, and that gets recorded.

Two things bound it. The metrics are computed over the interviewer's **questions**, never over answer
quality (§2), so the effect can only reach the numbers by changing what gets asked next. And the
opening answer — the one turn that decides which topic is on offer first — is byte-identical across
every run either way, because iteration 0 is where it is captured.

**What would have been the alternative.** Keeping the pilot: one extra 25-minute sitting, every
runs on equal footing. It was rejected on the author's judgement that four clerical steps around a
25-minute sitting is a worse failure risk than a bounded, disclosed asymmetry. A reader who disagrees
has everything needed to say so — this paragraph, and iteration 0's transcript.

---

## 2. Metric definitions, fixed now

Computed over the interviewer's **questions**, never over the quality of the candidate's answers.
The opening turn is excluded from all rates, since it is identical by construction.

**Coverage (primary).**

```
coverage = |{ slots targeted by at least one substantive question }| / 6
```

A question "targets" a slot when the measurement cascade says so: a literal keyword match against
`slots.yaml` first, and for questions no rule resolves, a blind LLM judge — iteration id stripped,
transcripts shuffled, temperature 0. The share resolved by each layer is reported with every
result. (The judge shares the interviewer's model — see §3d for why that is acceptable for a blind
classification task, and what it costs.)

> **The keyword layer described above no longer exists — see §2b.** It resolved 0 of 11 questions
> on iteration 0 and was removed. Every question is labelled by the judge, and §2b also records
> that coverage is not stable under re-measurement: the same record scored 4/6 once and 5/6 twice.

**Carry-over rate (guardrail).** Fully deterministic, no model involved. `terms()` counts
technologies, not layers — **see §2b**, which corrects an implementation that counted `backend`
and `api` and reported 100%:

```
carry_over(question) = ( terms(question) ∩ terms(previous candidate answers) ) − keywords(targeted slot) ≠ ∅
carry_over_rate      = |{ questions where that holds }| / |questions|
```

This is the tunneling measurement. A question that reaches for a technology the candidate raised,
and that does not belong to the slot being asked about, is drift — regardless of how good a
question it is.

**Grounding rate (guardrail).** The share of questions anchored in the frozen résumé evidence for
the slot being asked about. Grounding and carry-over separate _personalised_ from _tunneled_: a
good interview scores high on the first and near zero on the second.

**Secondary.** Question variety across runs for the same slot (leak resistance), ratable-slot yield,
leak rate on clarification replies.

---

### 2a. Amendment, 2026-08-31 — what coverage cannot see

**Declared before any measured run.** `evals/results/` is empty and no interview has been
recorded. It is also declared with knowledge gained from exploratory runs that were not retained
as results — piloting, not measurement, and disclosed here rather than left for a reader to
wonder about. Nothing below redefines an existing metric.

**Coverage stays primary and its definition in §2 is unchanged.** What changes is that it is
reported as a *distribution* rather than a point, and that two things it cannot see are measured
beside it.

**Why.** Coverage is a set: a competency counts as covered when one substantive question touches
it. A set is blind, by construction, to how the 25 minutes were divided. An interviewer can reach
all six competencies and still spend four of ten questions drilling one situation the candidate
raised first, leaving the other five a question each — and the candidate is then judged on five
drive-by answers and one deep one. That is a different interview from an evenly allocated one,
and §2 as written scores them identically.

**1. Allocation (new).** Computed from the same per-question labels the cascade already produces.
No model involved beyond the labelling that coverage already uses.

```
longest_chain      = the longest run of consecutive questions on one competency
max_slot_share     = questions on the most-asked competency / questions asked
normalised_entropy = H(question counts per competency) / log(6)
```

`longest_chain` is the operative one. It has a ceiling that is a property of the code rather than
of the run: a scheduled interviewer asks one primary question per slot plus at most
`max_followups_per_slot` follow-ups, so it cannot exceed that sum. A single prompt has no
ceiling, because nothing in it counts what it has asked.

**2. Coverage as a distribution (reporting change).** Where a rung has been run more than once,
its reported coverage is the **worst** run, with the mean and the spread beside it. A screen
returning full evidence four times in five still returns partial evidence about one candidate in
five, and it is that candidate who is rejected on it. Reporting the mean describes a candidate
nobody interviewed.

**3. Branching (new).** `Interviewer.next_utterance` is a pure function of the transcript, so a
recorded interview can be rewound to each turn boundary and the interviewer asked, k times, what
it would say next. Reported as the mean number of *distinct* competencies it reaches for per
decision point. One means topic selection is determined; above one means it is a draw.

This uses one human sitting, not k: the answers are a real respondent's, given once and replayed.
Nothing simulates a candidate, so the constraint in §5 stands.

**A validity condition, stated because it is easy to get wrong.** Sampling a provider pinned to
`temperature: 0` or a fixed seed returns k copies and would report a perfectly consistent
interviewer when it had measured the seed. The command refuses that configuration rather than
producing the number. Any run that clears the seed to enable sampling is recorded in
`CHANGELOG.md`, because it changes what every other run of that provider means.

**What this does not do.** It does not rescue the §3 prediction. If iteration 0 covers ≥ 3/6 the
prediction has failed and §3's clause applies as written — recorded as a failed prediction, and
the premise re-examined. These measurements say what *else* is true of that run; they are not a
second chance at the first claim, and none of them is promoted to primary.

---

### 2b. Amendment, 2026-08-31 — the instrument was wrong, and how wrong

**Made after seeing iteration 0's result, which is exactly the timing §4 warns about.** It is
recorded here in full, with the before and after of every number it moved, because the alternative
is a comparison built on an instrument that was measuring something other than what §2 defines.
All three measurements of the run are committed under `evals/results/iteration-00/`, including the
one that gave the worst number.

**1. The keyword layer is removed.** §2 described a cascade: *"a literal keyword match against
slots.yaml first, and for questions no rule resolves, a blind LLM judge"*. Over iteration 0 the
rule layer resolved **0 of 11** questions and mislabelled two — `React Query` decomposes into
`react` + `query`, and `query` belongs to the data layer, so two purely frontend questions
registered as reaching into it.

The cause is structural, not a keyword needing a tweak: `api_contract` and
`cross_boundary_debugging` are **relational** competencies, defined in terms of the other slots'
vocabulary. No word-matcher separates *a question about the boundary* from *a question that names
both sides of it*.

**Removing it changes no number, and that was verified rather than assumed.** `label_by_rule`
returned `None` on all 11 questions, so the old path (`None` → judge) and the new path
(→ judge) are the same code. Re-measuring reproduced the pre-removal labels exactly.

**What it costs, plainly:** coverage is now 100% a model's classification, with no deterministic
layer beneath it. `interview measure --no-judge` is no longer a reproduction path — though it
already returned 0/6 before this, so the claim in `REPRODUCTION-GUIDE.md` was already false and
now says so. The hand-labelled agreement sample (§3d) is the only external check that remains.

**2. Structural vocabulary no longer counts as drift.** §2 defines carry-over as a question
reaching for *"a technology the candidate raised"*. The implementation counted every term the
lexicon recognised, and the lexicon contains the slot keywords — so `backend`, `api`, `ui`,
`request` and `query` all counted. Over iteration 0 that produced a carry-over rate of **100%**
while the five consecutive questions about one idempotency key went **uncounted**, because
`idempotency` is lowercase and in no curated list. The rate was measuring the domain.

`solution/domain/data/structural_terms.txt` is subtracted by `is_carry_over` and `is_grounded`
and by nothing else. Its header carries the membership test, and a test asserts no named
technology is on it.

**This is a correction, not a redefinition.** The sentence in §2 is unchanged; the implementation
now matches it. A layer is not a technology.

**What it moved, both numbers reported as §4 requires:**

| | before | after |
| --- | ---: | ---: |
| carry-over | 100% | **18%** |
| grounding | 18% | **9%** |

The 18% that survives is `microservices` and `rest` — two technologies the candidate did raise
and the interviewer did chase. **It is a lower bound and must be reported as one:** `idempotency`,
`refetch`, `race condition` and `optimistic updates` are still invisible, being lowercase terms in
no curated list. Adding them now, having seen them in the transcript, is the post-hoc tuning §4
forbids, so they stay uncounted and stay disclosed.

**3. The finding that matters more than either fix: coverage is not stable.**

Three measurements of the *same record* were run. Two returned **5/6** with identical labels; one
returned **4/6**, because the judge moved two questions from `api_contract` to `backend`. Both
questions are from the idempotency block, where — as the failed-prediction entry in `CHANGELOG.md`
records — one continuous conversation is being assigned to whichever competency the judge picks
that time.

**Coverage for iteration 0 is therefore 4/6–5/6, not a point.** The primary metric carries a
measurement error of at least ±1/6 from the judge alone, on identical input. Any baseline-versus-
solution difference smaller than that is noise, and §3's iteration-10 target of 6/6 has to clear
it rather than land inside it. This was not known when §2 was written and it is not fixed here;
it is measured, disclosed, and left for the agreement sample to characterise further.

---

## 3. The prediction

### Iteration 0 — the single-prompt interviewer

> **coverage ≤ 2/6 (33%)** and **carry-over rate ≥ 50%**

In plain terms: a well-written prompt with the job description and the CV in front of it will spend
the interview on one or two topics, driven by what the candidate says first, and will leave most of
what the role requires unasked.

**Falsification.** If iteration 0 reaches **coverage ≥ 3/6**, this prediction has failed. In that
case the result is recorded in `CHANGELOG.md` as a failed prediction, and the premise is
re-examined before any further iteration is built — not quietly reframed as a weaker claim, and not
re-run with a different opening answer until it tunnels. A problem that does not reproduce under
the conditions we specified is a finding, and it is a more useful one than a confirmation.

### Iteration 10 — the finished system

> **coverage ≥ 6/6 (100%)** and **carry-over rate ≤ 10%**, with grounding rate materially above
> iteration 0's

Coverage of 6/6 is achievable by construction once the scheduler exists, so on its own it is a weak
claim. The claim that carries weight is the pair: full coverage **while** questions stay grounded in
the candidate's own background. A fixed questionnaire would reach 6/6 and score near zero on
grounding, and that is the failure mode the guardrail exists to catch.

---

## 3f. Amendment, 2026-08-31 — three corrections to the interviewer, before rung 2

**Made after rung 1 was run and before rung 2**, from the respondent's account of sitting it. It
changes no metric and no prediction. It changes what the interviewer *is*, which is why it is
recorded here rather than applied quietly, and `CHANGELOG.md` carries the same three with their
evidence.

**1. From rung 2, the interviewer composes its question while the candidate answers.** Rung 1 spent
409 of 1491 seconds — 27% of the interview — generating questions with nothing on the candidate's
screen. Withholding the transcript is what makes the fix sound: the next question does not depend on
the answer being given, so it can be composed in parallel. Speculative and validated — the schedule
is consulted again once the answer's real duration is known, and a question it no longer wants is
discarded and regenerated live.

> **The consequence for the comparison, stated before the run.** With the wait off the clock, more
> questions fit in 25 minutes. **Question counts are not comparable between rungs 0–1 and rungs
> 2–3.** Coverage, `longest_chain`, carry-over and grounding remain comparable: the first two are
> defined over competencies and the last two are per-question rates. The baseline cannot compose
> ahead — it is handed the transcript and asked to react to it — and per §4 of the hackathon brief
> that difference in what each end of the ladder can do is stated rather than left implicit.

**2. A follow-up is given the answer it is following up on, and nothing else.** It was previously
generated from the same prompt as a primary question, so the model was never told it was deepening.
A bounded exception to the isolation: the schedule has already chosen the slot and a follow-up
cannot leave it, so nothing read here can move the interview. The gate's carry-over allowance is
widened by exactly the terms in that one answer.

**3. The interviewer may open with one short, neutral acknowledgment.** It may not name anything the
candidate said. An isolated interviewer never read the answer, so it can only acknowledge, never
summarise.

**What this costs the ladder, and it is the real cost.** Rungs 2 and 3 run with these three; rung 1's
record does not have them. **The difference between rung 1 and rung 2 is therefore isolation plus
three corrections, not isolation alone**, and no reader should attribute a rung-2 change in
grounding or carry-over to the isolation by itself. The alternative was re-running rung 1 — another
25-minute sitting, for an ablation that is not the claim under test. The claim under test is who
decides the allocation, and §3e's per-rung predictions are unchanged.

## 3e. Amendment, 2026-08-31 — the ladder is three rungs, and what each is predicted to do

**Written before any of the three was run**, and before the sittings that produce them. The
baseline they are measured against is the run already recorded: coverage **4/6–5/6**, carry-over
**18%**, grounding **9%**, `longest_chain` **4**.

The ladder shrinks from eleven rungs to three, and §3's "Iteration 10" above should be read as
"the finished system", which is now rung 3. Nothing in the hackathon brief asked for eleven — its
own changelog template stops at *Iteration 2* — and §3 of the brief penalises stacking components
that are not each traceable to a failure they fix. Three rungs, one mechanism each:

| Rung | Switches on | Prediction |
| --- | --- | --- |
| **1** | `decide_next` chooses the slot; the model still sees the transcript | `longest_chain` **≤ 2**, coverage **6/6**; carry-over and grounding roughly unchanged |
| **2** | context isolation — the transcript is withheld, the CV line supplied | carry-over **< 10%**, grounding **materially above 9%** |
| **3** = solution | the gate verifies every question before the candidate sees it | carry-over **0**, and a non-zero gate rejection rate in the session record |

**What would falsify each.** Rung 1 failing to reach 6/6, or `longest_chain` exceeding 2 — the
latter would be a bug rather than a finding, since the ceiling is `1 + max_followups_per_slot` in
code. Rung 2 failing to raise grounding would mean the CV line is not what makes a question
specific, and the isolation buys nothing. **Rung 3 recording a rejection rate of zero would mean
the gate is decoration** — every question already clean — and that is the outcome most worth
reporting, because it would say the two rungs before it had done the work.

**Coverage cannot separate these rungs and is not expected to.** Any scheduled rung reaches 6/6 by
construction, and the baseline already reached 4/6–5/6. The rungs are told apart by
`longest_chain`, carry-over, grounding and ratable-slot yield. That is a weakness of the primary
metric, recorded in §2a and §2b, not a result.

**A cost accepted knowingly.** One primary per competency plus at most one follow-up means every
competency gets shallow treatment. The respondent's verdict on the baseline was that it never let
them show breadth — asking about backend without reaching architecture, concurrency, messaging,
security or testing. **The solution does not fix that and cannot:** six competencies in 25 minutes
is one or two questions each, whoever schedules them. The claim under test is about *who decides
the allocation*, not about depth, and the README says so where a reader will see it.

## 3d. Amendment, 2026-08-30 — one model everywhere, for now

Supersedes the provider split in §3c. Made **before any measured run**.

**Everything runs on `claude-sonnet-4-5-20250929`**: the interviewer across all
iterations, and the measurement judge. There is no second model anywhere in the pipeline.

**On the judge sharing the interviewer's model.** The earlier rule — that the judge must run
elsewhere — was a reasonable default applied without examining whether it earned its cost here. It
does not, for three reasons:

1. The judge performs **classification**, not quality evaluation. It answers _which competency is
   this question about_, never _is this question good_. Self-preference bias is a phenomenon of
   preference and quality judgement; a blind classification task gives it almost nowhere to act.
2. The judge is **blind by construction**: one question plus the competency list, with no
   transcript, no iteration number, and nothing identifying the system. It cannot know whether it
   is labelling its own output.
3. The **same judge labels both ends of the ladder**. To distort the comparison the bias would have
   to act differently at the baseline than at the final rung, and blindness leaves no mechanism for
   that.

Against that, the gain is concrete: a stronger judge resolves the hard cases better, and the hard
cases are precisely what reaches it — questions spanning three or four slots that the rule layer
escalates rather than guesses at.

**What this does cost, and it is not the bias:**

- **The cross-model check is gone**, so **D11 — that the result is about the architecture rather
  than about one model — is deferred, not demonstrated.** Until a second model is run, no claim of
  model independence appears in the README or anywhere else. The provider abstraction remains in
  the code and the check can be added later; it has simply not been measured.
- **The hand-labelled agreement sample is now the judge's only external check.** It was a
  confirmation before; it is load-bearing now. It is not optional, and the agreement rate is
  reported with the results whatever it turns out to be.

---

## 3c. Amendment, 2026-08-30 — the ladder moves to Claude Sonnet 4.5 _(provider split superseded by §3d)_

Supersedes §3b below. Made **before any measured run**, and recorded rather than quietly applied.

- **The ladder runs on `claude-sonnet-4-5-20250929`** (Claude Code CLI), every iteration.
- **Iterations 0 and 10 additionally run on `ollama/gemma4:12b`** as the cross-model check —
  the same design as §3b, with the two sides swapped.
- **The judge runs on `ollama/gemma4:12b`**, because it must not share a model with the system it
  measures.

**Why.** The project author's judgement: a baseline running on a model strong enough not to tunnel
would measure model capability rather than architecture, and the interviewer should sit in a
capability tier where the failure can plausibly occur.

**What this is not.** It is **not** an attempt to match the model Zara runs. Claude Sonnet 3.5 —
the contemporary of the GPT-4o the paper names — was retired on 2025-10-28, and nothing currently
served is a proxy for GPT-4o. No claim of resemblance is made anywhere in this project, and the
statement in §5 that nothing is claimed about Zara's implementation stands unchanged.

**What it costs, stated plainly:**

- **Reproducibility.** Reproducing the headline result now requires a Claude Code subscription.
  The free path — `ollama pull gemma4:12b` and nothing else — reproduces the cross-check at
  iterations 0 and 10, not the full ladder. This is a real regression against agentic-workflows.md's
  requirement that a reviewer reach the main result from a clean environment, and it is disclosed
  in the README rather than hidden.
- **A higher chance the prediction fails.** Sonnet 4.5 is considerably stronger than a 12B local
  model, so iteration 0 covering ≥ 3/6 is now materially more likely. The falsification clause in
  §3 is unchanged and will be applied as written: if it fires, it gets recorded and the premise is
  re-examined, not reframed.
- **A weaker judge.** Moving the judge to a 12B model lowers the quality of the labelling it
  resolves. Every result reports the share resolved by rule versus by judge, so a reader can see
  exactly how much of a number rests on it.

Model ids are pinned to dated snapshots throughout. An alias resolves to whatever is current, which
would silently change the experiment for anyone running it later.

---

## 3b. Amendment, 2026-08-29 — which model runs the ladder _(superseded by §3c)_

Added before any measured run, and for a specific reason: choosing the provider _after_ seeing
which one tunnels more would be the same offence as re-running until the prediction confirms. So
the choice is made here, in advance, on stated grounds.

- **The ladder runs on `ollama/gemma4:12b`**, every iteration. It is the default in
  `config.yaml`, it is free, and a reviewer reproduces the main result with `ollama pull
gemma4:12b` and nothing else — no subscription, no API key. It is also the honest deployment for
  a system running ~1,600 interviews a day.
- **Iterations 0 and 10 are additionally run on `claude_cli`**, declared now, as a cross-model
  check. If the effect holds on both a 12B local model and a frontier model, the claim that this
  result is about architecture rather than about one model is measured rather than asserted.

Whatever these runs show is reported, including the case where the strong model does not tunnel and
the weak one does — that would itself be the finding, and a more interesting one than the
prediction.

---

## 4. What would invalidate the result

Stated now so it cannot be negotiated later:

- The slot plan changing after this commit.
- The opening answer differing between runs.
- Any metric being redefined after seeing a result.
- Iterations being reported selectively. Every run goes into `evals/results/`, including the ones
  that made things worse.
- The judge ceasing to be blind — being shown the transcript, the iteration number, or anything
  else identifying which system produced a question. Sharing the interviewer's model is allowed
  (§3d); seeing whose output it is labelling is not.
- The hand-labelled agreement sample not being produced, or being reported selectively. It is the
  judge's only external check.

---

### 4a. Addendum, 2026-08-30 — the list above is now enforced, not remembered

Added **before any measured run**. It changes no prediction and no metric; it makes the section
above mechanical.

The first measured run — the baseline — hashes everything §1 fixes into
`evals/experiment-lock.yaml`. Every run after it compares the inputs on disk against that file
before the first question is asked. A run whose role, slot plan, CV, résumé evidence, opening
answer or time budget has moved does not start: it prints which input moved, what it was, what it
is now, and which iterations already depend on the old value.

Recording is not a separate step, deliberately. There is no case in which one would want to
measure without recording what was measured against, so a `freeze` command could only ever have
produced a step to forget. The decision it would have asked for is already made when the opening
answer is pasted into its file.

**A changed input restarts the ladder rather than continuing it.** Iteration 0 measured against
one CV and iteration 5 against another do not form a comparison, so the only way forward is
`interview run --baseline --restart`, which begins again at the first rung under a new lock id.
There is no way to carry on from the middle, and that is the intended shape of the constraint.

Each run also stamps the lock it ran under into its own session record, so a result is attributable
to an experiment even if the file is moved, and `interview report` refuses to build a comparison
table spanning two of them.

**One input is tracked rather than locked.** `response-brief.md` records its digest with every run
but never blocks one, because its own rule 1 allows it to grow when a question reaches a fact it
does not hold, provided the growth is recorded in `CHANGELOG.md`. Locking it would forbid a
legitimate documented action; recording it makes the session records and the changelog agree by
construction.

**What this does not do.** It cannot detect a respondent who answers differently, and it does not
stop anyone deleting the lock and starting over. It removes the *silent* version of the failure:
inputs that move without anyone noticing. The honest version — deciding the experiment has
restarted, running `interview run --baseline --restart`, and reporting both — stays available and stays
visible, which is the most a mechanism can do.

---

## 5. Known limitations, acknowledged in advance

- **One case, not ten.** agentic-workflows.md §6 asks for 10 or more evaluation cases; this design has one
  respondent across 11 runs. The trade is deliberate — it makes the interviewer's questions the
  only moving variable — but the result is a within-subject trajectory, not a population estimate,
  and it is reported as such.
- **The respondent knows the system.** Mitigated by the frozen response brief and the verbatim
  opening answer, not eliminated.
- **No claim is made about Zara's implementation.** micro1 has not published its interview-conduct
  policy (paper §3.1). Iteration 0 is the obvious way to build this, not a reconstruction of theirs.
