"""Stage 5: Run log.

One SQLite row per pipeline run. This is deliberately a single denormalized table --
scope for this project is a run log a hiring manager can query in one sitting, not a
production analytics schema. Per-channel detail (verdicts, retries, key-message
presence) is stored as JSON columns rather than a separate child table; scripts/
metrics.py reads and unpacks them to compute the four success metrics.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "run_log.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    started_at TEXT NOT NULL,
    model TEXT NOT NULL,
    intake_outcome TEXT NOT NULL,          -- 'brief' | 'questions'
    channels TEXT,                          -- JSON list, null if intake_outcome='questions'
    first_pass_verdicts TEXT,               -- JSON {channel: "pass"|"fail"}
    final_verdicts TEXT,                    -- JSON {channel: "pass"|"fail"}
    key_message_present TEXT,               -- JSON {channel: bool}
    retry_counts TEXT,                      -- JSON {channel: 0|1}
    needs_human_attention TEXT,             -- JSON {channel: bool}
    intake_duration_seconds REAL NOT NULL,
    total_duration_seconds REAL NOT NULL
);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def log_run(
    run_id: str,
    slug: str,
    started_at,
    model: str,
    intake_outcome: str,
    channel_results: list[dict] | None,
    intake_duration: float,
    total_duration: float,
    db_path: Path = DB_PATH,
) -> None:
    if channel_results is None:
        channels = None
        first_pass_verdicts = None
        final_verdicts = None
        key_message_present = None
        retry_counts = None
        needs_human_attention = None
    else:
        channels = json.dumps([r["channel"] for r in channel_results])
        first_pass_verdicts = json.dumps(
            {r["channel"]: r["attempts"][0]["review"]["verdict"] for r in channel_results}
        )
        final_verdicts = json.dumps(
            {r["channel"]: r["final_review"]["verdict"] for r in channel_results}
        )
        key_message_present = json.dumps(
            {r["channel"]: r["final_review"]["key_message_present"] for r in channel_results}
        )
        retry_counts = json.dumps(
            {r["channel"]: (1 if r["retried"] else 0) for r in channel_results}
        )
        needs_human_attention = json.dumps(
            {r["channel"]: r["needs_human_attention"] for r in channel_results}
        )

    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs (
                run_id, slug, started_at, model, intake_outcome, channels,
                first_pass_verdicts, final_verdicts, key_message_present,
                retry_counts, needs_human_attention,
                intake_duration_seconds, total_duration_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                slug,
                started_at.isoformat(),
                model,
                intake_outcome,
                channels,
                first_pass_verdicts,
                final_verdicts,
                key_message_present,
                retry_counts,
                needs_human_attention,
                intake_duration,
                total_duration,
            ),
        )
    conn.close()
