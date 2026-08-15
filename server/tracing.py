"""The stdout tracing sink.

One JSON object per line, which Render captures in its log viewer.

There are now TWO sinks for a turn: this one and the SQLite table in
trace_store.py. That duplication is deliberate, not an oversight — Render's
free tier wipes the disk on redeploy, so the log stream is what survives when
the database does not. Do not "clean up" one of them without replacing the
durability it provides.
"""
import json
from datetime import datetime, timezone


def trace(event, **fields):
    """Emit one structured record. Never raises: a trace must not break a request."""
    try:
        record = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                  "event": event, **fields}
        print(json.dumps(record, default=repr), flush=True)
    except Exception:
        # A trace must never break a request. Silently ignore any error
        # (json serialization, repr raising, print to broken stdout, etc).
        pass
