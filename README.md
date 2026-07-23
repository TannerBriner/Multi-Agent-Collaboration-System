# Campaign Brief → Multi-Agent Content Production Pipeline

A pipeline that takes a messy, incomplete campaign request in plain English and produces
a reviewed, approval-ready content package for multiple channels, with a human sign-off
gate at the end. It never publishes anything — the output is a single markdown file a
human reads and approves.

**Stack:** Python · Anthropic Claude API (native tool-use, no framework) · SQLite (run log)

---

## Problem

A marketing/comms team receives campaign requests by email or chat. In practice, that
process has four recurring pain points:

Requests arrive incomplete — no audience, no deadline, no success measure — and someone
spends a back-and-forth cycle, often days, just extracting a usable brief before any
content gets written. One brief then has to become multiple deliverables (email,
social, an internal post), each drafted separately, often by different people, drifting
off-message from each other along the way. Every draft then goes through brand and
compliance review, which catches the same categories of problems every time — tone,
banned claims, missing disclaimers — a checklist that doesn't need a person to hold it.
And because none of this is instrumented, nobody can say where the process actually
stalls or how often it stalls for the same reasons.

## Future-state workflow

```
Free-text request
      │
      ▼
[1] INTAKE AGENT ──── incomplete? ──→ outputs clarifying questions, STOPS
      │ complete
      ▼  structured brief (JSON)
[2] DRAFTING AGENTS (one per channel: email, social, intranet)
      │
      ▼  channel drafts
[3] REVIEWER AGENT ── fail? ──→ back to drafter with specific edits (max 1 retry loop)
      │ pass (or max retries hit — flagged)
      ▼
[4] HUMAN APPROVAL PACKAGE (markdown file: brief + drafts + review verdicts + flags)
      │
      ▼
[5] RUN LOG (SQLite row per run: timestamps per stage, pass/fail, retry count)
```

Stage 4 is deliberate, not a limitation: this pipeline produces a reviewed package for a
human to approve, and stops there. See Governance below for why.

## Success metrics

| Metric | Definition | Why it matters to the business |
|---|---|---|
| Intake completeness rate | % of test requests where the intake agent correctly identified all missing fields | Measures whether ambiguity is caught at the door instead of mid-production |
| Request-to-package time | Wall-clock seconds from raw request to approval package | The manual equivalent is measured in days |
| First-pass review rate | % of drafts passing brand review without a retry loop | Proxy for how well drafting constraints encode the brand guide |
| Cross-channel consistency | % of multi-channel runs where every channel's final draft carries the key message | The failure mode of splitting drafting across people |

Real numbers, computed from this repo's own run log, are in Results below.

## Approach

**Every agent is a plain `client.messages.create()` call with its own system prompt.**
There's no framework here. The "multi-agent system" is an orchestrator function
(`src/orchestrator.py`, `src/pipeline.py`) calling specialized prompts with structured
handoffs between them. That's a deliberate description, not an understatement — the
value in this project is the handoff design and the governance rules around it, not
model power. The model default is Haiku (`ANTHROPIC_MODEL` env override) for exactly
that reason.

**Intake stops instead of guessing.** The intake agent (`src/intake_agent.py`) extracts
a structured brief from free text, but if the request is missing `objective`,
`audience`, or `key_message`, it calls `ask_clarifying_questions` instead of
`submit_brief` and the pipeline stops for that run. A fabricated brief field is this
workflow's equivalent of a hallucinated citation — worse than asking, because it lets a
wrong brief flow silently into drafting and review, where it will look successful even
though it's wrong.

**The brief is the contract between stages.** Channel drafters (`src/drafting_agents.py`)
receive only the structured brief, never the original raw request. That boundary forces
all ambiguity to be resolved once, at intake, instead of being reinterpreted
inconsistently by three separate drafters working from the same messy text.

**Tool schemas enforce structure, not prose parsing.** Every agent that must return
structured data — intake's brief and clarifying questions, the reviewer's verdict — is
given a single tool whose input schema IS the output format (`src/schemas.py`). This is
the same "prompt the model for what it does reliably, post-process the rest" judgment
that shows up in well-built agent systems generally: tool-use is a reliable path to
valid structured output; asking a model to "please respond in JSON" in a text block is
not.

**Brand knowledge lives in exactly one place.** Drafters never see `brand/brand_guide.md`
— only the reviewer (`src/reviewer_agent.py`) does. This is a deliberate separation, not
an oversight: a drafter that already knew every brand rule by heart could quietly
self-censor a bad key message on its first attempt, which would erase the review/retry
cycle this pipeline is built to demonstrate. Instead, violations are caught downstream
and fed back to the drafter as specific, quoted feedback on retry — the only brand
information a drafter ever sees, and only after a real failure.

