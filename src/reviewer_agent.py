"""Stage 3: Reviewer agent.

The reviewer is the only agent that sees the brand guide. That's a deliberate design
choice (see src/drafting_agents.py's module docstring): brand knowledge lives in one
place, so review verdicts are consistent and the retry loop is meaningful instead of
redundant.

The reviewer is given one draft, the brief it was drafted from, and the brand guide,
and must call submit_review exactly once. Violations must quote the offending text
verbatim -- that's what makes a verdict checkable by a human approver instead of a
vibe.
"""

import json
from pathlib import Path

from src.client import get_client, get_model
from src.schemas import SUBMIT_REVIEW_TOOL

BRAND_GUIDE_PATH = Path(__file__).resolve().parent.parent / "brand" / "brand_guide.md"
BRAND_GUIDE_TEXT = BRAND_GUIDE_PATH.read_text(encoding="utf-8")

SYSTEM_PROMPT = f"""You are the brand and compliance reviewer for Northbridge's \
campaign content pipeline.

You will be given a structured campaign brief and ONE channel draft produced from it.
Review the draft against the brand guide below and decide pass or fail. You are the
only agent in this pipeline that sees the brand guide -- drafters do not see it, so
don't assume the draft was written with these rules in mind.

BRAND GUIDE:
{BRAND_GUIDE_TEXT}

Rules for your review:
- verdict is "fail" if the draft breaks ANY rule in the brand guide above, or if it
  does not communicate the brief's key_message in substance.
- key_message_present is true only if the draft's core message matches the brief's
  key_message in substance. Near-verbatim wording is fine; a different point entirely
  is not.
- For every violation, quote the EXACT offending text from the draft, verbatim -- not
  a paraphrase or summary of what's wrong. Name which brand guide rule it breaks, and
  give a specific, actionable suggested fix.
- Do not invent violations that aren't there, and do not soften or excuse a real
  violation to make a draft pass.
- If the draft is genuinely clean, verdict is "pass", violations is an empty list, and
  notes can be null.

Call submit_review exactly once.
"""


def run_review(draft: str, brief: dict) -> dict:
    """Review a single channel draft against the brief and brand guide.

    Returns the submit_review tool input directly:
      {"verdict": "pass"|"fail", "key_message_present": bool, "violations": [...], "notes": ...}
    """
    client = get_client()

    user_content = (
        f"Brief:\n{_format_brief(brief)}\n\n"
        f"Draft to review:\n{draft}"
    )

    response = client.messages.create(
        model=get_model(),
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[SUBMIT_REVIEW_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": user_content}],
    )

    tool_calls = [block for block in response.content if block.type == "tool_use"]
    if not tool_calls:
        raise RuntimeError("Reviewer agent responded without calling submit_review.")

    return tool_calls[0].input


def _format_brief(brief: dict) -> str:
    return json.dumps(brief, indent=2)
