# Response brief — case-01

> **STATUS: frozen 2026-08-31**, transcribed from the iterations 0 and 1 transcripts. Everything
> below is something the respondent actually said in a recorded interview; nothing is invented, and
> nothing is polished into a better answer than the one that was given.

## What this is for

The brief holds the *content* of the answers constant across rungs, so that the interviewer's
questions stay the only moving variable. It is organised by competency rather than as
question-and-answer pairs, because only the opening question is fixed — the rest are generated, and
a brief that anticipated them would push the respondent to fit their answer to prepared material.

**It was produced from the transcripts, not before them.** That ordering has a cost, recorded in
`PREREGISTRATION.md` §1a and §1c: **rungs 0 and 1 were answered from memory**, without this file, and
rungs 2 and 3 are answered with it. Every fact here was already said unbriefed, so the brief cannot
add substance to a later answer — but it does make one easier to recall, and that asymmetry is
disclosed rather than absorbed.

Sources: [`iteration-00/session-20260831-120601.jsonl`](../../results/iteration-00/session-20260831-120601.jsonl)
and [`iteration-01/session-20260831-153049.jsonl`](../../results/iteration-01/session-20260831-153049.jsonl).
Read either back with `interview show <record>`.

## Rules for the respondent

1. **Answer from this brief.** If a question reaches something genuinely not here, answer honestly,
   then add the fact afterwards and note it in `CHANGELOG.md`. The brief grows; it is not quietly
   rewritten.
2. **Do not improve your answers between runs.** A sharper way of telling the same story is a
   change to the experiment. It goes into the brief before the *next* run, and it gets recorded —
   otherwise later rungs look better for a reason unrelated to the system.
3. **Answer naturally, and take the time the answer needs.** Nothing times you. That freedom is the
   one confound this design no longer prevents — answers that lengthen across runs shorten the
   interviews and depress coverage for a reason that is not the interviewer. Every run reports its
   answer durations so the effect is visible (`PREREGISTRATION.md` §1b), but keeping them comparable
   is on you.
4. **Use the names the committed CV uses** — *Company X*, *Company Y*, *University Name*. Naming a
   real employer introduces a term the interviewer never saw, which counts against grounding and
   towards carry-over for a reason that has nothing to do with the interviewer.

The brief is the one input the experiment lock **tracks rather than freezes**, precisely so rule 1
stays possible: every run records its digest, so a reader can see which runs saw which version.

---

## Background (the frozen opening answer covers this)

Based in São Paulo. Computer Science degree finished this year; just over three years of
professional experience, mostly from consultancies.

**Company Y**, from 2023, intern then software developer — internal web applications in TypeScript,
Node.js and React.js; dashboards and operational portals used daily by back-office and operations
teams. Also Python and SQL on the back end, exposing REST APIs for those applications.

**Company X** — payment microservices processing thousands of transactions a day across several
payment methods. TypeScript, Node.js and AWS, with clean architecture, event-driven architecture
and TDD.

---

## `frontend` — frontend development

**A slow, hard-to-maintain dashboard.** A dashboard with a lot of data was becoming slow to use and
difficult to maintain. Found the performance problems came from unnecessary renders and from how the
data was being fetched and processed; refactored some of the components and changed the way the data
was handled. The dashboard became much more responsive and the code easier to maintain.

**Making a dashboard work across screen sizes.** Used mainly by operations teams, so the priority
was keeping the important information accessible without crowding the interface. Broke the dashboard
into reusable components and used responsive layouts with a CSS framework, adapting tables, cards
and navigation to the screen size. One dashboard that worked across devices instead of separate
versions.

**Handling a slow or unreliable API in the UI.** The concern was the UI looking frozen and the user
not knowing whether their action had worked. Modelled the request states explicitly — loading,
success, error — showed a loading state while pending, and disabled the action that could trigger
duplicate requests.

**React Query, concretely.** Used for both state management and data fetching. Configured a limited
retry count with a delay between attempts (`retry: 2` and a retry delay) so as not to hammer an
already unreliable API. When the automatic retries were exhausted the query entered the error state,
which showed a message plus a manual retry button; the button's `onClick` calls `refetch()`, which
runs the query function again.

