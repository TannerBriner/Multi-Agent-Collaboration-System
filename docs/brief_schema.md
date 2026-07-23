# Structured Brief Schema

This is the contract between the intake agent and every downstream stage. Drafters never
see the original raw request — only this object. That boundary is deliberate: it forces
all ambiguity to be resolved once, at intake, instead of being re-interpreted
inconsistently by three different drafters.

This schema is also the input schema for the intake agent's `submit_brief` tool. Tool-use
gives us guaranteed-valid JSON instead of parsing prose out of a text response.

```json
{
  "campaign_name": "string",
  "objective": "string — what business outcome this supports",
  "audience": "string — who this reaches",
  "key_message": "string — the ONE thing every deliverable must communicate",
  "channels": ["email", "social", "intranet"],
  "deadline": "string or null",
  "tone": "string",
  "constraints": "string or null — legal, budget, exclusions",
  "missing_fields": ["array of field names the request did not contain"]
}
```

## Required fields

`objective`, `audience`, and `key_message` are required. If the intake agent cannot
extract any one of these from the request, it does not fabricate a value and does not
call `submit_brief`. Instead it calls a second tool, `ask_clarifying_questions`:

```json
{
  "questions": ["2 to 4 specific questions, each naming what's missing and why it matters"]
}
```

When `ask_clarifying_questions` is called, the pipeline stops for that run. No brief is
produced, no drafters run. The next run (once a human supplies the missing info) is a
fresh intake call over the combined text.

## Extraction rule

The intake agent extracts only what the request actually states. It never invents an
audience, deadline, or key message to fill a gap — a fabricated brief field is this
workflow's equivalent of a hallucinated citation, and it's worse than stopping the
pipeline, because it would let a wrong brief flow silently into three drafts and a review
pass that all "look" successful.

## `missing_fields`

Even on a successful `submit_brief` call, `missing_fields` records anything the request
didn't explicitly state but that the agent was able to infer safely (e.g. `tone` inferred
from context rather than stated outright) or fields that are optional and genuinely
absent (e.g. `deadline`, `constraints`). This gives the run log a record of how much the
intake agent had to infer versus what was given outright — the raw material for the
"intake completeness rate" metric.
