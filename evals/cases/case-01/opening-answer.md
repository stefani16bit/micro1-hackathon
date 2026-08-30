# Opening answer — case-01

> **STATUS: not frozen. Produced by the pilot run.**
>
> There is deliberately no fenced block below yet. A measured run refuses to start without one,
> which is the intended failure: the opening answer must exist in the candidate's own words before
> any measurement happens, and an assistant-written draft sitting here would be used by accident.

## Why this file exists

Every interview opens the same way: *"tell me about yourself and your experience."* That answer is
the controlled stimulus of the whole experiment. It is what the interviewer reacts to, and in a
system that tunnels it is what decides which single topic swallows the next 23 minutes.

If it varies between runs, a coverage difference can no longer be attributed to the interviewer,
and the comparison across the ladder is worthless. So it is written once, frozen, and replayed
identically every time.

## How it gets frozen

Run the pilot, which types the opening live rather than replaying it:

    .venv\Scripts\python.exe -m solution.adapters.cli --iteration 0 --pilot

(Indented rather than fenced on purpose: the runner reads the *first fenced block* in this file as
the frozen answer, so until one exists, nothing here can be mistaken for it.)

Answer it as you actually would — genuine, not engineered to bait the interviewer. The natural
answer already leads with the strongest and most recent work, which is the condition under which
tunneling happens in real interviews. Manufacturing bait would make the result a trick rather than
a finding.

What you type is then copied verbatim into a fenced block in this file. From that point the runner
reads exactly that text and replays it in all eleven measured runs.

## After freezing, read it back once

Read the frozen answer the way the interviewer will. Note which competencies it hands over for
free, and which it leaves untouched — the untouched ones are where the measurement actually
happens.
