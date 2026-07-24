"""Day 9 test harness: run the full pipeline (intake -> draft/review/retry -> approval
package -> run log) end to end for all 6 example requests.

This is the same RUNS list as run_intake_examples.py -- run 2 is tested alone (expect
a stop-and-ask approval package) and again with the follow-up appended (expect a full
package with drafts).

Usage:
    python scripts/run_pipeline_examples.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipeline import run_pipeline  # noqa: E402

INPUTS_DIR = ROOT / "example_runs" / "inputs"
OUTPUT_DIR = ROOT / "example_runs"

RUNS = [
    ("01_complete_request", ("01_complete_request.txt",)),
    ("02_vague_request", ("02_vague_request.txt",)),
    ("02_vague_request+02b_vague_followup", ("02_vague_request.txt", "02b_vague_followup.txt")),
    ("03_brand_violation_request", ("03_brand_violation_request.txt",)),
    ("04_single_channel_request", ("04_single_channel_request.txt",)),
    ("05_compliance_tripwire_request", ("05_compliance_tripwire_request.txt",)),
    ("06_repeat_failure_request", ("06_repeat_failure_request.txt",)),
]


def load_thread(*filenames: str) -> str:
    parts = [
        (INPUTS_DIR / name).read_text(encoding="utf-8").strip() for name in filenames
    ]
    return "\n\n---\n\n".join(parts)


def main() -> None:
    for slug, filenames in RUNS:
        request_text = load_thread(*filenames)
        print(f"\n=== {slug} ===")
        result = run_pipeline(request_text, slug, OUTPUT_DIR)

        if result["outcome"] == "questions":
            print(f"  intake stopped -- approval package: {result['package_path']}")

        elif result["outcome"] == "error":
            print(f" error: {result['error']}")

        else:
            summary = ", ".join(
                f"{r['channel']}={r['final_review']['verdict']}"
                f"{'*' if r['needs_human_attention'] else ''}"
                for r in result["channel_results"]
            )
            print(f"  {summary}")
            print(f"  approval package: {result['package_path']}")

    print(f"\nRun log written to {ROOT / 'run_log.db'}")


if __name__ == "__main__":
    main()
