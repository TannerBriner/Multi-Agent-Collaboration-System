"""Day 10: read the run log and compute the four success metrics defined in the
README's Results section.

Ground truth for "intake completeness rate" is hardcoded against this project's known
6 test requests (7 runs, counting the vague request's before/after) -- this is a
portfolio-scale evaluation against a curated example set, not a claim about intake
accuracy on arbitrary unseen requests. See docs/brief_schema.md for why stopping to
ask is the correct behavior for an incomplete request.

Usage:
    python scripts/metrics.py
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.run_log import DB_PATH  # noqa: E402

# slug -> expected intake outcome for this project's known test requests.
EXPECTED_INTAKE_OUTCOME = {
    "01_complete_request": "brief",
    "02_vague_request": "questions",
    "02_vague_request+02b_vague_followup": "brief",
    "03_brand_violation_request": "brief",
    "04_single_channel_request": "brief",
    "05_compliance_tripwire_request": "brief",
    "06_repeat_failure_request": "brief",
}


def load_runs(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.execute("SELECT * FROM runs")]
    conn.close()
    return rows


def intake_completeness_rate(runs: list[dict]) -> tuple[float, int, int]:
    checked = [r for r in runs if r["slug"] in EXPECTED_INTAKE_OUTCOME]
    correct = sum(
        1 for r in checked if r["intake_outcome"] == EXPECTED_INTAKE_OUTCOME[r["slug"]]
    )
    total = len(checked)
    return (correct / total if total else 0.0), correct, total


def request_to_package_time(runs: list[dict]) -> tuple[float, float, float]:
    durations = [r["total_duration_seconds"] for r in runs]
    return (
        sum(durations) / len(durations) if durations else 0.0,
        min(durations) if durations else 0.0,
        max(durations) if durations else 0.0,
    )


def first_pass_review_rate(runs: list[dict]) -> tuple[float, int, int]:
    total = 0
    first_pass = 0
    for r in runs:
        if not r["retry_counts"]:
            continue
        retry_counts = json.loads(r["retry_counts"])
        for channel, retried in retry_counts.items():
            total += 1
            if retried == 0:
                first_pass += 1
    return (first_pass / total if total else 0.0), first_pass, total


def cross_channel_consistency(runs: list[dict]) -> tuple[float, int, int]:
    multi_channel_runs = [
        r for r in runs if r["key_message_present"] and len(json.loads(r["channels"])) > 1
    ]
    consistent = 0
    for r in multi_channel_runs:
        present = json.loads(r["key_message_present"]).values()
        if all(present):
            consistent += 1
    total = len(multi_channel_runs)
    return (consistent / total if total else 0.0), consistent, total


def main() -> None:
    if not DB_PATH.exists():
        print(f"No run log found at {DB_PATH}. Run scripts/run_pipeline_examples.py first.")
        return

    runs = load_runs(DB_PATH)

    completeness_pct, completeness_n, completeness_total = intake_completeness_rate(runs)
    avg_time, min_time, max_time = request_to_package_time(runs)
    first_pass_pct, first_pass_n, first_pass_total = first_pass_review_rate(runs)
    consistency_pct, consistency_n, consistency_total = cross_channel_consistency(runs)

    lines = [
        "# Success Metrics",
        "",
        f"Computed from {len(runs)} runs in {DB_PATH.name}.",
        "",
        "| Metric | Result |",
        "|---|---|",
        (
            "| Intake completeness rate | "
            f"{completeness_pct:.0%} ({completeness_n}/{completeness_total} runs "
            "matched expected stop/proceed behavior) |"
        ),
        (
            "| Request-to-package time | "
            f"avg {avg_time:.1f}s (min {min_time:.1f}s, max {max_time:.1f}s) |"
        ),
        (
            "| First-pass review rate | "
            f"{first_pass_pct:.0%} ({first_pass_n}/{first_pass_total} channel drafts "
            "passed without a retry) |"
        ),
        (
            "| Cross-channel consistency | "
            f"{consistency_pct:.0%} ({consistency_n}/{consistency_total} multi-channel "
            "runs stated the key message in every channel) |"
        ),
    ]
    output = "\n".join(lines)

    print(output)

    summary_path = ROOT / "example_runs" / "metrics_summary.md"
    summary_path.write_text(output + "\n", encoding="utf-8")
    print(f"\nWritten to {summary_path}")


if __name__ == "__main__":
    main()