## `backend` — backend development

**A new Pix flow in the payment microservices.** The requirement was to support the new flow without
affecting the existing payment methods. Worked on the API and the integration with other services,
following the existing architecture and adding tests for the new behaviour. Events were used to
communicate between some of the services.

**Idempotency for duplicate payment requests.** Retries and network issues meant the same payment
request could reach the backend more than once, and the same payment must not be processed twice.
The idempotency key is generated in the backend but is **not random per request** — it is derived
from a stable identifier of the operation, the payment transaction ID, so a retry of the same
payment produces the same key.

The record lives in **DynamoDB**. A conditional expression means only the first request can create
it, so only that request becomes the owner of the operation. It then processes the payment and
updates the record with the final status and result. A later request with the same key fails the
conditional write, so instead of processing again it reads the existing record: if the operation is
complete it gets the stored result, and if it is still running it gets a processing status.

## `api_contract` — the API contract between frontend and backend

**Changing a REST contract already in use by a React dashboard.** The concern was not breaking the
frontend while the backend was being deployed. Rather than changing the existing response directly,
the new contract was introduced in a backward-compatible way; on the frontend the API client and the
TypeScript types were updated to handle the new response structure, and compatibility with the old
fields was kept during the transition. Integration tests were updated to cover both the contract and
the dashboard behaviour. Backend and frontend could then be deployed independently, with no downtime
and without breaking existing users.

## `data_layer` — the data layer

**The regulatory reporting query.** It took around 20 minutes because it queried a large amount of
payment data with several joins and aggregations. Used `EXPLAIN ANALYZE` to find the expensive
parts: missing indexes, and joins and filters causing large table scans. Added indexes, optimised the
joins, and moved some of the filtering earlier in the query so it processed less data. (The CV
records the result as 1.5 minutes.)

**Also true, from the CV:** database schema evolution managed through Knex migrations.

## `cross_boundary_debugging` — debugging across the frontend/backend boundary

**This is the slot the CV marks `has_experience: false`**, and it is the only one. It gets a
situational question rather than a behavioural one, which is the fair way to ask about something you
have not done.

**The approach given, when asked hypothetically:** verify the data at each layer. Reproduce the
database query directly with the same filters and parameters the API uses, then compare that with
the API response, checking backend logs and query parameters to see whether the data is already
wrong there. If the API response is correct, inspect the React side — state management, data
transformation, rendering. Also check caching, pagination, filters and date/timezone handling, which
cause this kind of discrepancy. Isolate the layer before changing anything.

**The general process, from iteration 0:** reproduce, inspect the UI, inspect the network tab, trace
the request through the backend logs.

> **A gap, recorded rather than filled.** Iteration 0 asked twice for a *specific* incident — a real
> debugging story with a symptom, a network tab, logs and a root cause — and no concrete example was
> given; the second attempt ran out of time and got an empty answer. That is an honest state of the
> evidence, not an omission to fix here. **Do not invent one.** If a later rung asks again, the
> honest answer is that the hard bugs were between backend services rather than between a UI and an
> API.

## `code_quality` — code quality, review and documentation

**A Clean Architecture violation found in review.** Noticed a use case depending directly on
infrastructure code, which coupled the business logic to the database layer. Suggested introducing a
repository interface in the application layer so the use case depends on the abstraction, with the
infrastructure layer providing the implementation. The result was code that was easier to test, with
the business logic independent of the infrastructure.

**Also true, from the CV:** TypeScript and Node.js applying Clean Architecture, Domain-Driven Design
and TDD.

---

## Facts available but not volunteered

True and on the CV, answered if asked, but unlikely to be raised unprompted — the opening answer
leads with the most recent work. Whether the interviewer reaches them is part of what is measured.

- AWS Certified Cloud Practitioner.
- GCP: Cloud Functions, Cloud Run, Compute Engine — a second cloud, not only AWS.
- English at CEFR C1; Spanish basic to intermediate.
- The frontend work is at the *earlier* employer (Company Y), not the most recent one.
- Serverless AWS: Lambda, SQS, Cognito.
