"""One capped SQLite table of turns — the durable half of tracing.

Best-effort by contract. Every function here swallows its own failures and
falls back to the stdout sink in tracing.py: a trace that cannot be stored is a
missing row, never a failed request.

Steps are stored as a JSON blob rather than a child table. Nothing in scope
aggregates across steps — both UI surfaces load one whole trace and render it —
so a second table would buy a join and a migration and nothing else.
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from server.tracing import trace

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
  id TEXT PRIMARY KEY, ts TEXT NOT NULL, model TEXT,
  question TEXT, answer TEXT, latency_ms INTEGER, error TEXT,
  step_count INTEGER NOT NULL DEFAULT 0, steps TEXT NOT NULL
)
"""

# No secondary index: every read is newest-first, which is a reverse scan of the
# implicit rowid — already ordered — over a table capped at a few thousand rows.
#
# step_count is denormalised on purpose. The list view needs it, and the whole
# point of leaving `steps` out of the summary query is to avoid dragging every
# BTS payload across the wire — recomputing the count would read them all back.
COLUMNS = ("id", "ts", "model", "question", "answer", "latency_ms", "error",
           "step_count", "steps")
SUMMARY = ("id", "ts", "model", "question", "answer", "latency_ms", "error",
           "step_count")


def db_path(path=None):
    """Resolved per call, not at import: tests and Render both set it late."""
    return path or os.environ.get("TRACE_DB", "traces.db")


def max_rows():
    try:
        return int(os.environ.get("TRACE_MAX_ROWS", "2000"))
    except ValueError:
        return 2000


def connect(path=None):
    connection = sqlite3.connect(db_path(path))
    # WAL plus a busy timeout is what keeps concurrent uvicorn workers from
    # tripping over SQLite's database-level write lock.
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute(SCHEMA)
    return connection


def make_record(question, answer, model, steps, latency_ms, error=None):
    """One turn, in the shape both the wire and the table use."""
    return {"id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "model": model,
            "question": question,
            "answer": answer,
            "latency_ms": latency_ms,
            "error": error,
            "steps": steps}


def write(record, path=None):
    """Insert one turn and enforce the row cap. Never raises."""
    try:
        steps = record.get("steps") or []
        with connect(path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record["id"], record["ts"], record.get("model"),
                 record.get("question"), record.get("answer"),
                 record.get("latency_ms"), record.get("error"),
                 len(steps), json.dumps(steps, default=repr)))
            # Ordered by rowid, NOT ts: timestamps can collide at millisecond
            # resolution and rowids cannot. Doubles as the retention policy —
            # the server now remembers every question anyone asks.
            connection.execute(
                "DELETE FROM traces WHERE rowid NOT IN "
                "(SELECT rowid FROM traces ORDER BY rowid DESC LIMIT ?)",
                (max_rows(),))
    except Exception as e:
        trace("trace_write_failed", error=f"{type(e).__name__}: {e}")


def recent(limit=50, offset=0, path=None):
    """Summaries, newest first. No steps column: the list view must not drag
    every BTS payload across the wire."""
    try:
        with connect(path) as connection:
            rows = connection.execute(
                f"SELECT {', '.join(SUMMARY)} FROM traces "
                "ORDER BY rowid DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    except Exception as e:
        trace("trace_read_failed", error=f"{type(e).__name__}: {e}")
        return []
    return [dict(zip(SUMMARY, row)) for row in rows]


def get(trace_id, path=None):
    """One full turn, steps parsed back into a list. None if unknown."""
    try:
        with connect(path) as connection:
            row = connection.execute(
                f"SELECT {', '.join(COLUMNS)} FROM traces WHERE id = ?",
                (trace_id,)).fetchone()
    except Exception as e:
        trace("trace_read_failed", error=f"{type(e).__name__}: {e}")
        return None
    if row is None:
        return None
    record = dict(zip(COLUMNS, row))
    try:
        record["steps"] = json.loads(record["steps"])
    except (ValueError, TypeError):
        record["steps"] = []
    return record
