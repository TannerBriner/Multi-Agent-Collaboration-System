"""Orchestrator: ties drafting and review together with the retry/flag rule.

This is the governance core of the pipeline: one retry maximum, never a silent loop,
never a silent pass. If a draft fails review, the orchestrator sends it back to the
SAME drafter with the reviewer's violations (quoted text + rule + suggested fix)
appended. If the redraft still fails, the draft goes into the approval package flagged
NEEDS HUMAN ATTENTION with the violations attached -- it does not retry again, and it
does not get force-passed.
"""

from src.drafting_agents import draft_channel
from src.reviewer_agent import run_review

MAX_RETRIES = 1


def produce_channel_content(channel: str, brief: dict) -> dict:
    """Draft, review, and (if needed) retry once for a single channel.

    Returns:
        {
            "channel": str,
            "final_draft": str,
            "final_review": {...submit_review output...},
            "retried": bool,
            "needs_human_attention": bool,
            "attempts": [{"draft": str, "review": {...}}, ...],  # 1 or 2 entries
        }
    """
    draft = draft_channel(channel, brief)
    review = run_review(draft, brief)
    attempts = [{"draft": draft, "review": review}]

    retried = False
    if review["verdict"] == "fail":
        retried = True
        feedback = _format_feedback(review)
        draft = draft_channel(channel, brief, revision_feedback=feedback)
        review = run_review(draft, brief)
        attempts.append({"draft": draft, "review": review})

    return {
        "channel": channel,
        "final_draft": draft,
        "final_review": review,
        "retried": retried,
        "needs_human_attention": review["verdict"] == "fail",
        "attempts": attempts,
    }


def produce_all_channels(brief: dict) -> list[dict]:
    """Draft + review (+ retry) every channel listed in the brief, sequentially."""
    return [produce_channel_content(channel, brief) for channel in brief["channels"]]


def _format_feedback(review: dict) -> str:
    lines = []
    for v in review["violations"]:
        lines.append(
            f'- Rule: {v["rule"]}\n'
            f'  Offending text: "{v["quote"]}"\n'
            f'  Suggested fix: {v["suggested_fix"]}'
        )
    if review.get("notes"):
        lines.append(f"- Note: {review['notes']}")
    return "\n".join(lines) if lines else "The reviewer marked this as a failure but gave no specific violations."
