"""End-to-end pipeline: intake -> (stop, if incomplete) or draft+review+retry per
channel -> approval package + run log row.

This is the single entry point used by scripts/run_pipeline_examples.py and
is what a real trigger (a cron job, an inbox watcher, a Slack command) would call.
"""

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.approval_package import write_approval_package
from src.client import get_model
from src.intake_agent import run_intake
from src.orchestrator import produce_channel_content
from src.run_log import log_run


def run_pipeline(request_text: str, slug: str, output_dir: Path) -> dict:
    run_id = uuid.uuid4().hex[:8]
    model = get_model()
    started_at = datetime.now(timezone.utc)

    pipeline_clock_start = time.monotonic()
    try:
        intake_result = run_intake(request_text)
        intake_duration = time.monotonic() - pipeline_clock_start
        if intake_result["outcome"] == "questions":
            finished_at = datetime.now(timezone.utc)
            total_duration = time.monotonic() - pipeline_clock_start

            package_path = write_approval_package(
                output_dir=output_dir,
                slug=slug,
                run_id=run_id,
                request_text=request_text,
                intake_result=intake_result,
                channel_results=None,
                model=model,
                started_at=started_at,
                finished_at=finished_at,
                stage_durations={"intake": intake_duration, "total": total_duration},
            )
            log_run(
                run_id=run_id,
                slug=slug,
                started_at=started_at,
                model=model,
                status="success",
                error_detail="none",
                intake_outcome="questions",
                channel_results=None,
                intake_duration=intake_duration,
                total_duration=total_duration,
            )
            return {
                "run_id": run_id,
                "outcome": "questions",
                "questions": intake_result["questions"],
                "package_path": str(package_path),
            }

        brief = intake_result["brief"]
        channel_results = []
        for channel in brief["channels"]:
            channel_clock_start = time.monotonic()
            result = produce_channel_content(channel, brief)
            result["duration_seconds"] = round(time.monotonic() - channel_clock_start, 2)
            channel_results.append(result)

        finished_at = datetime.now(timezone.utc)
        total_duration = time.monotonic() - pipeline_clock_start

        package_path = write_approval_package(
            output_dir=output_dir,
            slug=slug,
            run_id=run_id,
            request_text=request_text,
            intake_result=intake_result,
            channel_results=channel_results,
            model=model,
            started_at=started_at,
            finished_at=finished_at,
            stage_durations={"intake": intake_duration, "total": total_duration},
        )
        log_run(
            run_id=run_id,
            slug=slug,
            started_at=started_at,
            model=model,
            status="success",
            error_detail="none",
            intake_outcome="brief",
            channel_results=channel_results,
            intake_duration=intake_duration,
            total_duration=total_duration,
        )

        return {
            "run_id": run_id,
            "outcome": "brief",
            "package_path": str(package_path),
            "channel_results": channel_results,
        }
    
    except Exception as e:

        total_duration = time.monotonic() - pipeline_clock_start
        error_message = str(e)
        log_run(
            run_id=run_id,
            slug=slug,
            started_at=started_at,
            model=model,
            status="error",
            error_detail=error_message,
            intake_outcome="error",
            channel_results=None,
            intake_duration=total_duration,
            total_duration=total_duration,
        )
        return {
            "run_id": run_id,
            "outcome": 'error',
            "error": error_message,

        }