"""The single tracing sink.

One JSON object per line on stdout, which Render captures in its log viewer.
Render's free-tier disk is wiped on restart, so a local SQLite file would
silently lose data — swap the write below (not the call sites) to change sinks.
"""
import json
from datetime import datetime, timezone


def trace(event, **fields):
    """Emit one structured record. Never raises: a trace must not break a request."""
    record = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
              "event": event, **fields}
    print(json.dumps(record, default=repr), flush=True)
