"""Stage 2: Channel drafting agents.

One system prompt per channel, built from a shared template with hard per-channel
constraints layered in. Each drafter receives ONLY the structured brief -- never the
original raw request, and (deliberately) never the brand guide either. The brief is the
contract between intake and drafting; brand knowledge lives in exactly one place, the
reviewer. That separation is what makes the retry loop meaningful: a drafter that
already knew every brand rule by heart could quietly self-censor a bad key_message on
its first attempt, which would erase the review/retry cycle these test runs are built to
demonstrate. Instead, violations are caught downstream and fed back as specific,
quoted feedback -- the same "prompt for what the model does reliably, post-process the
rest" judgment used elsewhere in this pipeline.
"""

import json

from src.client import get_client, get_model

CHANNEL_INSTRUCTIONS = {
    "email": """Format your draft exactly as:

Subject: <subject line>
Preview text: <preview/preheader text>

Body:
<body copy, about 150 words>

CTA: <single clear call to action>

Constraints: subject + preview text + ~150-word body + exactly one CTA. Keep it
scannable -- short paragraphs, no walls of text.""",
    "social": """Write a single social post as plain text, under these constraints:
- 280 characters maximum, including spaces and punctuation
- At most 2 hashtags total
- No link-bait phrasing (e.g. "you won't believe," "this one trick," "wait until you see")
Return only the post text, nothing else.""",
    "intranet": """Format your draft exactly as:

Headline: <headline>

Body:
<body copy, about 250 words>

This is for Northbridge employees, not customers or prospects -- informational tone, no
marketing hype, no CTA needed.""",
}

SYSTEM_PROMPT_TEMPLATE = """You are the {channel} drafter for Northbridge's campaign \
content pipeline.

You are given ONLY the structured campaign brief below -- never the original raw \
request. Treat the brief as a contract, not a starting point to improve on: don't add \
detail, claims, or framing the brief doesn't support.

Your draft MUST state the brief's key_message verbatim or very close to verbatim. This \
is checked downstream -- drifting from the key message is treated as a failure even if \
the copy is otherwise well-written.

Never invent a specific number, duration, date, or statistic that isn't in the brief \
(trial lengths, percentages, counts of anything, dollar amounts, etc.). If the brief \
doesn't give you a number, don't add one -- write around it instead of guessing. A \
fabricated figure is worse than vaguer copy, because it can silently contradict what \
another channel's drafter -- working from the same brief, independently -- writes.

{channel_instructions}

Even if the brief and the revision feedback pull in different directions (for example, a brief that requires exact wording containing something the brand guide bans), you must still produce your best-effort draft copy. Never refuse to draft, and never write meta-commentary, caveats, or escalation notes in place of copy -- that decision belongs to the reviewer and the human approver downstream, not to you. If you truly cannot satisfy both, prioritize the brief's key_message and constraints exactly as given, and let the reviewer flag whatever conflict results.

Return only the draft itself -- no preamble, no meta-commentary about your choices.
"""


def _build_system_prompt(channel: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        channel=channel, channel_instructions=CHANNEL_INSTRUCTIONS[channel]
    )


def draft_channel(channel: str, brief: dict, revision_feedback: str | None = None) -> str:
    """Produce (or revise) a single channel's draft from the brief.

    revision_feedback, when present, is the reviewer's violations list from a failed
    first pass -- this is the ONLY brand information a drafter ever sees, and only after
    a failure. See module docstring for why.
    """
    client = get_client()

    user_content = "Brief:\n" + json.dumps(brief, indent=2)
    if revision_feedback:
        user_content += (
            "\n\nYour previous draft failed brand review. Revise it to address the "
            "following, while still honoring the brief above (including its "
            "key_message and constraints):\n" + revision_feedback
        )

    response = client.messages.create(
        model=get_model(),
        max_tokens=1024,
        system=_build_system_prompt(channel),
        messages=[{"role": "user", "content": user_content}],
    )

    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()


def draft_all_channels(brief: dict) -> dict:
    """Draft every channel listed in the brief. Sequential calls -- see README for why
    concurrency is scoped out as a 'what I'd do next' rather than built now."""
    return {channel: draft_channel(channel, brief) for channel in brief["channels"]}
