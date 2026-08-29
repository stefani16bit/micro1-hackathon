# Pre-registration

**Written 2026-08-29, before iteration 0 was run.** The git history is the evidence: the frozen
slot plan lands in `c8fc64e`, this document lands immediately after, and the first interview
result lands after that. Nothing below was written with a result in hand.

CLAUDE.md §6 requires defining what a good result looks like *before* running the evaluation. This
document does that, and adds the part that costs something: a statement of what would prove the
premise of this project wrong.

---

## 1. What is fixed before any run

| | |
|---|---|
| Role | `roles/fullstack/role.txt` — a real micro1 Full Stack Developer posting, retrieved 2026-08-29 |
| Slot plan | `roles/fullstack/slots.yaml`, **6 slots**, frozen in commit `c8fc64e`, read-only thereafter |
| Respondent | One human (the author), same profile in every run |
| Answer corpus | `evals/cases/case-01/response-brief.md`, frozen before iteration 0 |
| Opening answer | `evals/cases/case-01/opening-answer.md`, pasted **verbatim and identical** into all 11 runs |
| Time budget | 25 minutes total, 120 s per answer, constant |
| Metrics | Defined in §2 below and not redefined afterwards |

The opening answer is the controlled stimulus. It is the answer that names a technology early, and
holding it identical across all 11 runs is what makes the interviewer's behaviour the only moving
variable.

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
transcripts shuffled, temperature 0, running on a **different provider** than the interviewer. The
share resolved by each layer is reported with every result.

**Carry-over rate (guardrail).** Fully deterministic, no model involved:

```
carry_over(question) = ( terms(question) ∩ terms(previous candidate answers) ) − keywords(targeted slot) ≠ ∅
carry_over_rate      = |{ questions where that holds }| / |questions|
```

This is the tunneling measurement. A question that reaches for a technology the candidate raised,
and that does not belong to the slot being asked about, is drift — regardless of how good a
question it is.

**Grounding rate (guardrail).** The share of questions anchored in the frozen résumé evidence for
the slot being asked about. Grounding and carry-over separate *personalised* from *tunneled*: a
good interview scores high on the first and near zero on the second.

**Secondary.** Question variety across runs for the same slot (leak resistance), ratable-slot yield,
leak rate on clarification replies.

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

## 3b. Amendment, 2026-08-29 — which model runs the ladder

Added before any measured run, and for a specific reason: choosing the provider *after* seeing
which one tunnels more would be the same offence as re-running until the prediction confirms. So
the choice is made here, in advance, on stated grounds.

- **The ladder runs on `ollama/gemma4:12b`**, all eleven iterations. It is the default in
  `config.yaml`, it is free, and a reviewer reproduces the main result with `ollama pull
  gemma4:12b` and nothing else — no subscription, no API key. It is also the honest deployment for
  a system running ~1,600 interviews a day.
- **Iterations 0 and 10 are additionally run on `claude_cli`**, declared now, as a cross-model
  check. If the effect holds on both a 12B local model and a frontier model, the claim that this
  result is about architecture rather than about one model is measured rather than asserted.

Whatever these runs show is reported, including the case where the strong model does not tunnel and
the weak one does — that would itself be the finding, and a more interesting one than the
prediction.

**Context for this amendment.** Two pipeline smoke runs were executed before it (recorded under
`evals/results/smoke/`, on both providers). They are **not measurements**: the canned candidate
returns the same generic sentence to every question, so both models re-asked rather than moving on —
persistence against a non-answer, not topic selection. They are noted here only because both
providers spent their second turn on the candidate's *gap* rather than on the material the opening
answer offered, which runs against the prediction in §3. That is weak, confounded evidence and it
changes nothing about the prediction, which stands as written.

---

## 4. What would invalidate the result

Stated now so it cannot be negotiated later:

- The slot plan changing after this commit.
- The opening answer differing between runs.
- Any metric being redefined after seeing a result.
- Iterations being reported selectively. Every run goes into `evals/results/`, including the ones
  that made things worse.
- The measurement cascade's blind judge sharing a provider with the interviewer being measured.

---

## 5. Known limitations, acknowledged in advance

- **One case, not ten.** CLAUDE.md §6 asks for 10 or more evaluation cases; this design has one
  respondent across 11 runs. The trade is deliberate — it makes the interviewer's questions the
  only moving variable — but the result is a within-subject trajectory, not a population estimate,
  and it is reported as such.
- **The respondent knows the system.** Mitigated by the frozen response brief and the verbatim
  opening answer, not eliminated.
- **No claim is made about Zara's implementation.** micro1 has not published its interview-conduct
  policy (paper §3.1). Iteration 0 is the obvious way to build this, not a reconstruction of theirs.
