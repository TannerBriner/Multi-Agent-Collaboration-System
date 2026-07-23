# Campaign Brief → Multi-Agent Content Production Pipeline

You paste in a messy, incomplete campaign request, the kind of thing that actually shows
up in an inbox or a Slack channel, and this pipeline turns it into a reviewed,
approval-ready content package across email, social, and an internal post. A human
still has to sign off at the end. It doesn't publish anything on its own; the final
output is a markdown file for a person to read and approve.

**Stack:** Python, the Anthropic Claude API (native tool use, no framework), SQLite for the run log.

---

## Problem

Marketing and comms teams get campaign requests by email or chat, and the process has
the same handful of problems every time. Requests show up incomplete: no audience, no
deadline, no way to measure success. Someone has to go back and forth, sometimes for
days, before there's even a usable brief to hand off. Then that one brief has to become
three or four different deliverables, usually written by different people, and they
drift apart in tone and message without anyone noticing until review. Review itself
catches the same categories of mistake every single time: banned words, missing
disclaimers, tone that's off. None of that actually requires human judgment, it's a
checklist. And because nobody's tracking any of this, there's no way to say where the
process is actually slow or why it keeps stalling in the same places.

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
      │ pass (or max retries hit, flagged)
      ▼
[4] HUMAN APPROVAL PACKAGE (markdown file: brief + drafts + review verdicts + flags)
      │
      ▼
