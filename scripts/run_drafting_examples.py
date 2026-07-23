"""Day 5-6 test harness: draft every channel for each intake result that produced a
brief (runs that stopped at clarifying questions are skipped -- there's nothing to draft
yet).

Reads example_runs/intake_test_outputs/*.json (produced by run_intake_examples.py) and
writes each channel's draft to example_runs/draft_test_outputs/<slug>/<channel>.txt.

Usage:
    python scripts/run_drafting_examples.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.drafting_agents import draft_channel  # noqa: E402

INTAKE_DIR = ROOT / "example_runs" / "dev_test_outputs" / "intake"
OUTPUT_DIR = ROOT / "example_runs" / "dev_test_outputs" / "drafting"


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
            draft = draft_channel(channel, brief)
            print(f"--- {channel} ---\n{draft}\n")
            (run_dir / f"{channel}.txt").write_text(draft, encoding="utf-8")

    print(f"\nAll drafts written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
