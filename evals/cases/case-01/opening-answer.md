# Opening answer — case-01

> **STATUS: frozen.** Captured live during iteration 0 and written by
> `interview run --baseline`, character for character as it was typed. Never edited
> afterwards - editing it would make the runs incomparable, and the run refuses to
> start if its digest moves.

## Why this file exists

Every interview opens the same way: *"tell me about yourself and your experience."* That answer is
the controlled stimulus of the whole experiment. It is what the interviewer reacts to, and in a
system that tunnels it is what decides which single topic swallows the next 23 minutes.

If it varies between runs, a coverage difference can no longer be attributed to the interviewer,
and the comparison across the ladder is worthless. So it is given once, frozen, and replayed
identically every time.

## How it gets frozen

Start the ladder:

    .venv\Scripts\python.exe -m solution.adapters.cli run --baseline

(Indented rather than fenced on purpose: the runner reads the *first fenced block* in this file as
the frozen answer, so until one exists, nothing here can be mistaken for it.)

There is no separate step. The baseline run notices this file holds no opening answer, tells you so
before it starts, and **freezes your first answer the moment you give it** — character for
character, appended to this file as a fenced block, with the status line above rewritten. Every
later rung then replays exactly that text.

Answer as you actually would — genuine, not engineered to bait the interviewer. The natural answer
already leads with the strongest and most recent work, which is the condition under which tunneling
happens in real interviews. Manufacturing bait would make the result a trick rather than a finding.

## Why the machine writes it and not you

An earlier design printed the answer and asked a person to paste it here. That was replaced, and
the reason is worth keeping: pasting puts a gap between what was said under a 120-second clock and
what ends up frozen, and that gap is exactly where an answer gets quietly improved. Capturing it in
code means the frozen stimulus is what was actually typed during the interview, with no opportunity
to polish it afterwards.

The same run records `evals/experiment-lock.yaml`, which includes this answer's digest. From that
point a run against a different opening does not start.

## After it is frozen, read it back once

Read the frozen answer the way the interviewer will. Note which competencies it hands over for
free, and which it leaves untouched — the untouched ones are where the measurement actually
happens.

**Do not edit it.** A better way of saying the same thing is a different experiment. If it genuinely
has to change, that is `interview run --baseline --restart`, which starts the ladder again from the
first rung and records why in `CHANGELOG.md`.

---

## The frozen opening answer

Captured 2026-08-31, during the iteration 0 interview. This is the text every
measured run replays, and the runner reads it from the fenced block below.

```
I'm Stefani, based in São Paulo, Brazil. I finished my Computer Science degree this year, and I built my career as a software developer along the way, so I have just over three years of professional experience.

Most of that experience comes from consultancies. I started at Company Y in 2023, first as an intern and then as a software developer. I built internal web applications in TypeScript, Nodejs and Reactjs, dashboards and operational portals that the back-office and operations teams used every day. On the back-end I also worked with Python and SQL, exposing REST APIs for those applications.

At Company X I moved into a much more complex environment and really grew technically. I worked on payment microservices, developing and maintaining services that processed thousands of transactions a day across different payment methods. The stack was TypeScript, Nodejs and AWS Cloud, with strong engineering practices behind it: clean architecture, event driven architecture, and test driven development. 

Now I'm look for a opportunity at micro1 as a software developer.
```
