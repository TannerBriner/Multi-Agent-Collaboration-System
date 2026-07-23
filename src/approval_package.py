"""Stage 4: Approval package generation.

One markdown file per run. This file IS the product -- a hiring manager (or, in the
real workflow, a human approver) should be able to read it and understand the whole
run without executing anything. It always contains five things, in order: the raw
request, the structured brief (or the clarifying questions, if intake stopped), every
channel's draft with its full review history, any NEEDS HUMAN ATTENTION flags, and run
metadata (timestamps, retry counts, model).
"""

import json
from pathlib import Path


def write_approval_package(
    output_dir: Path,
    slug: str,
    run_id: str,
    request_text: str,
    intake_result: dict,
    channel_results: list[dict] | None,
    model: str,
    started_at,
    finished_at,
    stage_durations: dict,
) -> Path:
    run_dir = Path(output_dir) / slug
    run_dir.mkdir(parents=True, exist_ok=True)
    package_path = run_dir / "approval_package.md"

    sections = [
        _header(slug, run_id, started_at, finished_at, model),
        _section_request(request_text),
        _section_brief(intake_result),
    ]

    if channel_results is not None:
        sections.append(_section_channels(channel_results))
        sections.append(_section_flags(channel_results))
        sections.append(_section_metadata(channel_results, stage_durations, model))
    else:
        sections.append(
            "## 4. Flags\n\n"
            "Pipeline stopped at intake -- no drafts were produced, so there is "
            "nothing to flag or approve yet. See Section 2 for the questions that "
            "need answering before this run can proceed."
        )
        sections.append(_section_metadata(None, stage_durations, model))

    package_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    return package_path


def _header(slug, run_id, started_at, finished_at, model) -> str:
    return (
        f"# Approval Package -- {slug}\n\n"
        f"- **Run ID:** {run_id}\n"
        f"- **Started:** {started_at.isoformat()}\n"
        f"- **Finished:** {finished_at.isoformat()}\n"
        f"- **Model:** {model}"
    )


def _section_request(request_text: str) -> str:
    quoted = "\n".join(f"> {line}" for line in request_text.splitlines())
    return f"## 1. Original Request (verbatim)\n\n{quoted}"


def _section_brief(intake_result: dict) -> str:
    if intake_result["outcome"] == "questions":
        questions = "\n".join(f"- {q}" for q in intake_result["questions"])
        return (
            "## 2. Structured Brief\n\n"
            "Intake stopped here -- the request was missing information required to "
            "build a brief (objective, audience, and/or key_message), and the intake "
            "agent asked instead of guessing. Questions asked:\n\n"
            f"{questions}"
        )

    brief_json = json.dumps(intake_result["brief"], indent=2)
    return f"## 2. Structured Brief\n\n```json\n{brief_json}\n```"


def _section_channels(channel_results: list[dict]) -> str:
    parts = ["## 3. Channel Drafts & Review"]
    for result in channel_results:
        channel = result["channel"]
        final_review = result["final_review"]
        verdict = final_review["verdict"].upper()
        flag = " -- NEEDS HUMAN ATTENTION" if result["needs_human_attention"] else ""

        parts.append(
            f"### {channel}\n\n"
            f"**Final verdict:** {verdict}{flag}  \n"
            f"**Retried:** {'yes' if result['retried'] else 'no'}  \n"
            f"**Key message present:** {final_review['key_message_present']}\n\n"
            f"**Final draft:**\n\n```\n{result['final_draft']}\n```\n\n"
            f"**Review history:**\n\n{_format_attempts(result['attempts'])}"
        )
    return "\n\n".join(parts)


def _format_attempts(attempts: list[dict]) -> str:
    lines = []
    for i, attempt in enumerate(attempts, start=1):
        review = attempt["review"]
        lines.append(f"- Attempt {i}: **{review['verdict']}**")
        for v in review["violations"]:
            lines.append(
                f"  - Rule: {v['rule']} | Quote: \"{v['quote']}\" | "
                f"Suggested fix: {v['suggested_fix']}"
            )
        if review.get("notes"):
            lines.append(f"  - Note: {review['notes']}")
    return "\n".join(lines)


def _section_flags(channel_results: list[dict]) -> str:
    flagged = [r for r in channel_results if r["needs_human_attention"]]
    if not flagged:
        return "## 4. Flags\n\nNo flags -- every channel passed review within one retry."

    lines = ["## 4. Flags", "", "**NEEDS HUMAN ATTENTION:**", ""]
    for result in flagged:
        last_review = result["attempts"][-1]["review"]
        lines.append(
            f"- **{result['channel']}** -- failed review after 1 retry. "
            "Unresolved violations:"
        )
        for v in last_review["violations"]:
            lines.append(
                f"  - Rule: {v['rule']} | Quote: \"{v['quote']}\" | "
                f"Suggested fix: {v['suggested_fix']}"
            )
    return "\n".join(lines)


def _section_metadata(channel_results: list[dict] | None, stage_durations: dict, model: str) -> str:
    lines = [
        "## 5. Run Metadata",
        "",
        f"- Model: {model}",
        f"- Intake duration: {stage_durations['intake']:.2f}s",
        f"- Total duration: {stage_durations['total']:.2f}s",
    ]
    if channel_results is not None:
        lines.append("- Retry counts:")
        for result in channel_results:
            lines.append(
                f"  - {result['channel']}: "
                f"{'1 (retried)' if result['retried'] else '0'}"
            )
    return "\n".join(lines)
