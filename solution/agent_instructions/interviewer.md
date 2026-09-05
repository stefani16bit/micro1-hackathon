# Agent instruction — the scheduled interviewer (iterations 1–3)

**Runs:** once per turn, for every rung above the baseline.
**Decides:** the wording of one question. **Does not decide:** which competency that question is
about. That is `solution/domain/scheduler.py`, and it never reads the candidate's answers.

## What this agent is not allowed to know

The list matters more than the prompt, because every item on it is a way the interview could be
steered by the conversation instead of by the job:

| Withheld | If it had it |
|---|---|
| the transcript *(iterations 2–3)* | it would follow what the candidate said — the failure being measured |
| the other five competencies | it could try to cover them itself, and coverage would stop being the scheduler's property |
| how much time is left | it could pace its own coverage, which is the thing under test |
| that it is being measured at all | an interviewer that knows is not the interviewer the experiment is about |

One answer is not withheld, and only on one turn: a follow-up sees the answer it is following up on.
The section below states the bound on that.

Iteration 1 **does** see the transcript: that rung isolates topic selection, so everything else is
held as it was in the baseline. Iteration 2 removes it, and the difference between the two rungs is
what that removal was worth.

## System prompt

```
You are a technical interviewer conducting one turn of a screening interview. You are
speaking with the candidate directly, in English.

You will be given ONE competency to ask about, and what the candidate's CV says about it.
Ask about that competency and nothing else.

HOW TO ASK
- Ask exactly one question. One question mark, no compound questions.
- If the candidate has done this work, ask them to describe a specific time they did it -
  the situation, what they personally did, and how it turned out.
- If the candidate has NOT done this work, ask a hypothetical instead: put them in a
  situation that requires the competency and ask how they would approach it. Never imply
  they should have experience they do not have.
- When the CV gives you a specific detail about this competency, anchor the question in
  it. A question that could be asked of any candidate wastes the turn.
- Do not name technologies the CV does not mention for this competency.
- Vary how you open. Do not begin every question the same way.

BEFORE THE QUESTION
You may open with at most one short, neutral acknowledgment - six words or so, of the
kind a person says while turning to the next topic. It must not name anything the
candidate said, must not summarise their answer, and must not judge it. If you have
nothing neutral to say, say nothing.

OUTPUT FORMAT
Reply with a JSON object and nothing else:
{"question": "<the question you ask the candidate>"}
```

## User prompt (per turn)

```
COMPETENCY
<<SLOT_NAME>>

THE CANDIDATE HAS DONE THIS WORK: <<HAS_EXPERIENCE>>

WHAT THEIR CV SAYS ABOUT IT
<<EVIDENCE>>

<<TRANSCRIPT_BLOCK>><<FOLLOWUP_BLOCK>>Ask your one question, as JSON.
```

`<<TRANSCRIPT_BLOCK>>` is empty from iteration 2 onwards. In iteration 1 it carries the transcript,
so that rung differs from the baseline in exactly one respect.

`<<FOLLOWUP_BLOCK>>` is empty on a primary question. On a follow-up it carries **the candidate's
answer to this competency's first question, and nothing else** — see below.

## What a follow-up is allowed to see

A follow-up used to be generated from exactly the same prompt as a primary question, which meant
the model never knew it was following anything up. It wrote a second standalone question about the
same competency, and the candidate heard *"Describe a time…"* twice in a row. That was the defect;
this is the fix.

A follow-up receives the candidate's answer to that competency's own first question. Not the
transcript, not the other answers — that one answer. It is a **bounded exception** to the isolation
rather than a hole in it, and the bound is what makes it safe: the schedule has already chosen the
slot, and a follow-up cannot leave it, so nothing the model reads here can move the interview
anywhere. The gate's carry-over rule is widened by exactly the same amount and no more — picking up
the candidate's own words is the entire point of a follow-up, and drift is what happens *across*
competencies.

**A follow-up is not triggered by a thin answer.** Nothing reads answer quality. The schedule grants
one only when the clock affords it after every remaining competency has been paid for
([`_affords_followup`](../domain/scheduler.py)), at most `max_followups_per_slot` per competency.

## Composing before the answer arrives

From iteration 2 the interviewer is handed the next competency without the transcript, so its next
question does not depend on what the candidate is currently saying — and it is composed while they
say it. In iteration 1 that measured 409 of 1491 seconds, 27% of the interview, spent watching a
terminal that showed nothing.

The composition is **speculative and validated**: the schedule is consulted again once the answer's
real duration is known, and a question composed for a competency the schedule no longer wants is
discarded and regenerated live. Only primaries are composed ahead; a follow-up needs the answer that
has not been given yet. `speculation_used`, `speculation_discarded` and `composed_ahead` land in the
session record, so the hit rate is a count.

The baseline cannot do this, and that is not an oversight: it is handed the transcript every turn
and asked to react to it, so its next question cannot exist before the answer does.
`Interviewer.may_compose_ahead` states the capability rather than leaving it implicit.

## Clarification prompt (third block)

Used when the candidate asks for the question again rather than answering it. It restates; it
never helps. [`gate.py`](../domain/gate.py)'s `check_clarification` rejects a reply that introduces
any technical term the original question did not already contain — because an interviewer that
explains the topic while asking about it has answered its own question, and the rating that follows
is of the interviewer.

```
The candidate has asked you to explain your question. Say the same question again in
plainer words.

RULES
- Introduce no new technical terms. Not one. If your question named a technology, you may
  name it again; you may not name anything else.
- Do not hint at what a good answer contains, do not give an example, do not narrow the
  question into something easier.
- Two sentences at most, and end with the question.

Reply with a JSON object and nothing else:
{"question": "<your restatement>"}
```

**One clarification per question.** If the candidate asks a second time, the interview moves on
rather than restating again — `solution/domain/clarification.py` says why: an interview that can be
held on one topic by repeating "what do you mean" has this project's own failure mode arriving from
the other side. The move-on turn opens with a line that says so without blaming the candidate, then
asks the next competency's question.

## What happens to what it produces

Nothing reaches the candidate unverified from iteration 3 onwards.
[`gate.py`](../domain/gate.py) rejects a question that reaches for a technology the candidate raised
outside this competency, that fails to name the competency at all, or whose phrasing is behavioural
when the CV says the candidate has not done the work. A rejected question is regenerated once; a
second rejection falls back to the template for the slot's kind, below. Every decision is written to
the session record, so the gate's rejection rate is a count rather than a claim.

## Fallback templates

From `research/interview-guidance.md` §2. Used when generation fails or the gate rejects twice —
which is what `SlotKind` exists for.

| Slot kind | Behavioural | Situational |
|---|---|---|
| `language_framework` | What is the most demanding thing you have built with {slot}, and what made it demanding? | Suppose you had to build a feature with {slot} on a system you do not know — how would you approach it? |
| `data_storage` | Tell me about a time {slot} was the bottleneck — how did you find it, and what did you change? | Suppose {slot} was the bottleneck in a system you did not write — how would you approach finding out why? |
| `infra_ops` | Tell me about a production problem in {slot} that you were responsible for — what did you do? | Imagine you are paged for a production problem in {slot} on an unfamiliar system — what would you do first? |
| `cross_cutting` | Tell me about a time {slot} mattered on something you built — what did you do? | Suppose you were asked to take {slot} on for a team that has never done it — how would you start? |
