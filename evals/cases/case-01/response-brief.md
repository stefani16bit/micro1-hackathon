# Response brief — case-01

> **STATUS: drafted, awaiting the candidate's correction pass. Not frozen.**
>
> Items marked **⚠ CONFIRM** were drafted from the CV by the assistant and contain specifics the
> CV does not state. Each one must be confirmed as true, corrected, or **deleted**. An item the
> candidate cannot confirm is removed rather than softened — this file is the factual basis of
> eleven interviews and of every quote in the final reports.

## What this file is for

The same person answers all 11 interviews. This file fixes the *content* they draw on, so that the
interviewer's questions are the only thing moving between iteration 0 and iteration 10.

It matters most for **iterations 0 to 3**, which have no scheduler: there the model chooses topics
freely, so what the candidate says directly determines what gets asked next. From iteration 4 the
scheduler fixes topic selection, but answer *length* still consumes the shared time budget, and the
carry-over metric is computed from the terms in previous answers — so the control still holds.

## Rules for the respondent

1. **Answer only from this brief.** If a question reaches something genuinely not here, answer
   honestly, then add the fact to the brief afterwards and note it in `CHANGELOG.md`. The brief
   grows; it does not get quietly rewritten.
2. **Do not improve your answers between runs.** If in run 6 you find a sharper way to tell the
   migrations story, that is a change to the experiment. It goes into the brief before the *next*
   run and it gets recorded — otherwise later iterations look better for a reason that has nothing
   to do with the system.
3. **Answer naturally.** Do not pad to fill the 120 seconds, and do not compress to look efficient.
4. **The opening answer is pasted verbatim** from `opening-answer.md`, every run, unedited.

---

## 1. frontend — *no hands-on evidence in the CV*

**Not drafted, and deliberately so.** React appears in the CV's skills list; neither role in the
work history uses it. Inventing frontend experience here would erase the finding this whole project
rests on — that an interviewer which follows the candidate's strongest material never discovers the
gap that decides a Full Stack Developer application.

The honest position, to be held identically in all 11 runs:

> I don't have professional frontend delivery experience. React is on my CV as familiarity — I can
> read it and I've worked alongside frontend teams — but I haven't owned frontend work in
> production. My delivery experience is backend, data and infrastructure.

**⚠ CONFIRM — one line from the candidate:** any real frontend exposure at all (university project,
personal project, a frontend PR reviewed, one screen touched at work)? If none, say none. "None" is
a complete answer and a useful one.

**How you would approach an unfamiliar frontend codebase** — ⚠ CONFIRM this reflects how you would
actually work:

> I'd start from the outside in: run it, find the screen the task touches, then trace that screen
> back to where it gets its data. I'd look at how state and API calls are organised before writing
> anything, because that's where a codebase's conventions actually live. Then I'd make the smallest
> possible change and see what breaks. It's the same approach I use on an unfamiliar backend
> service — the language is different, the method isn't.

---

## 2. backend — *evidenced*

Facts from the CV (verified):

- Payment microservices at Thoughtworks: credit card, boleto and Pix, thousands of daily
  transactions, for a large Brazilian cosmetics company and its franchise network.
- TypeScript and Node.js, applying Clean Architecture, Domain-Driven Design and TDD.
- Event persistence in DynamoDB: domain events consumed by downstream services.
- Accenture: Python, Java, SQL; GraphQL APIs; Selenium and SAP scripting.
- Python RPA automations: 3–5 analyst hours per day reduced to under 10 minutes unattended.

**⚠ CONFIRM — a design decision you personally made, and what it cost.** Drafted:

> Persisting domain events in DynamoDB before the downstream services consume them. It gives you a
> record of what actually happened, so a downstream service that was down can catch up instead of
> losing transactions. What it cost: an extra write on every payment path, and now there are two
> things that have to stay consistent — the transactional state and the event record. It also puts
> the burden of idempotency on the consumers, because a replay will deliver an event twice.

---

## 3. api_contract — *evidenced*

Facts from the CV (verified):

- API Gateways with Cognito authorizers; HTTP and consumer Lambdas over SNS/SQS; IAM roles and
  resource policies; base path mappings, rate limiting, timeouts, stage configuration.
- OAuth 2.0, AWS Cognito, mTLS/TLS — app clients, scopes, credentials, routing, authorizers.
- GraphQL APIs at Accenture.

**⚠ CONFIRM — a time the contract between two services was wrong or ambiguous.** Drafted:

> A timeout mismatch. The API Gateway cuts a request off at 29 seconds, but the processing behind
> it could take longer under load. The caller saw a timeout and retried, so the same payment got
> submitted twice — the contract said nothing about how long the callee was allowed to take, or
> what a retry meant. We fixed it on both sides: the slow path moved to an asynchronous flow over
> SQS, and the consumer was made idempotent on the transaction id.

---

## 4. data_layer — *evidenced*

Facts from the CV (verified):

- Event persistence in DynamoDB, consumed by downstream services in an event-driven architecture.
- Schema evolution through Knex migrations.
- SQL optimisation for regulatory reporting in payments: **20 minutes to 1.5 minutes**.

**⚠ CONFIRM — how you found the bottleneck and how you verified the result.** Drafted:

> The report generation was slow enough that people noticed, so I timed the stages rather than
> guessing: the query was almost all of it, not the file writing. Reading the plan, it was doing
> the work per row instead of in a set. I rewrote it and adjusted the indexes it depended on.
> Verified by running the same report over the same period before and after — 20 minutes down to
> about a minute and a half, same output file.

---

## 5. cross_boundary_debugging — *no hands-on evidence in the CV*

Nothing in the CV describes a bug that crossed the UI/API boundary. The nearest real material:

- Fuzzy matching on Levenshtein distance to reconcile records with inconsistent or misspelled data
  where exact matching was not viable.
- Selenium and SAP scripting for data validation and integrity checks.

**⚠ CONFIRM — the hardest bug you chased across two systems.** Not drafted: this needs to be a real
one. If the honest answer is *"my hard bugs have been between backend services, not between a UI
and an API"*, that is the answer, and the timeout/duplicate-payment story in section 3 is the
natural thing to reach for. Say so explicitly rather than stretching a story to fit.

---

## 6. code_quality — *evidenced*

Facts from the CV (verified):

- Clean Architecture, Domain-Driven Design, TDD, Clean Code, Design Patterns.
- Trunk Based Development; Jenkins CI/CD for automated build, test and production releases.
- AI-assisted development with AWS Kiro, Devin and Claude Code, using Spec-Driven Development.

**⚠ CONFIRM — a code review that changed a design.** Drafted:

> A review where someone pointed out that business rules had leaked into the Lambda handler — the
> handler was doing validation and orchestration that belonged in the use case. It passed its
> tests, but the tests were going through the handler, which meant they were slow and coupled to
> the AWS event shape. Moving the logic behind the use-case boundary meant the rules could be
> tested directly. It's the kind of comment that looks like style and isn't.

---

## Facts available but not volunteered

True, on the CV, and answered if asked — but never raised unprompted. Whether the interviewer
reaches them is part of what is being measured.

- AWS Certified Cloud Practitioner.
- GCP: Cloud Functions and Compute Engine — a second cloud, not only AWS.
- Computer Science degree, University São Judas Tadeu, expected June 2026.
- English at CEFR C1.
