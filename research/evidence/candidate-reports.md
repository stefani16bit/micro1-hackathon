# Candidate reports — r/micro1_ai

Four accounts of the interview, from candidates who sat it. They are the reason the bottleneck in
`README.md` is described as *allocation* rather than as *missed topics*: none of these people say
they were never asked about their field. They say the interview spent itself going deeper and
deeper into one corner of it.

---

## What this is, and what it is not

**It is not measurement.** Read it as the reason a hypothesis was worth testing, never as a result.
Four specific limits, stated so nobody has to infer them:

- **Self-selected.** People who post about an interview are disproportionately people it went badly
  for. Nothing here estimates how common this is, and this file must never be used as if it did.
- **n = 4**, from one thread, on one subreddit.
- **Not this project's role.** These are voice coaching, video editing and annotation roles — not
  the Full Stack Developer posting in `roles/fullstack/`. That cuts both ways: it means they are
  not direct evidence about the evaluation case, and it means the behaviour they describe is not
  specific to software interviews.
- **Unverifiable from here.** Reddit blocks automated fetching, and its public JSON API returns 404
  (checked against a control subreddit, so it is the route rather than the subreddit). These were
  transcribed by the project author from screenshots and re-typed into this file. The permalinks
  below are how a reader checks them; this file is not itself the source.

**Attribution.** Usernames are deliberately not reproduced. The quotes are all that matter here,
the permalink makes each one checkable, and there is no reason a public repository should make four
pseudonymous individuals easier to find. The four quotes are from **four distinct accounts**, which
is the only thing about their identity that carries any weight.

**Source.** Thread *"Interviews with Zara the Terrible"*, r/micro1_ai, posted approximately
2026-07 (Reddit showed "2 months ago" when captured on 2026-08-31):
<https://www.reddit.com/r/micro1_ai/comments/1uqm2xr/interviews_with_zara_the_terrible/>

Two comments were singled out by the project author, at
`/comment/ow952nn/` and `/comment/owfajrs/` on that thread. Which of the transcriptions below
corresponds to which permalink was not established, and is not guessed at here.

---

## 1. The original post

> Is anyone else convinced that Zara isn't interviewing for a voice coach but for an intergalactic
> AI voice deity?
>
> I went into the interview thinking, "Great, I've spent over a decade teaching English, coaching
> pronunciation, analysing speech, correcting intonation and helping thousands of students improve
> their spoken communication."
>
> Twenty-three minutes later I was questioning every life decision I'd ever made.
>
> **Every question seemed to one-up the last.** You answer one and then suddenly you're wondering
> whether they actually wanted someone with a PhD in acoustic phonetics, speech science,
> neuroscience, AI annotation, voice acting, emotional psychology and possibly communication with
> extraterrestrial life.
>
> By the end I wasn't even sure what job I'd applied for.
>
> I'm not complaining that the interview was challenging, I enjoy being challenged, but **the
> expectations felt miles away from what the advert suggested.** It left me completely bewildered.

## 2. On questions that restate the previous one

> I actually just provided similar feedback at the end of my interview today. I don't know that they
> read the feedback, but I still voiced my thoughts… just as some of you have said, **she builds on
> the answers and turns it into the same question with an additional detail or rebranded phrases
> added to it. That has been the entirety of my past couple of interviews.** I also noted that she
> is very bland, un-engaging, and flat — at best, she makes even Domain Experts feel ignorant, not
> necessarily due to the questions she asks, but the manner in which she responds and presents
> information… it's like you're being judged by some elite CEO of a company and you're just a
> little peasant

## 3. On following a passing mention

> I believe she's been a little strange lately, **she builds off your answers too much, mention
> something tangentially math related and soon she will be asking you to solve The Riemann
> Hypothesis**, like what? I thought I was applying to annotate videos??? Haha

*(35 upvotes, the highest-scored comment captured.)*

## 4. On half the interview going to one thing

> It was a really bad experience. I am filmmaker and professional editor with more than 20 years of
> experience. And I used to be a computer programmer. I am very technical and love technology.
>
> **Almost half the interview was about technical specs that no one knows by heart.**
>
> It's the stuff we all used to google and access forums and now use AI.
>
> Even though the role was about video editing the questions were about some specific parameters and
> jargons that no editor need to deal with on a daily basis.
>
> Any way, I got rejected and **the system broke and can not provide me a detailed feedback of my
> interview.**

And the reply to it:

> Same! Also an editor with decades of experience. "Zara" was asking questions about some
> ridiculously detailed option in After Effects that I have had to lay hands on maybe 2-3 times in
> my career and then asks me to explain in detail what it does and when to apply it. Please.
> Pointless. If I need it I Google it, watch a tutorial, do it, and then move on with my life and
> forget it. **Questions like these do not assess anyone's real world knowledge or ability.**

---

## What these map onto, and what they do not

Each row names the measurement that would detect the described behaviour, so a reader can check
whether the instrument actually addresses the complaint rather than taking the connection on trust.

| What they describe | What measures it |
| --- | --- |
| *"turns it into the same question with an additional detail added"* | `longest_chain` — consecutive questions on one competency (`evals/metrics/allocation.py`) |
| *"every question seemed to one-up the last"* | `longest_chain`, and the follow-up ceiling the scheduler enforces |
| *"builds off your answers too much"*, the tangent that becomes the whole interview | **carry-over rate** — a question reaching for a term the candidate raised, outside the competency being asked (`evals/metrics/rates.py`) |
| *"almost half the interview was about technical specs"* | `max_slot_share` and `normalised_entropy` |
| *"the expectations felt miles away from what the advert suggested"* | **coverage** — measured against the frozen plan derived from the job description, and nothing else |
| *"I wasn't even sure what job I'd applied for"* | the same; coverage's denominator *is* the posting |

**Two complaints this project does not address, named so the gap is visible rather than quiet:**

- *"very bland, un-engaging, flat"*, and being made to feel judged. That is conversational manner,
  and it is the one thing the Zara paper's own metrics already score well (§5.1: conversational
  dynamics 8.27 against a human-led 5.49). Nothing here measures it or claims to improve it.
- *"the system broke and can not provide me a detailed feedback"*. Post-interview feedback is
  phases (3) and (4) of the paper — the part micro1 *has* published — and is out of scope for a
  project about how the interview is conducted.

**One thing worth noticing about the sample.** These are a voice coach, a video editor and an
annotator. The behaviour described — escalating depth inside whatever the candidate mentioned — is
the same in all four, across unrelated roles. That is consistent with it being a property of the
interviewing policy rather than of any one domain, which is the premise this project tests. It is
consistent with it; four self-selected reports cannot establish it.
