#!/usr/bin/env python3
"""
recorder.py — what the agent DID, as it happens.

The loop in agent.py already leaves tool names, arguments and results behind in
its message list. What it cannot leave behind is TIME: nothing in a message says
how long a BTS fetch took, or how much of a slow turn was the model thinking.
That has to be observed while the loop runs, which is what this file is for.

Injected, never imported, by agent.py: the default is NULL, so the CLI and the
REPL carry no tracing at all and backend/ keeps running with no server, no
database and no configuration.
"""
import time
from contextlib import contextmanager


class Step:
    """One recorded step. `data` is the dict that lands in Recorder.steps."""

    def __init__(self, kind, round_, **fields):
        self.data = {"kind": kind, "round": round_, **fields}

    def set(self, **fields):
        """Add what is only known once the block has run — a result, an error."""
        self.data.update(fields)


class Recorder:
    """Accumulates steps for one turn. Construct one per /chat request."""

    def __init__(self):
        self.steps = []
        self.round = 0

    def start_round(self):
        self.round += 1

    @contextmanager
    def step(self, kind, **fields):
        """Time one block and record it.

        The append sits in `finally`, so a step whose block RAISED is still
        recorded. That is deliberate: a turn that dies mid-flight is exactly the
        one worth having a trace of, and it is what lets server/app.py write a
        partial record from its exception handler.

        The block's own exception is never swallowed — it propagates to the
        loop's existing handling. Only the recorder's own bookkeeping is
        guarded, because a trace must not break a request.
        """
        step = Step(kind, self.round, **fields)
        started = time.monotonic()
        try:
            yield step
        finally:
            try:
                step.data["ms"] = int((time.monotonic() - started) * 1000)
                self.steps.append(step.data)
            except Exception:
                pass


class _Null:
    """Same interface, no memory. The default, so tracing is opt-in."""

    steps = ()
    round = 0

    def start_round(self):
        pass

    @contextmanager
    def step(self, kind, **fields):
        yield Step(kind, 0)


NULL = _Null()
