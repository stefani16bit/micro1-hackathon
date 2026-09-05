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

Reply with your next message to the candidate, as JSON.
```

---

## Exactly what the model receives

Nothing on this page reaches the model except the two fenced blocks above. `load_prompt_pair`
extracts them and nothing else, so this prose — including the paragraph about a well-written prompt
being sufficient — is documentation the interviewer never sees. `interview show-prompt` prints the
assembled result if you would rather check than take that on trust, and
`tests/application/test_prompt_contamination.py` fails if project vocabulary ever appears in it.

| The model gets | The model does not get |
|---|---|
| the instructions in the system block | anything about this project, the ladder, or that it is being measured |
| the job posting, **without** `role.txt`'s comment header | the slot plan, or that competencies are being counted |
| the candidate's CV, as text | how long the interview lasts, or how much of it is left |
| the transcript so far, every turn | its own earlier reasoning, beyond what it said aloud |

**Why the interviewer is not told the time.** It used to be: the system block asked it to pace
itself over 25 minutes, and every turn carried `Elapsed: N of 25 minutes`. That was removed, and the
table below is the reason it should never have been there — *time-aware scheduling* is what rung 1
contributes, so a baseline that paced itself against a clock made that row false and left rung 1
with nothing to add. The candidate still sees a countdown in their own console; that is for the
person answering, not for the model asking.

`role.txt`'s comment header is stripped for a different reason, and a worse one: it told the model
*"candidates who apply to it are screened by the AI interviewer this project examines"*, which would
have put the interviewer on notice that it was the subject of a study. See
`solution/adapters/role_text.py`.

## What this iteration deliberately does not have

The ladder is three rungs above this one, each switching on one mechanism
(`PREREGISTRATION.md` §3e):

| Absent here | Arrives in |
|---|---|
| Deterministic topic selection from a frozen slot plan | **rung 1** |
| A record of which competencies have been covered | **rung 1** |
| A follow-up budget, and time-aware scheduling | **rung 1** |
| Context isolation between turns | **rung 2** |
| Composing the next question while the candidate answers | **rung 2** — it is what isolation buys |
| Verification of the generated question before it is asked | **rung 3** |
| A leakage gate on clarification replies | **rung 3** |

The transcript is passed in full on every turn, and the model decides everything else. That is the
floor, and `PREREGISTRATION.md` states — before this iteration is ever run — what we expect the
floor to look like.
