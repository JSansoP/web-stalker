"""
SQLite-backed job store.

Database file lives at  data/jobs.db  (relative to the project root).
The directory is created automatically on first access.
"""

import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"

class JobType(str, Enum):
    SCREENSHOT = "screenshot"
    TEXT = "text"

class ConditionType(str, Enum):
    CONTAINS = "contains"
    DOESNT_CONTAIN = "doesnt_contain"

@dataclass
class Job:
    id: int
    name: str
    url: str
    cron: str
    chat_id: str
    job_type: JobType
    selector: str | None
    condition_type: ConditionType | None
    condition_value: str | None
    enabled: bool
    last_run: str | None
    full_page: bool = False
    timeout: int = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        name=row["name"],
        url=row["url"],
        cron=row["cron"],
        chat_id=row["chat_id"],
        job_type=JobType(row["job_type"]) if "job_type" in row.keys() else JobType.SCREENSHOT,
        selector=row["selector"] if "selector" in row.keys() else None,
        condition_type=ConditionType(row["condition_type"]) if ("condition_type" in row.keys() and row["condition_type"]) else None,
        condition_value=row["condition_value"] if "condition_value" in row.keys() else None,
        enabled=bool(row["enabled"]),
        last_run=row["last_run"],
        full_page=bool(row["full_page"]) if "full_page" in row.keys() else False,
        timeout=row["timeout"] if "timeout" in row.keys() else 10,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create the jobs table if it doesn't exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT    NOT NULL,
                url      TEXT    NOT NULL,
                cron     TEXT    NOT NULL,
                chat_id  TEXT    NOT NULL,
                job_type TEXT    NOT NULL DEFAULT 'screenshot',
                selector TEXT,
                condition_type TEXT,
                condition_value TEXT,
                enabled  INTEGER NOT NULL DEFAULT 1,
                last_run TEXT,
                full_page INTEGER NOT NULL DEFAULT 0,
                timeout INTEGER NOT NULL DEFAULT 10
            )
            """
        )
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN timeout INTEGER NOT NULL DEFAULT 10")
        except sqlite3.OperationalError:
            pass

def add_job(
    name: str, 
    url: str, 
    cron: str, 
    chat_id: str, 
    job_type: JobType = JobType.SCREENSHOT,
    selector: str | None = None,
    condition_type: ConditionType | None = None,
    condition_value: str | None = None,
    full_page: bool = False,
    timeout: int = 10
) -> int:
    """Insert a new job and return its auto-assigned ID."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (name, url, cron, chat_id, job_type, selector, condition_type, condition_value, full_page, timeout) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name, 
                url, 
                cron, 
                chat_id, 
                job_type.value, 
                selector, 
                condition_type.value if condition_type else None,
                condition_value,
                int(full_page),
                timeout
            ),
        )
        return cur.lastrowid  # type: ignore[return-value]


def get_jobs() -> list[Job]:
    """Return all jobs ordered by ID."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY id").fetchall()
    return [_row_to_job(r) for r in rows]


def get_job(job_id: int) -> Job | None:
    """Return a single job by ID, or None if not found."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def delete_job(job_id: int) -> bool:
    """Delete a job. Returns True if a row was actually removed."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return cur.rowcount > 0


def update_last_run(job_id: int, timestamp: str) -> None:
    """Record the ISO-8601 UTC timestamp of the most recent successful run."""
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET last_run = ? WHERE id = ?",
            (timestamp, job_id),
        )


def update_job(
    job_id: int,
    name: str | None = None,
    url: str | None = None,
    cron: str | None = None,
    chat_id: str | None = None,
    job_type: JobType | None = None,
    selector: str | None = None,
    condition_type: ConditionType | None = None,
    condition_value: str | None = None,
    full_page: bool | None = None,
    timeout: int | None = None,
    clear_conditions: bool = False,
) -> bool:
    """Update job fields dynamically. Returns True if the job was found and updated."""
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if url is not None:
        updates.append("url = ?")
        params.append(url)
    if cron is not None:
        updates.append("cron = ?")
        params.append(cron)
    if chat_id is not None:
        updates.append("chat_id = ?")
        params.append(chat_id)
    if job_type is not None:
        updates.append("job_type = ?")
        params.append(job_type.value)
    if selector is not None:
        updates.append("selector = ?")
        params.append(selector)
    if condition_type is not None:
        updates.append("condition_type = ?")
        params.append(condition_type.value)
    elif clear_conditions:
        updates.append("condition_type = NULL")
    if condition_value is not None:
        updates.append("condition_value = ?")
        params.append(condition_value)
    elif clear_conditions:
        updates.append("condition_value = NULL")
    if full_page is not None:
        updates.append("full_page = ?")
        params.append(int(full_page))
    if timeout is not None:
        updates.append("timeout = ?")
        params.append(timeout)

    if not updates:
        return False

    params.append(job_id)
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        return cur.rowcount > 0


def toggle_job(job_id: int, enabled: bool) -> bool:
    """Enable or disable a job. Returns True if the job was found and updated."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE jobs SET enabled = ? WHERE id = ?",
            (int(enabled), job_id),
        )
        return cur.rowcount > 0
