# Response brief — case-01

> **DRAFT.** Drawn from the CV by the project author, to be reviewed, corrected and completed
> before it is frozen. Sections marked `TO COMPLETE` need facts only the candidate has.

## What this file is for

The same person answers all 11 interviews. This file is what makes that a controlled experiment
rather than a confound: it fixes the *content* the candidate draws on, so that the only thing
moving between iteration 0 and iteration 10 is the interviewer's questions.

## Rules for the respondent

1. **Answer only from this brief.** If a question reaches something genuinely not here, answer it
   honestly, then add the fact to the brief afterwards and note it in `CHANGELOG.md`. The brief
   grows; it does not get quietly rewritten.
2. **Do not improve your answers between runs.** This is the rule that costs something. If in
   run 6 you find a sharper way to tell the migrations story, that improvement is a change to the
   experiment, not a change to your delivery — it goes into the brief before the *next* run and it
   gets recorded, because otherwise later iterations look better for a reason that has nothing to
   do with the system.
3. **Answer naturally.** Do not pad an answer to fill the 120 seconds, and do not compress it to
   look efficient. How you would really answer is the measurement.
4. **The opening answer is pasted verbatim** from `opening-answer.md`, every run, without edits.

---

## By competency

### 1. frontend — *no hands-on evidence in the CV*

The CV lists React under skills, but neither role in the work history uses it. Expect a
hypothetical rather than a past-experience question.

- `TO COMPLETE`: any real frontend exposure — university projects, personal projects, small work
  contributions, code review of frontend PRs. Be specific and honest about the scale.
- `TO COMPLETE`: how you would actually approach picking up a frontend codebase you do not know.
- Consistent honest position to hold across all 11 runs, so it does not drift:
  `TO COMPLETE` — one or two sentences.

### 2. backend — *evidenced*

- Payment microservices at Thoughtworks: credit card, boleto and Pix, thousands of daily
  transactions, for a large Brazilian cosmetics company and its franchise network.
- TypeScript and Node.js, applying Clean Architecture, Domain-Driven Design and TDD.
- Accenture: back-end in Python, Java and SQL; GraphQL APIs; Selenium and SAP scripting for data
  validation and integrity checks.
- Python RPA automations replacing manual back-office routines: 3–5 analyst hours per day reduced
  to under 10 minutes of unattended execution.
- `TO COMPLETE`: one concrete design decision you personally made in the payments services, and
  the trade-off it cost you.

### 3. api_contract — *evidenced*

- API Gateways with Cognito authorizers; HTTP and consumer Lambdas over SNS/SQS; IAM roles and
  resource policies; base path mappings, rate limiting, timeouts, stage configuration.
- Authentication and authorization with OAuth 2.0, AWS Cognito, mTLS/TLS — app clients, scopes,
  credentials, routing, authorizers.
- GraphQL APIs at Accenture.
- `TO COMPLETE`: a time the contract between two services was wrong or ambiguous, and what you did.

### 4. data_layer — *evidenced*

- Event persistence in DynamoDB: domain events consumed by downstream services in an event-driven
  architecture.
- Schema evolution through Knex migrations.
- SQL optimisation for regulatory reporting files in payments: file generation cut from
  **20 minutes to 1.5 minutes**.
- `TO COMPLETE`: how you found that the query was the bottleneck, and how you verified the result.

### 5. cross_boundary_debugging — *no hands-on evidence in the CV*

Nothing in the CV describes debugging a bug that crossed the UI/API boundary. The nearest material:

- Fuzzy matching on Levenshtein distance to reconcile records with inconsistent or misspelled data
  where exact matching was not viable.
- Selenium and SAP scripting for data validation and integrity checks.
- `TO COMPLETE`: the hardest bug you have personally chased across two systems — even if both were
  backend. Say plainly if it was never a UI-to-API bug; that is a real answer, not a bad one.

### 6. code_quality — *evidenced*

- Clean Architecture, Domain-Driven Design, TDD, Clean Code, Design Patterns.
- Trunk Based Development; Jenkins CI/CD pipelines for automated build, test and production
  releases.
- AI-assisted development with AWS Kiro, Devin and Claude Code, using Spec-Driven Development.
- `TO COMPLETE`: a code review you gave or received that changed the design, and what changed.

---

## Facts deliberately available but not volunteered

These are true and on the CV, and the candidate answers about them if asked — but does not
volunteer them unprompted. Whether the interviewer reaches them is part of what is being measured.

- AWS Certified Cloud Practitioner.
- GCP: Cloud Functions and Compute Engine — a second cloud, not just AWS.
- Computer Science degree, University São Judas Tadeu, expected June 2026.
- English at CEFR C1.
