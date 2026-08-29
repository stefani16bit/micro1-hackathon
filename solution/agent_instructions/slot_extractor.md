# Agent instruction — slot extractor (call L1)

**Runs:** once per role, offline, before any interview exists.
**Human checkpoint:** a person reviews and edits the output before it is frozen into
`roles/<role>/slots.yaml`. Nothing downstream ever revisits this decision.

## Why this call is offline

The slot plan is the denominator of the primary metric. If it were derived during an interview it
could be influenced by the conversation, and coverage would become a number the system could move
by redefining what counts as covered. Extracting it once, reviewing it by hand, and freezing it is
what makes coverage a measurement rather than a self-assessment.

## System prompt

```
You extract the competencies a job description requires, so that an interview can be
planned to cover them.

Read the job description and list every distinct technical competency it asks for.

RULES
- A competency is something a candidate could be asked to describe from experience.
  "React" is a competency. "Team player" is not. "5 years of experience" is not.
- Merge near-duplicates. If the description mentions React, Redux and hooks, that is one
  competency (frontend / React), not three.
- Split genuinely different areas. "Backend and databases" is two competencies, because a
  candidate can be strong in one and weak in the other.
- Rank by relevance to the role: rank 1 is the competency the job description leans on
  most heavily, judged by prominence, repetition and whether it is listed as required
  rather than preferred.
- Aim for 6 to 10 competencies. Fewer than 6 usually means you merged too aggressively.
- keywords are the words an interviewer would actually use when asking about this
  competency, including the technology names the description mentions. They are matched
  literally and case-insensitively later, so give lowercase single words or short
  phrases, not sentences.
- kind selects the question template used when generation fails:
    language_framework - a language, framework or library
    data_storage       - databases, caching, storage, data modelling
    infra_ops          - cloud, deployment, CI/CD, monitoring, incidents
    cross_cutting      - testing, code review, architecture, security, collaboration
      practices

Reply with JSON only, no prose.
```

## Output schema

```json
{
  "type": "object",
  "properties": {
    "competencies": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id":       {"type": "string"},
          "name":     {"type": "string"},
          "kind":     {"type": "string",
                       "enum": ["language_framework", "data_storage", "infra_ops", "cross_cutting"]},
          "rank":     {"type": "integer"},
          "keywords": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["id", "name", "kind", "rank", "keywords"]
      }
    }
  },
  "required": ["competencies"]
}
```

## What happens to the output

1. The top `max_slots` competencies by rank become the slot plan.
2. The remainder are written to the `excluded` section of `slots.yaml` **with the reason**, so the
   cut made by the time budget is visible rather than silent.
3. A human reviews both lists, edits freely, and commits the file. From that commit on, the plan is
   read-only for the rest of the project.
