"""Day 3-4 test harness: run the intake agent against all 6 example requests.

Run 2 (vague) is tested twice: once alone (expect ask_clarifying_questions), and once
with the follow-up answers appended (expect submit_brief) -- simulating the two-message
thread described in the build spec.

Usage:
    python scripts/run_intake_examples.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.intake_agent import run_intake  # noqa: E402

INPUTS_DIR = ROOT / "example_runs" / "inputs"
OUTPUT_DIR = ROOT / "example_runs" / "dev_test_outputs" / "intake"

# Each tuple is one intake run; multiple filenames simulate a multi-message thread.
RUNS = [
    ("01_complete_request.txt",),
    ("02_vague_request.txt",),
    ("02_vague_request.txt", "02b_vague_followup.txt"),
    ("03_brand_violation_request.txt",),
    ("04_single_channel_request.txt",),
    ("05_compliance_tripwire_request.txt",),
    ("06_repeat_failure_request.txt",),
]


def load_thread(*filenames: str) -> str:
    parts = [
        (INPUTS_DIR / name).read_text(encoding="utf-8").strip() for name in filenames
    ]
    return "\n\n---\n\n".join(parts)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for filenames in RUNS:
        slug = "+".join(name.removesuffix(".txt") for name in filenames)
        request_text = load_thread(*filenames)

        print(f"\n=== {slug} ===")
        result = run_intake(request_text)
        print(json.dumps(result, indent=2))

        out_path = OUTPUT_DIR / f"{slug}.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"\nAll results written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
