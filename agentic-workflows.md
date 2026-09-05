# micro1 — Hackathon

**The mandate, verbatim from the brief:** *"Pick a specific and meaningful problem you understand.
Use agents to solve it and show through clear evidence that your solution improves the way the
task is handled today."*

Practical beats impressive. The goal is something a real person would want to use.

---

## 1. Problem statement — NOT YET DEFINED

- **Target user:** `<!-- who -->`
- **Their bottleneck today:** `<!-- what makes the task slow, error-prone or inconsistent -->`
- **Why solving it is valuable:** `<!-- practical consequence -->`
- **Primary metric:** `<!-- the one number that means success to this user -->`
- **Evaluation cases:** `<!-- what a case is, where they come from, how many -->`

**Do not start building until this block is filled.** Every rubric criterion is graded against
it — a solution without a named user and a named bottleneck loses points in five of six rows.

---

## 2. The four questions behind every decision

Keep these visible at all times; the brief repeats them as the self-check:

1. **Who has this problem?**
2. **What bottleneck makes it worth solving?**
3. **Does the agent solve it well?**
4. **Can another person reproduce the result?**

---

## 3. Judging rubric — 100 points

This is the prioritization function. When trading off work, spend where the points are.

| Criterion | Pts | What strong work looks like |
|---|---:|---|
| Problem & User Value | 15 | A meaningful problem for a clearly defined user. *Who experiences the bottleneck and why does solving it matter?* |
| **Agent Solution & Engineering** | **30** | Agents used **purposefully** and technically sound. Better context or tools may carry one project; memory, verification, skills or orchestration may carry another. *Which design choices helped the agent solve the problem?* |
| **End to End Quality** | **20** | A realistic, self-contained execution producing a result the user can actually use, with the finish of something a person would sign their name to. *Would the intended user consider this high quality, or does it read as clearly AI generated?* |
| Measured Improvement | 15 | Demonstrated gains over a fair baseline, with the changelog connecting each iteration to evidence. *Which changes truly improved the outcome?* |
| Reproducibility | 15 | A clear path for another person to run solution and baseline and reach the main result. *Could they do it from a clean environment?* |
| Hot Take / Insights | 5 | An observed failure mode turned into a practical lesson for building more reliable agents. *What did you learn and how would it change what you build next?* |

Two consequences worth internalizing:

- **Purposeful choices matter more than the number of components.** Do not stack memory +
  verification + multi-agent orchestration because they sound sophisticated. Each component must
  be traceable to a failure it fixed, and that trace belongs in the changelog.
- Engineering (30) + End-to-End Quality (20) is **half the score**. One polished workflow that
  runs end to end beats a broad feature surface that half-works.

---

## 4. Baseline discipline — non-negotiable

A baseline must exist and must be a *reasonable basic way* to handle the task. The brief's four
acceptable shapes:

- One direct prompt with basic instructions
- One general-purpose agent with basic tools
- A simple script or template
- The manual process people use today

**Fairness rules:** baseline and final solution get the **same task** and the **same evaluation
cases**. Any meaningful difference in the resources available to each must be stated explicitly
in the report. A strawman baseline invalidates the Measured Improvement score.

---

## 5. Improvement Changelog — required format

The changelog tells the story of how the solution evolved. Baseline comparison shows the *size* of
the improvement; the changelog shows *where it came from*.

| Stage | What you tried and why | Evidence | Decision / Learning |
|---|---|---|---|
| Baseline | | | Established the starting point |
| Iteration 1 | | | kept / revised / removed |
| Iteration 2 | | | kept / revised / removed |
| Final | Combined the changes that worked | | Identified the main contribution |

Rules:
- One entry per **meaningful experiment**, not per commit.
- Re-measure with the **same evaluation method** for every entry wherever possible.
- **Include experiments that were removed** and explain what they taught about the problem.
  Removals are explicitly rewarded, and the video must highlight one.
- Append the entry **at the moment of the experiment**. Reconstructing it at the end produces
  vague evidence and costs points.

---

## 6. Evaluation protocol

- Pick **one primary metric** that reflects what success means to the user. The brief's examples:
  tests passing (developer), time or cost saved (ops team), calibration (forecasting team).
- **Define what a good final result looks like before running the evaluation.**
- Target **10 or more cases** when the task allows. Include **at least one challenging case** and
  write down what it revealed.
- Same cases for baseline and final solution. **Report complete results, failures included.**

Results table:

| Metric | Simple baseline | Agent solution | Change |
|---|---|---|---|
| Primary outcome | | | |
| Human time per task | | | |
| Cost per task | | | |

If this format fits the task poorly, the brief permits designing an explicit scoring rubric
instead — but it must be written down and proposed so judges can apply it.

---

## 7. Ground rules (all 10)

1. Building with tools and components already known is welcome.
2. **Make clear what existed before the competition and what was added.**
3. Use every tool and component per its license and service terms.
4. **Keep consequential actions sandboxed or simulated, with human approval before the action.**
5. A qualified human reviewer must be part of any solution that could significantly affect someone.
6. Legal and ethical use case; treat people and their data responsibly.
7. Use information allowed to be shared — public or synthetic data is easiest; approved anonymous
   data also works.
8. **Keep credentials and private information out of the submission.**
9. Every claim about results connects to submitted evidence.
10. Give judges enough access to run the project and reproduce the main result.

---

## 8. Final deliverables — three items

1. **Solution code + Improvement Changelog.** The full project and everything required to run it,
   *including the instructions that shape each agent*. The README introduces the intended user,
   explains their current bottleneck, and why solving it is valuable. Add a clearly labeled
   **Improvement Changelog** in the format above, one entry per meaningful iteration, each tied to
   the evidence that guided the next decision. Close with **the main failure mode and the hot take**.
2. **Reproduction guide.** Written for someone starting from a clean environment: setup, the exact
   commands for solution / baseline / evaluation, which data is required, what output to expect,
   relevant versions, and approximate runtime and cost.
3. **Agent trajectories.** Representative traces for **every** agent used, easy to follow from
   agent instructions to final result: what the agent did, how its tools responded, the feedback
   that shaped the next step, plus any retries and human checkpoints.

---

## 9. Working conventions

Default repo layout — follow it unless the actual problem argues otherwise:

```
README.md            # user, bottleneck, value, results, main failure mode, hot take
CHANGELOG.md         # the Improvement Changelog table
REPRODUCE.md         # clean-environment setup + exact commands + expected output
baseline/            # the fair baseline, runnable by one command
solution/            # the agent system; agent instructions live here as files
evals/cases/         # the shared case set (10+), used by BOTH baseline and solution
evals/results/       # raw run outputs, one file per run, never hand-edited
trajectories/        # captured agent traces, one per agent, per representative run
```

- Agent instructions are **files in the repo**, not prose buried in a prompt. They are a graded
  deliverable and judges must be able to read them.
- **Capture trajectories as work happens.** They cannot be reconstructed later.
- After every meaningful change: re-run the **full** case set, save raw output to
  `evals/results/`, then append the changelog entry.
- **Every number in the README or video must point to a file under `evals/results/`.** No claim
  without evidence (ground rule 9).
- Secrets via environment variables only, never committed (ground rule 8). Commit sample or
  synthetic data so a judge can run from a clean clone.
- Quality bar: the final output must read as human-authored work someone would sign their name to,
  not a generic AI draft. This is 20 points.