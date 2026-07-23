"""Day 7-8 test harness: draft + review (+ retry if needed) every channel for each
intake result that produced a brief.

Reads example_runs/intake_test_outputs/*.json and writes, per run, one JSON file per
channel to example_runs/review_test_outputs/<slug>/<channel>.json containing every
attempt (1 or 2), the final verdict, and whether it needs human attention.

Usage:
    python scripts/run_review_examples.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.orchestrator import produce_channel_content  # noqa: E402

INTAKE_DIR = ROOT / "example_runs" / "dev_test_outputs" / "intake"
OUTPUT_DIR = ROOT / "example_runs" / "dev_test_outputs" / "review"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for path in sorted(INTAKE_DIR.glob("*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))

        if result.get("outcome") != "brief":
            print(f"skip {path.stem} (intake asked clarifying questions, no brief)")
            continue

        brief = result["brief"]
        run_dir = OUTPUT_DIR / path.stem
        run_dir.mkdir(exist_ok=True)

        print(f"\n=== {path.stem} ({', '.join(brief['channels'])}) ===")
        for channel in brief["channels"]:
            outcome = produce_channel_content(channel, brief)
            verdict = outcome["final_review"]["verdict"]
            flag = " -- NEEDS HUMAN ATTENTION" if outcome["needs_human_attention"] else ""
            print(
                f"--- {channel}: {verdict} "
                f"(retried={outcome['retried']}){flag} ---"
            )
            (run_dir / f"{channel}.json").write_text(
                json.dumps(outcome, indent=2), encoding="utf-8"
            )

    print(f"\nAll results written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