**One retry, then flag — never a silent loop, never a silent pass.** The orchestrator
(`src/orchestrator.py`) sends a failed draft back to the same drafter once, with the
reviewer's violations (quoted offending text, which rule, a suggested fix) appended. If
the second attempt still fails, the draft goes into the approval package flagged
`NEEDS HUMAN ATTENTION` with the violations attached. It does not retry again, and it
does not get force-passed.

**No publish step.** The pipeline's last artifact is a markdown approval package, not a
sent email or a live post. That's covered under Governance, because it's a design
decision worth stating on its own.

## Governance & guardrails

This pipeline is built around a human approval gate: the last thing it produces is a
markdown package for a person to read and sign off on, never a live send. Every retry is
bounded — one attempt, then escalation, so a stubborn brief/brand conflict can't loop
forever or get quietly force-passed. Intake is forbidden from fabricating any brief
field; when required information is missing, it asks instead of guessing, and the
pipeline stops rather than proceeding on an invented assumption. The reviewer is
required to quote the exact offending text for every violation it raises, which keeps a
verdict checkable by a human approver instead of a black-box opinion. And nothing in
this system auto-publishes anything, anywhere — the pipeline's job ends at a reviewed
package, not a sent message.

## Results

Computed from this repo's own `run_log.db` (see `scripts/metrics.py`; numbers will
reflect however many times you've run the example suite, since the log is cumulative
history, not a latest-run snapshot):

| Metric | Result |
|---|---|
| Intake completeness rate | 100% (14/14 runs matched expected stop/proceed behavior) |
| Request-to-package time | avg 15.1s (min 2.3s, max 29.4s) |
| First-pass review rate | 64% (14/22 channel drafts passed without a retry) |
| Cross-channel consistency | 100% (8/8 multi-channel runs stated the key message in every channel) |

Six example requests, engineered to cover the realistic range, live under
`example_runs/inputs/`, with their full approval packages in `example_runs/<slug>/`:

1. **Complete, clean request** — happy path, all three channels, everything passes on
   the first attempt.
2. **Vague request** ("we should do something for open enrollment"-style) — intake
   correctly stops and asks clarifying questions instead of guessing; a follow-up run
   with the answers supplied then proceeds to a full brief.
3. **Request that bait-and-switches into a brand violation** — the key message itself is
   clean, but the requested tone leads an unguarded drafter into hype language on its
   own initiative. The reviewer catches it, and the retry passes clean — the
   review/retry loop working as intended.
4. **Single-channel request** — email only; the pipeline correctly skips the other
   drafters rather than defaulting to all three.
5. **Compliance tripwire** — a certification announcement that requires the standard
   disclaimer; the first draft omits it, fails review, and the retry includes it
   verbatim.
6. **Unresolvable conflict** — the brief's required key message itself contains banned
   language that leadership has (in the scenario) already approved verbatim. No
   compliant draft is possible without revising the brief, so the retry still fails and
   the run correctly lands on `NEEDS HUMAN ATTENTION` instead of looping again or
   force-passing.

## What I'd do next

A Tableau throughput dashboard on the run log would be the natural next step — the
table already tracks per-stage and total duration, retry counts, and outcomes, which is
exactly the raw material a dashboard needs. Beyond that: running the three channel
drafters concurrently instead of sequentially (they're independent given the same
brief); a configurable channel set instead of the fixed email/social/intranet three; and
feeding human edits made during approval back into the drafter prompts as a lightweight
feedback loop, so recurring manual fixes stop recurring.

## How to run

```
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
python scripts/run_pipeline_examples.py   # full pipeline, all 6 example requests
python scripts/metrics.py                 # compute the four success metrics
```

Individual stages can also be run and inspected on their own, useful when iterating on
one agent at a time:

```
python scripts/run_intake_examples.py     # intake only
python scripts/run_drafting_examples.py   # intake + drafting, no review
python scripts/run_review_examples.py     # intake + drafting + review/retry, no approval package
```

## Repo structure

```
brand/brand_guide.md        Brand guide the reviewer checks every draft against
docs/brief_schema.md        The structured brief contract between intake and drafting
example_runs/inputs/        The 6 synthetic test requests
example_runs/<slug>/        Generated approval packages (one markdown file per run)
src/client.py               Shared Anthropic client + model default (Haiku)
src/schemas.py               Tool schemas: submit_brief, ask_clarifying_questions, submit_review
src/intake_agent.py          Stage 1: extract a brief, or stop and ask
src/drafting_agents.py       Stage 2: one prompt template, three channel constraint sets
src/reviewer_agent.py        Stage 3: the only agent that sees the brand guide
src/orchestrator.py          Draft → review → one retry → flag, per channel
src/approval_package.py      Stage 4: builds the human-readable markdown package
src/run_log.py               Stage 5: SQLite run log
src/pipeline.py              End-to-end entry point tying all five stages together
scripts/run_pipeline_examples.py   Runs the full pipeline against all 6 example requests
scripts/metrics.py                 Computes the four success metrics from the run log
run_log.db                   Generated SQLite run log (created on first run)
```
