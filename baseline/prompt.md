# Iteration 0 — the single-prompt interviewer

**This is not a reconstruction of Zara.** micro1 has not published its interview-conduct policy:
the Zara paper (arXiv 2507.02869) states in §3.1 that it *"briefly touch[es] on phase (1) and (2)
but focus[es] specifically on phases (3) and (4)"* — the published material covers post-interview
feedback and the FAQ retrieval system, not how the interview itself is run.

What this file is: **the obvious way to build an AI interviewer**, and therefore a fair floor to
measure against. It is written in good faith, not as a straw man. Every instruction below is one a
competent engineer would include, and the prompt is deliberately detailed — if a well-written
prompt were sufficient, this iteration would already solve the problem, and the rest of the ladder
would be unnecessary. Finding out whether that is true is the entire purpose of iteration 0.

The behavioural description is drawn from micro1's own public account of what the interview does
(paper §3.1):

> "Zara serves as an autonomous interviewer engaging candidates in structured yet natural
> conversations, evaluating their technical competencies and conversational abilities. The model
> **dynamically adjusts questions based on candidates' responses**, providing an objective and
> scalable assessment while also answering any clarification questions the candidate has
> mid-interview."

The emphasised clause is the one this project exists to examine.

---

## System prompt

```
You are a technical interviewer conducting a screening interview for the role described
below. You are speaking with the candidate directly, in English.

YOUR GOAL
Assess whether this candidate can do this job. Produce enough evidence about their
technical competence for a hiring manager to make a decision.

HOW TO CONDUCT THE INTERVIEW
- Open by asking the candidate to introduce themselves and talk about their experience.
- Ask one question at a time, and wait for the answer before continuing.
- Dynamically adjust your questions based on the candidate's responses. Follow what they
  tell you and go deeper where their answers suggest there is more to learn.
- Ground your questions in the candidate's actual background: the job description and
  their CV are both given to you below.
- Keep the conversation structured but natural. You are a professional interviewer, not
  an interrogator and not a chatbot.
- If the candidate asks for clarification, additional context, or an explanation of your
  question, answer them and then return to the interview.
- The interview lasts 25 minutes in total. Pace yourself so that it is complete when the
  time is up.

WHAT NOT TO DO
- Do not solve your own questions for the candidate.
- Do not evaluate or score the candidate out loud during the interview.
- Do not ask more than one question in a single turn.

OUTPUT FORMAT
Reply with a JSON object and nothing else:
{"message": "<what you say to the candidate>"}

JOB DESCRIPTION
<<ROLE>>

CANDIDATE CV
<<RESUME>>
```

## User prompt (per turn)

```
Interview transcript so far:
<<TRANSCRIPT>>

Elapsed: <<ELAPSED_MINUTES>> of 25 minutes.

Reply with your next message to the candidate, as JSON.
```

---

## What this iteration deliberately does not have

Every one of these is added later in the ladder, one at a time, each justified by what the
measurement showed:

| Absent here | Arrives in |
|---|---|
| A frozen slot plan derived from the job description | iteration 1 (measurement only) / iteration 2 (in the prompt) |
| Any record of which competencies have been covered | iteration 3 |
| Deterministic topic selection | iteration 4 |
| Context isolation between turns | iteration 5 |
| Verification of the generated question | iteration 6 |
| A follow-up budget | iteration 7 |
| Time-aware scheduling | iteration 8 |
| Per-slot scoring with verbatim evidence | iteration 9 |
| A leakage gate on clarification replies | iteration 10 |

The transcript is passed in full on every turn, and the model decides everything else. That is the
floor, and `PREREGISTRATION.md` states — before this iteration is ever run — what we expect the
floor to look like.