[5] RUN LOG (SQLite row per run: timestamps per stage, pass/fail, retry count)
```

Stopping at a reviewed package instead of publishing anything is on purpose. I get into
why under Governance below.

## Success metrics

| Metric | Definition | Why it matters to the business |
|---|---|---|
| Intake completeness rate | % of test requests where the intake agent correctly identified all missing fields | Measures whether ambiguity is caught at the door instead of mid-production |
| Request-to-package time | Wall-clock seconds from raw request to approval package | The manual equivalent is measured in days |
| First-pass review rate | % of drafts passing brand review without a retry loop | Proxy for how well drafting constraints encode the brand guide |
| Cross-channel consistency | % of multi-channel runs where every channel's final draft carries the key message | The failure mode of splitting drafting across people |

The real numbers, pulled from this repo's own run log, are in Results further down.

## Approach

There's no agent framework anywhere in this codebase. Every stage is just a plain
`client.messages.create()` call with its own system prompt, and an orchestrator function
(`src/orchestrator.py`, `src/pipeline.py`) that passes structured data between them. I'd
rather say that plainly than dress it up, because the interesting part of this project
isn't the model, it's the handoffs between stages and the rules governing what happens
when something fails. That's also why the default model is Haiku: this pipeline doesn't
need a frontier model to prove the pattern works.

Why does intake stop instead of guessing? Because a fabricated brief is worse than an
unanswered question. If the intake agent invents an audience or a deadline that wasn't
in the request, that wrong information flows straight into drafting and review, and
both of those stages will happily process it and produce something that looks
successful. So instead, when `objective`, `audience`, or `key_message` is missing, the
agent calls `ask_clarifying_questions` instead of `submit_brief`, and the run just stops
there until a human answers.

The structured brief is the one thing that crosses between intake and the drafting
stage. Channel drafters never see the original raw request, only the brief. That's a
boundary I set up deliberately: any ambiguity in the original request gets resolved once,
at intake, instead of getting reinterpreted three different ways by three drafters
working off the same messy paragraph.

Getting structured output out of Claude reliably comes down to tool schemas, not asking
nicely for JSON in a text response. Anywhere this pipeline needs structured data back
(the brief itself, clarifying questions, the reviewer's verdict) it's defined as a tool
whose input schema is literally the shape of the data I want. See `src/schemas.py` for
all three.

One choice I went back and forth on: should the drafters also see the brand guide? I
decided no, and only the reviewer (`src/reviewer_agent.py`) gets it. If a drafter already
knew every banned word and every disclaimer rule by heart, it could quietly clean up a
bad key message on the very first attempt, and the retry loop this project is supposed
to demonstrate would basically never fire. Keeping brand knowledge in one place means
violations get caught downstream and handed back to the drafter as specific, quoted
feedback, and that's the only brand information a drafter ever sees, only after it's
actually failed once.

When a draft fails review, the orchestrator sends it back to the same drafter exactly
once, along with the reviewer's quoted violations and suggested fixes. If it still
fails on the second try, it goes into the approval package flagged NEEDS HUMAN
ATTENTION, violations attached. It doesn't try a third time, and it doesn't get passed
through anyway just to move on. I think that rule, more than anything else here, is
what makes this a governed system instead of just a content generator with extra steps.

And finally, nothing publishes. The last thing this pipeline produces is a markdown
file. No email goes out, no post gets scheduled. More on why that's a feature and not a
missing integration in the next section.

## Governance & guardrails

The whole system is built around a human approval gate. Whatever comes out the other
end is a package for a person to read and sign off on, not something that goes live on
its own. Retries are capped at one, so a brief that genuinely conflicts with the brand
guide can't loop forever chasing a pass, or get quietly waved through just because it's
inconvenient to keep failing it. Intake won't fabricate a brief field under any
circumstance; if something required is missing, it asks rather than guessing, and the
whole run pauses instead of continuing on an assumption nobody actually made. The
reviewer has to quote the exact text it's objecting to for every violation, so a human
looking at the approval package can check the reviewer's work instead of just trusting
its judgment. None of this auto-publishes, anywhere, ever. The job of this pipeline ends
at a reviewed package.

## Results

These numbers come straight from this repo's own `run_log.db` (`scripts/metrics.py`
computes them). They'll shift a bit depending on how many times you've run the example
suite yourself, since the log keeps every run rather than just the latest one:

| Metric | Result |
|---|---|
| Intake completeness rate | 100% (14/14 runs matched expected stop/proceed behavior) |
| Request-to-package time | avg 15.1s (min 2.3s, max 29.4s) |
| First-pass review rate | 64% (14/22 channel drafts passed without a retry) |
| Cross-channel consistency | 100% (8/8 multi-channel runs stated the key message in every channel) |

There are six example requests under `example_runs/inputs/`, written to cover a
realistic spread of what actually shows up, with their full approval packages sitting in
`example_runs/<slug>/`.

The first one is the happy path: a complete, clean request across all three channels
where everything passes on the first try. The second is genuinely vague, something like
"we should do something for open enrollment," and intake correctly stops to ask
questions instead of inventing an audience; there's a follow-up run where those
questions get answered and the request goes on to produce a full brief. Request three
looks clean on paper (the key message itself has nothing wrong with it) but the
requested tone pushes an unguarded drafter into hype language it came up with on its
own, and the reviewer catches it. The retry comes back clean, which is the review/retry
loop doing exactly what it's supposed to. Fourth is a single-channel request, email
only, and the pipeline correctly skips the other two drafters rather than defaulting to
all three. Fifth is a compliance tripwire: a certification announcement that needs a
specific disclaimer, which the first draft leaves out, fails review over, and the retry
adds back in word for word. The sixth one is the hard case. The brief's required key
message contains banned language that, in the scenario, leadership has already signed
off on using verbatim. There's no version of a compliant draft that satisfies both the
brand guide and that requirement at the same time, so the retry fails too, and the run
correctly ends up flagged for a human instead of looping again or getting forced
through.

## What I'd do next

If I kept building this, a Tableau dashboard on top of the run log would be the obvious
next step, since the table already has per-stage duration, retry counts, and outcomes
sitting right there waiting to be visualized. Past that, I'd want the three drafters
running concurrently instead of one after another (nothing about them depends on each
other), a channel list that isn't hardcoded to just email, social, and intranet, and
some way of feeding human edits made during approval back into the drafter prompts, so
the same manual fix doesn't need to happen every single time.

## How to run

```
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
python scripts/run_pipeline_examples.py   # full pipeline, all 6 example requests
python scripts/metrics.py                 # compute the four success metrics
```

You can also run each stage on its own, which is useful if you're iterating on a single
agent rather than the whole thing:

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
example_runs/<slug>/        Generated approval packages (one markdown file per run), the actual product
example_runs/dev_test_outputs/   Per-stage raw output (intake/drafting/review) from testing each
                             agent in isolation before wiring up the full pipeline. Evidence
                             of the testing process, not the deliverable itself
src/client.py               Shared Anthropic client + model default (Haiku)
src/schemas.py               Tool schemas: submit_brief, ask_clarifying_questions, submit_review
src/intake_agent.py          Stage 1: extract a brief, or stop and ask
src/drafting_agents.py       Stage 2: one prompt template, three channel constraint sets
src/reviewer_agent.py        Stage 3: the only agent that sees the brand guide
src/orchestrator.py          Draft, review, one retry, then flag if it's still failing
src/approval_package.py      Stage 4: builds the human-readable markdown package
src/run_log.py               Stage 5: SQLite run log
src/pipeline.py              End-to-end entry point tying all five stages together
scripts/run_pipeline_examples.py   Runs the full pipeline against all 6 example requests
scripts/metrics.py                 Computes the four success metrics from the run log
run_log.db                   Generated SQLite run log (created on first run)
```
