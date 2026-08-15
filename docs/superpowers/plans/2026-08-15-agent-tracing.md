# Agent Tracing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture what the agent did on every turn — tools, arguments, results, per-step timings — persist it to SQLite, and show it inline under each answer plus on a token-gated debug page.

**Architecture:** A null-object `Recorder` is injected into `backend/agent.py` and times three seams in the loop (round boundaries, model calls, tool dispatches). `server/app.py` holds the recorder, builds one record per turn, ships it in the `/chat` response, and writes it to a capped SQLite table. The React app renders that record inline via a collapsed `<details>` disclosure, and a hash-routed `/#traces` page reads past turns back through a key-gated `/api/traces`.

**Tech Stack:** Python 3 / FastAPI / stdlib `sqlite3` (no new backend dependency); React 18 + Vite + Vitest (no new frontend dependency).

**Spec:** `docs/superpowers/specs/2026-08-15-agent-tracing-design.md`

## Global Constraints

- **No new dependencies.** Backend uses stdlib `sqlite3`; frontend adds no package. Do not add a router library — the debug page is a hash route for the reason given in Task 11.
- **A trace must never break a request.** Every recorder and store operation swallows its own exceptions, matching the rule already set in `server/tracing.py:19`.
- **`backend/` must still run standalone.** No server import, no DB, no env var may become required for `python3 agent.py`. The `NULL` recorder default is what guarantees this, and Task 2 tests it.
- **The trace must never enter `llmHistory`.** That ref is replayed to the server every turn (`frontend/src/hooks/useChat.js:27`); a trace inside it would be re-uploaded quadratically and become model input.
- **Read routes fail closed.** `/api/traces` is not registered at all when `TRACE_KEY` is unset; a wrong key returns 404, never 403.
- **Real tool names** are `get_congestion`, `get_growth`, `get_candidate`, `get_traffic_mix`, `get_national_rank` (`backend/tools.py:210-239`). The spec's example JSON used placeholder names; use the real ones.
- **Backend tests import via the bridge:** `import server.agent_bridge` first (puts `backend/` on `sys.path`), then `import recorder` / `import agent`. See `tests/test_llm.py:11-14`.
- Python tests run from the repo root: `python -m pytest`. `pytest.ini` sets `testpaths = tests`, `pythonpath = .`.
- Frontend tests run from `frontend/`: `npm test` (vitest).

---

### Task 1: The recorder

**Files:**
- Create: `backend/recorder.py`
- Test: `tests/test_recorder.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Recorder()` with `.steps` (list of dicts), `.round` (int), `.start_round()`, and `.step(kind, **fields)` as a context manager yielding a `Step`.
  - `Step.set(**fields)` — merges fields into the recorded dict.
  - `NULL` — module-level null object with the identical interface.

- [ ] **Step 1: Write the failing test**

Create `tests/test_recorder.py`:

```python
"""backend/recorder.py accumulates one dict per timed step.

The recorder sits inside the agent loop, so the tests that matter are about
what it does when things go wrong: it must record a step whose block raised,
and it must never raise anything of its own.
"""
import server.agent_bridge  # noqa: F401  — puts backend/ on sys.path

import pytest  # noqa: E402

from recorder import NULL, Recorder  # noqa: E402


def test_records_kind_round_and_ms():
    rec = Recorder()
    rec.start_round()
    with rec.step("tool", name="get_congestion"):
        pass

    assert len(rec.steps) == 1
    step = rec.steps[0]
    assert step["kind"] == "tool"
    assert step["round"] == 1
    assert step["name"] == "get_congestion"
    assert isinstance(step["ms"], int) and step["ms"] >= 0


def test_start_round_groups_steps():
    rec = Recorder()
    rec.start_round()
    with rec.step("model"):
        pass
    rec.start_round()
    with rec.step("model"):
        pass

    assert [s["round"] for s in rec.steps] == [1, 2]


def test_set_merges_fields_into_the_step():
    rec = Recorder()
    rec.start_round()
    with rec.step("tool", name="get_growth") as step:
        step.set(result={"score": 0.81}, error=None)

    assert rec.steps[0]["result"] == {"score": 0.81}
    assert rec.steps[0]["error"] is None


def test_a_raising_block_still_records_its_step():
    """This is what makes a partial trace possible when ask() dies mid-turn."""
    rec = Recorder()
    rec.start_round()
    with pytest.raises(ValueError):
        with rec.step("tool", name="get_candidate"):
            raise ValueError("boom")

    assert len(rec.steps) == 1
    assert rec.steps[0]["name"] == "get_candidate"


def test_the_block_exception_is_not_swallowed():
    rec = Recorder()
    with pytest.raises(ValueError, match="boom"):
        with rec.step("model"):
            raise ValueError("boom")


def test_null_recorder_records_nothing_and_supports_the_full_interface():
    NULL.start_round()
    with NULL.step("tool", name="get_congestion") as step:
        step.set(result={"anything": 1})

    assert list(NULL.steps) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_recorder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'recorder'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/recorder.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_recorder.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/recorder.py tests/test_recorder.py
git commit -m "feat(recorder): timed steps for the agent loop, null by default"
```

---

### Task 2: Wire the recorder into the agent loop

**Files:**
- Modify: `backend/agent.py` (imports, `Conversation.__init__` at 51-54, `ask()` at 60-70, `_next_message()` at 72-81)
- Test: `tests/test_agent_recorder.py`

**Interfaces:**
- Consumes: `Recorder`, `NULL` from Task 1.
- Produces:
  - `Conversation(model=None, recorder=None)` — `self.recorder` defaults to `NULL`.
  - Model steps: `{kind: "model", round, ms, text, calls: [tool names]}`
  - Tool steps: `{kind: "tool", round, ms, name, args, result, error}`

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_recorder.py`:

```python
"""backend/agent.py, instrumented.

The load-bearing test here is the LAST one: the whole justification for putting
a recorder inside the loop is that it costs nothing when absent. If the null
default ever changes behaviour, the tradeoff this design accepted stops being
worth it.

No key and no network: FakeClient stands in for llm.Client.
"""
import json

import server.agent_bridge  # noqa: F401  — puts backend/ on sys.path

import agent  # noqa: E402
from recorder import Recorder  # noqa: E402


class FakeClient:
    """Returns scripted assistant messages, one per complete() call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.model = "fake-model"
        self.calls = 0

    def complete(self, system, messages, tools):
        self.calls += 1
        return self.replies.pop(0)


def tool_call(call_id, name, args):
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def build(monkeypatch, replies, recorder=None):
    """A Conversation whose client is scripted."""
    monkeypatch.setattr(agent, "Client", lambda model=None: FakeClient(replies))
    return agent.Conversation(recorder=recorder)


ANSWER = {"role": "assistant", "content": "SFO runs about 81% full."}


def test_records_a_model_step_per_round(monkeypatch):
    rec = Recorder()
    convo = build(monkeypatch, [ANSWER], recorder=rec)
    convo.ask("How congested is SFO?")

    models = [s for s in rec.steps if s["kind"] == "model"]
    assert len(models) == 1
    assert models[0]["round"] == 1
    assert models[0]["text"] == "SFO runs about 81% full."
    assert models[0]["calls"] == []


def test_records_tool_name_args_and_result(monkeypatch):
    monkeypatch.setattr(agent, "TOOLS",
                        {"get_congestion": lambda airport: {"load_factor": 80.9}})
    rec = Recorder()
    convo = build(monkeypatch, [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"})]},
        ANSWER,
    ], recorder=rec)
    convo.ask("How congested is SFO?")

    tools = [s for s in rec.steps if s["kind"] == "tool"]
    assert len(tools) == 1
    assert tools[0]["name"] == "get_congestion"
    assert tools[0]["args"] == {"airport": "SFO"}
    assert tools[0]["result"] == {"load_factor": 80.9}
    assert tools[0]["error"] is None
    assert tools[0]["round"] == 1


def test_the_model_step_lists_the_tools_it_asked_for(monkeypatch):
    monkeypatch.setattr(agent, "TOOLS",
                        {"get_congestion": lambda airport: {"load_factor": 80.9}})
    rec = Recorder()
    convo = build(monkeypatch, [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"}),
                        tool_call("c2", "get_congestion", {"airport": "BOS"})]},
        ANSWER,
    ], recorder=rec)
    convo.ask("SFO or BOS?")

    assert rec.steps[0]["calls"] == ["get_congestion", "get_congestion"]


def test_a_failing_tool_is_recorded_and_the_turn_still_succeeds(monkeypatch):
    """agent.py turns a tool exception into an {"error": ...} the model reads and
    recovers from, so a SUCCESSFUL turn can legitimately contain a failed step."""
    def explode(airport):
        raise RuntimeError("BTS is down")

    monkeypatch.setattr(agent, "TOOLS", {"get_congestion": explode})
    rec = Recorder()
    convo = build(monkeypatch, [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"})]},
        ANSWER,
    ], recorder=rec)
    answer = convo.ask("How congested is SFO?")

    assert answer == "SFO runs about 81% full."
    tools = [s for s in rec.steps if s["kind"] == "tool"]
    assert tools[0]["error"] == "RuntimeError: BTS is down"
    assert tools[0]["result"] == {"error": "RuntimeError: BTS is down"}


def test_rounds_increment_across_tool_rounds(monkeypatch):
    monkeypatch.setattr(agent, "TOOLS",
                        {"get_congestion": lambda airport: {"load_factor": 80.9}})
    rec = Recorder()
    convo = build(monkeypatch, [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"})]},
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c2", "get_congestion", {"airport": "BOS"})]},
        ANSWER,
    ], recorder=rec)
    convo.ask("SFO then BOS")

    assert [s["round"] for s in rec.steps] == [1, 1, 2, 2, 3]


def test_null_recorder_leaves_behaviour_identical(monkeypatch):
    """The entire justification for the coupling in agent.py. If this fails, the
    tradeoff the design accepted no longer holds."""
    monkeypatch.setattr(agent, "TOOLS",
                        {"get_congestion": lambda airport: {"load_factor": 80.9}})
    replies = [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"})]},
        ANSWER,
    ]
    plain = build(monkeypatch, [dict(r) for r in replies])
    answer = plain.ask("How congested is SFO?")

    assert answer == "SFO runs about 81% full."
    assert [m["role"] for m in plain.messages] == [
        "system", "user", "assistant", "tool", "assistant"]
    assert plain.messages[3]["content"] == json.dumps({"load_factor": 80.9})
    assert plain.messages[3]["tool_call_id"] == "c1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agent_recorder.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'recorder'`

- [ ] **Step 3: Write minimal implementation**

In `backend/agent.py`, add to the imports (after `from llm import Client`):

```python
from recorder import NULL
```

Add these two module-level helpers just above `class Conversation` (after `call_tool`):

```python
def step_args(call):
    """A tool call's arguments as a dict, for the trace. Arguments arrive as a
    JSON string and a malformed one must not break a turn — it certainly must
    not break the recording of one."""
    try:
        return json.loads(call["function"]["arguments"])
    except (ValueError, TypeError):
        return {}


def step_outcome(raw):
    """What call_tool returned, split into a result and an error for the trace.

    call_tool never raises: a failed tool comes back as {"error": ...} that the
    model reads and recovers from. Pulling that key out here is what lets the UI
    mark a step failed even though the turn as a whole succeeded.
    """
    try:
        result = json.loads(raw)
    except (ValueError, TypeError):
        result = raw
    error = result.get("error") if isinstance(result, dict) else None
    return {"result": result, "error": error}
```

Replace `Conversation.__init__` (lines 51-54) with:

```python
    def __init__(self, model=None, recorder=None):
        self.client = Client(model)
        self.model = self.client.model
        # NULL by default: the CLI, the REPL and run() carry no tracing, and
        # backend/ keeps working with no server and no database.
        self.recorder = recorder or NULL
        self.messages = [{"role": "system", "content": SYSTEM}]
```

Replace `ask()` (lines 60-70) with:

```python
    def ask(self, question):
        self.say("user", question)
        for _ in range(MAX_ROUNDS):
            self.recorder.start_round()
            msg = self._next_message()
            calls = msg.get("tool_calls")
            if not calls:
                self.trim()                  # only safe once the turn has settled
                return msg["content"]
            for call in calls:
                # The timing wraps call_tool from OUT HERE, where the recorder
                # already lives, so call_tool itself stays the pure function it
                # was and its recovery guard is untouched.
                with self.recorder.step("tool", name=call["function"]["name"],
                                        args=step_args(call)) as step:
                    output = call_tool(call)
                    step.set(**step_outcome(output))
                self.say("tool", output, tool_call_id=call["id"])
        return "Stopped after too many tool rounds."
```

Replace `_next_message()` (lines 72-81) with:

```python
    def _next_message(self):
        """One model call. llm.py hands back a plain dict, so self.messages
        stays uniformly JSON-serialisable — that is what lets the whole history
        round-trip through the browser and back."""
        with self.recorder.step("model") as step:
            message = self.client.complete(
                system=self.messages[0]["content"],   # the system prompt is not a message
                messages=self.messages[1:],
                tools=TOOL_SCHEMAS)
            # Inside the block on purpose: recorded even if a later line throws.
            step.set(text=message.get("content", ""),
                     calls=[c["function"]["name"]
                            for c in message.get("tool_calls") or []])
        self.messages.append(message)
        return message
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agent_recorder.py tests/test_recorder.py -v`
Expected: PASS — 12 passed

- [ ] **Step 5: Verify nothing else regressed**

Run: `python -m pytest -v`
Expected: PASS — all pre-existing tests still green

- [ ] **Step 6: Commit**

```bash
git add backend/agent.py tests/test_agent_recorder.py
git commit -m "feat(agent): record timed model and tool steps through an injected recorder"
```

---

### Task 3: The SQLite trace store

**Files:**
- Create: `server/trace_store.py`
- Modify: `server/tracing.py` (docstring only)
- Test: `tests/test_trace_store.py`

**Interfaces:**
- Consumes: `trace()` from `server/tracing.py`.
- Produces:
  - `make_record(question, answer, model, steps, latency_ms, error=None) -> dict`
  - `write(record, path=None) -> None` — never raises
  - `recent(limit=50, offset=0, path=None) -> list[dict]` — newest first, **no `steps` key**
  - `get(trace_id, path=None) -> dict | None` — full record, `steps` parsed

- [ ] **Step 1: Write the failing test**

Create `tests/test_trace_store.py`:

```python
"""server/trace_store.py — one capped SQLite table of turns.

Best-effort by contract: every failure mode here must degrade to the stdout
sink rather than reach the request.
"""
import sqlite3

import pytest

from server import trace_store


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "traces.db")


def record(question="How congested is SFO?", steps=None):
    return trace_store.make_record(
        question=question,
        answer="About 81% full.",
        model="claude-opus-5",
        steps=steps if steps is not None else [
            {"kind": "model", "round": 1, "ms": 1240, "text": "",
             "calls": ["get_congestion"]},
            {"kind": "tool", "round": 1, "ms": 1810, "name": "get_congestion",
             "args": {"airport": "SFO"}, "result": {"load_factor": 80.9},
             "error": None},
        ],
        latency_ms=3050)


def test_make_record_stamps_an_id_and_a_timestamp():
    made = record()
    assert made["id"]
    assert made["ts"].endswith("Z")
    assert made["error"] is None
    assert made["latency_ms"] == 3050


def test_write_then_get_round_trips_the_steps(db):
    made = record()
    trace_store.write(made, path=db)

    got = trace_store.get(made["id"], path=db)
    assert got["question"] == "How congested is SFO?"
    assert got["answer"] == "About 81% full."
    assert got["model"] == "claude-opus-5"
    assert got["steps"][1]["args"] == {"airport": "SFO"}
    assert got["steps"][1]["result"] == {"load_factor": 80.9}


def test_get_returns_none_for_an_unknown_id(db):
    trace_store.write(record(), path=db)
    assert trace_store.get("no-such-id", path=db) is None


def test_recent_is_newest_first_and_omits_steps(db):
    for question in ["first", "second", "third"]:
        trace_store.write(record(question=question), path=db)

    rows = trace_store.recent(path=db)
    assert [r["question"] for r in rows] == ["third", "second", "first"]
    assert "steps" not in rows[0]
    # The summary still carries what the list view renders.
    assert rows[0]["latency_ms"] == 3050
    assert rows[0]["step_count"] == 2


def test_recent_honours_limit_and_offset(db):
    for question in ["a", "b", "c", "d"]:
        trace_store.write(record(question=question), path=db)

    assert [r["question"] for r in trace_store.recent(limit=2, path=db)] == ["d", "c"]
    assert [r["question"] for r in
            trace_store.recent(limit=2, offset=2, path=db)] == ["b", "a"]


def test_retention_keeps_only_the_newest_rows(db, monkeypatch):
    monkeypatch.setenv("TRACE_MAX_ROWS", "3")
    for question in ["a", "b", "c", "d", "e"]:
        trace_store.write(record(question=question), path=db)

    rows = trace_store.recent(path=db)
    assert [r["question"] for r in rows] == ["e", "d", "c"]


def test_write_survives_an_unwritable_database(tmp_path):
    """The premise of a best-effort sink: /chat must not care that this failed."""
    unwritable = str(tmp_path / "no-such-dir" / "traces.db")
    trace_store.write(record(), path=unwritable)   # must not raise


def test_write_survives_a_corrupt_database(db):
    with open(db, "w") as fh:
        fh.write("this is not a database")
    trace_store.write(record(), path=db)           # must not raise


def test_reads_survive_a_missing_database(tmp_path):
    missing = str(tmp_path / "never-written.db")
    assert trace_store.recent(path=missing) == []
    assert trace_store.get("anything", path=missing) is None


def test_path_comes_from_the_environment_when_not_given(tmp_path, monkeypatch):
    configured = str(tmp_path / "from-env.db")
    monkeypatch.setenv("TRACE_DB", configured)
    made = record()
    trace_store.write(made)

    assert trace_store.get(made["id"])["question"] == "How congested is SFO?"
    with sqlite3.connect(configured) as con:
        assert con.execute("SELECT COUNT(*) FROM traces").fetchone()[0] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trace_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'trace_store' from 'server'`

- [ ] **Step 3: Write minimal implementation**

Create `server/trace_store.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_trace_store.py -v`
Expected: PASS — 10 passed

- [ ] **Step 5: Amend the stdout sink's docstring**

In `server/tracing.py`, replace the module docstring with:

```python
"""The stdout tracing sink.

One JSON object per line, which Render captures in its log viewer.

There are now TWO sinks for a turn: this one and the SQLite table in
trace_store.py. That duplication is deliberate, not an oversight — Render's
free tier wipes the disk on redeploy, so the log stream is what survives when
the database does not. Do not "clean up" one of them without replacing the
durability it provides.
"""
```

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -v`
Expected: PASS — everything green, including the existing `tests/test_tracing.py`

- [ ] **Step 7: Commit**

```bash
git add server/trace_store.py server/tracing.py tests/test_trace_store.py
git commit -m "feat(store): capped SQLite table of turns, best-effort by contract"
```

---

### Task 4: Ship the trace in the /chat response

**Files:**
- Modify: `server/schemas.py` (add `TraceStep`, `Trace`; add `trace` to `ChatResponse`)
- Modify: `server/app.py:36-96`
- Test: `tests/test_chat_trace.py`

**Interfaces:**
- Consumes: `Recorder` (Task 1), `make_record`/`write` (Task 3).
- Produces: `ChatResponse.trace` — a `Trace` on every `/chat` 200; a row in the store for both success and failure.

- [ ] **Step 1: Write the failing test**

Create `tests/test_chat_trace.py`:

```python
"""/chat carries a trace, and stores one — including when the turn dies.

The fake Conversation in conftest.py does not run a real loop, so these tests
drive the recorder the way the real Conversation would: server/app.py assigns
convo.recorder, and the fake fills it.
"""
import pytest
from fastapi.testclient import TestClient

from server import trace_store
from server.app import create_app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACE_DB", str(tmp_path / "traces.db"))


class RecordingConversation:
    """A fake that writes into whatever recorder app.py assigns."""

    raises = None
    model = "fake-model"

    def __init__(self):
        self.messages = [{"role": "system", "content": "system prompt"}]
        self.recorder = None

    def trim(self):
        pass

    def ask(self, question):
        self.messages.append({"role": "user", "content": question})
        self.recorder.start_round()
        with self.recorder.step("model") as step:
            step.set(text="", calls=["get_congestion"])
        with self.recorder.step("tool", name="get_congestion",
                                args={"airport": "SFO"}) as step:
            step.set(result={"load_factor": 80.9}, error=None)
        if type(self).raises:
            raise type(self).raises
        self.messages.append({"role": "assistant", "content": "About 81% full."})
        return "About 81% full."


@pytest.fixture
def recording():
    RecordingConversation.raises = None
    yield RecordingConversation


@pytest.fixture
def rec_client(recording):
    return TestClient(create_app(conversation_factory=recording))


def test_the_response_carries_the_trace(rec_client):
    body = rec_client.post("/chat", json={"question": "How congested is SFO?",
                                          "history": []}).json()

    trace = body["trace"]
    assert trace["question"] == "How congested is SFO?"
    assert trace["answer"] == "About 81% full."
    assert trace["error"] is None
    assert trace["latency_ms"] >= 0
    assert [s["kind"] for s in trace["steps"]] == ["model", "tool"]
    assert trace["steps"][1]["name"] == "get_congestion"
    assert trace["steps"][1]["args"] == {"airport": "SFO"}
    assert trace["steps"][1]["result"] == {"load_factor": 80.9}


def test_the_turn_is_persisted(rec_client):
    body = rec_client.post("/chat", json={"question": "How congested is SFO?",
                                          "history": []}).json()

    stored = trace_store.get(body["trace"]["id"])
    assert stored["question"] == "How congested is SFO?"
    assert len(stored["steps"]) == 2


def test_a_failed_turn_stores_a_partial_trace(rec_client, recording):
    """The benefit that motivated holding the recorder in app.py: the steps that
    completed before the failure are exactly what you want to look at."""
    recording.raises = RuntimeError("BTS timed out")
    response = rec_client.post("/chat", json={"question": "How congested is SFO?",
                                              "history": []})
    assert response.status_code == 502

    rows = trace_store.recent()
    assert len(rows) == 1
    assert rows[0]["error"] == "RuntimeError: BTS timed out"
    assert rows[0]["question"] == "How congested is SFO?"
    assert trace_store.get(rows[0]["id"])["steps"][1]["name"] == "get_congestion"


def test_a_broken_store_does_not_break_chat(rec_client, monkeypatch, tmp_path):
    monkeypatch.setenv("TRACE_DB", str(tmp_path / "nope" / "traces.db"))
    response = rec_client.post("/chat", json={"question": "How congested is SFO?",
                                              "history": []})

    assert response.status_code == 200
    assert response.json()["answer"] == "About 81% full."


def test_existing_response_fields_are_untouched(client):
    """conftest's plain FakeConversation has no recorder attribute of its own —
    app.py must still work with the pre-existing test double."""
    body = client.post("/chat", json={"question": "hi", "history": []}).json()

    assert body["answer"] == "A plain-English answer."
    assert body["charts"] == []
    assert body["history"][-1]["content"] == "A plain-English answer."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_chat_trace.py -v`
Expected: FAIL — `KeyError: 'trace'`

- [ ] **Step 3: Add the wire types**

In `server/schemas.py`, add above `ChatResponse`:

```python
class TraceStep(BaseModel):
    """One step of a turn. `kind` is "model" or "tool"; the fields that apply
    depend on which, so everything past the first three is optional."""
    kind: str
    round: int = 0
    ms: int = 0
    name: str | None = None                            # tool steps
    args: dict = Field(default_factory=dict)           # tool steps
    result: Any = None                                 # tool steps
    error: str | None = None                           # tool steps
    text: str | None = None                            # model steps
    calls: list[str] = Field(default_factory=list)     # model steps


class Trace(BaseModel):
    id: str
    ts: str
    model: str | None = None
    question: str
    answer: str = ""
    latency_ms: int = 0
    error: str | None = None
    steps: list[TraceStep] = Field(default_factory=list)
```

And add the field to `ChatResponse`:

```python
class ChatResponse(BaseModel):
    answer: str
    charts: list[Chart]
    history: list[Any]
    trace: Trace
```

- [ ] **Step 4: Wire it into the endpoint**

In `server/app.py`, add to the imports:

```python
from server import trace_store
from server.schemas import ChatRequest, ChatResponse
```

(replacing the existing `from server.schemas import ChatRequest, ChatResponse` line — it is unchanged, listed here only for position), and:

```python
from recorder import Recorder
```

must NOT be imported at module scope — `backend/` is only on `sys.path` once `server.agent_bridge` has been imported. Add this instead, inside `create_app`, right after the existing factory default block:

```python
    from server.agent_bridge import Conversation  # noqa: F401 — puts backend/ on sys.path
    from recorder import Recorder
```

Then in `chat()`, after the `convo = conversation_factory()` try/except, add:

```python
        # Assigned rather than passed: conversation_factory keeps its zero-argument
        # contract, so the existing test doubles in tests/conftest.py still work.
        recorder = Recorder()
        convo.recorder = recorder
```

Replace the `except` block around `convo.ask(question)` and the lines after it with:

```python
        try:
            answer = convo.ask(question)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            trace("chat_error", question=question, error=error)
            # The recorder is OURS, so the steps that completed before the
            # failure are still here. A dead turn is the one most worth a trace.
            trace_store.write(trace_store.make_record(
                question=question, answer="", model=getattr(convo, "model", None),
                steps=list(recorder.steps),
                latency_ms=int((time.monotonic() - started) * 1000), error=error))
            # 502 with a readable message, not a 500 page: the chat stays usable
            # and the user can retry.
            return JSONResponse({"error": error}, status_code=502)

        fresh = [m for m in convo.messages if id(m) not in seen]
        del retained  # safe to release now that `fresh` no longer depends on ids
        charts = charts_from_messages(fresh)
        record = trace_store.make_record(
            question=question, answer=answer, model=getattr(convo, "model", None),
            steps=list(recorder.steps),
            latency_ms=int((time.monotonic() - started) * 1000))
        trace_store.write(record)
        trace("chat", question=question, answer=answer,
              tools=[c["tool"] for c in charts],
              tool_results=[c["data"] for c in charts],
              latency_ms=record["latency_ms"])

        # Everything except the system prompt: the client stores this and replays
        # it next turn, and our prompt is rebuilt server-side each time.
        return ChatResponse(answer=answer, charts=charts,
                            history=convo.messages[1:], trace=record)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_chat_trace.py -v`
Expected: PASS — 5 passed

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -v`
Expected: PASS. `tests/test_chat_endpoint.py` must still be green — if it asserts on exact response keys, add `trace` to the expectation there.

- [ ] **Step 7: Commit**

```bash
git add server/app.py server/schemas.py tests/test_chat_trace.py tests/test_chat_endpoint.py
git commit -m "feat(chat): return and persist a trace for every turn, failures included"
```

---

### Task 5: The key-gated read API

**Files:**
- Modify: `server/app.py` (new routes inside `create_app`, before the StaticFiles mount)
- Modify: `render.yaml`
- Test: `tests/test_trace_api.py`

**Interfaces:**
- Consumes: `recent`, `get` (Task 3).
- Produces: `GET /api/traces?limit=&offset=` and `GET /api/traces/{id}`, both requiring header `X-Trace-Key`, both absent when `TRACE_KEY` is unset.

- [ ] **Step 1: Write the failing test**

Create `tests/test_trace_api.py`:

```python
"""The read API fails closed.

The app is otherwise stateless by design — "no visitor can see another's
conversation" is true because nothing is stored. Persisting traces ends that,
so this route is the one place the property now has to be defended.
"""
import pytest
from fastapi.testclient import TestClient

from server import trace_store
from server.app import create_app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACE_DB", str(tmp_path / "traces.db"))


def stored(question="How congested is SFO?"):
    record = trace_store.make_record(
        question=question, answer="About 81% full.", model="claude-opus-5",
        steps=[{"kind": "tool", "round": 1, "ms": 1810, "name": "get_congestion",
                "args": {"airport": "SFO"}, "result": {"load_factor": 80.9},
                "error": None}],
        latency_ms=3050)
    trace_store.write(record)
    return record


def keyed(monkeypatch, fake, key="s3cret"):
    monkeypatch.setenv("TRACE_KEY", key)
    return TestClient(create_app(conversation_factory=fake))


def test_the_routes_do_not_exist_without_a_key(monkeypatch, fake):
    monkeypatch.delenv("TRACE_KEY", raising=False)
    client = TestClient(create_app(conversation_factory=fake))
    stored()

    assert client.get("/api/traces").status_code == 404


def test_a_wrong_key_is_404_not_403(monkeypatch, fake):
    """404 so a prober cannot tell 'wrong key' from 'no such route'."""
    client = keyed(monkeypatch, fake)
    stored()

    assert client.get("/api/traces",
                      headers={"X-Trace-Key": "wrong"}).status_code == 404


def test_a_missing_header_is_404(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    stored()

    assert client.get("/api/traces").status_code == 404


def test_the_right_key_lists_summaries_newest_first(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    stored("first")
    stored("second")

    body = client.get("/api/traces", headers={"X-Trace-Key": "s3cret"}).json()
    assert [row["question"] for row in body["traces"]] == ["second", "first"]
    assert "steps" not in body["traces"][0]
    assert body["traces"][0]["step_count"] == 1


def test_limit_and_offset_pass_through(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    for question in ["a", "b", "c"]:
        stored(question)

    body = client.get("/api/traces?limit=1&offset=1",
                      headers={"X-Trace-Key": "s3cret"}).json()
    assert [row["question"] for row in body["traces"]] == ["b"]


def test_one_trace_comes_back_whole(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    record = stored()

    body = client.get(f"/api/traces/{record['id']}",
                      headers={"X-Trace-Key": "s3cret"}).json()
    assert body["steps"][0]["name"] == "get_congestion"
    assert body["steps"][0]["result"] == {"load_factor": 80.9}


def test_an_unknown_trace_id_is_404(monkeypatch, fake):
    client = keyed(monkeypatch, fake)

    assert client.get("/api/traces/no-such-id",
                      headers={"X-Trace-Key": "s3cret"}).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trace_api.py -v`
Expected: FAIL — the list test gets 404 from the StaticFiles mount, not from the guard; `test_the_right_key_lists_summaries_newest_first` fails on JSON decode.

- [ ] **Step 3: Write the routes**

In `server/app.py` add `import hmac` to the imports, and add the following inside
`create_app` **after** the `/health` route and **before** the StaticFiles mount:

```python
    # Registered only when TRACE_KEY is set, so a fresh checkout exposes nothing.
    # The app is otherwise stateless by design (see the module docstring); storing
    # traces ends that, and this is where the property is defended.
    trace_key = os.environ.get("TRACE_KEY")
    if trace_key:

        def authorised(request):
            given = request.headers.get("X-Trace-Key", "")
            return hmac.compare_digest(trace_key, given)

        # 404, never 403: a prober cannot tell a wrong key from a missing route.
        missing = JSONResponse({"error": "Not found."}, status_code=404)

        @app.get("/api/traces")
        def list_traces(request: Request, limit: int = 50, offset: int = 0):
            if not authorised(request):
                return missing
            return {"traces": trace_store.recent(limit=min(limit, 200),
                                                 offset=max(offset, 0))}

        @app.get("/api/traces/{trace_id}")
        def one_trace(request: Request, trace_id: str):
            if not authorised(request):
                return missing
            record = trace_store.get(trace_id)
            return record if record else missing
```

Add `Request` to the FastAPI import:

```python
from fastapi import FastAPI, Request
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_trace_api.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Declare the env vars for deploys**

In `render.yaml`, add to the service's `envVars` list:

```yaml
      - key: TRACE_DB
        value: /tmp/traces.db
      - key: TRACE_MAX_ROWS
        value: "2000"
      - key: TRACE_KEY
        sync: false      # set by hand in the dashboard; unset = no read API
```

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m pytest -v`
Expected: PASS

```bash
git add server/app.py render.yaml tests/test_trace_api.py
git commit -m "feat(api): key-gated read routes for stored traces, failing closed"
```

---

### Task 6: Carry the trace through the frontend data layer

**Files:**
- Modify: `frontend/src/api/chat.js`
- Modify: `frontend/src/hooks/useChat.js`
- Test: `frontend/src/__tests__/useChat.test.jsx` (add cases)

**Interfaces:**
- Consumes: `body.trace` from Task 4, `/api/traces` from Task 5.
- Produces:
  - `useChat()` additionally returns `traces` — an object keyed by agent message id.
  - `fetchTraces(key, { limit, offset })` and `fetchTrace(key, id)` from `api/chat.js`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/__tests__/useChat.test.jsx`:

```jsx
  it('keeps the trace keyed by the answer message id', async () => {
    sendChat.mockResolvedValue({
      answer: 'About 81% full.',
      charts: [],
      history: [{ role: 'user', content: 'How congested is SFO?' }],
      trace: { id: 't1', steps: [{ kind: 'tool', name: 'get_congestion' }] },
    })

    const { result } = renderHook(() => useChat())
    await act(async () => { await result.current.send('How congested is SFO?') })

    const answer = result.current.messages.find((m) => m.role === 'agent')
    expect(result.current.traces[answer.id].id).toBe('t1')
  })

  it('never puts the trace into the history it replays', async () => {
    // llmHistory is re-uploaded every turn and becomes model input. A trace in
    // there would grow quadratically AND let the agent read its own timings.
    sendChat.mockResolvedValue({
      answer: 'About 81% full.',
      charts: [],
      history: [{ role: 'user', content: 'How congested is SFO?' }],
      trace: { id: 't1', steps: [{ kind: 'tool', name: 'get_congestion' }] },
    })

    const { result } = renderHook(() => useChat())
    await act(async () => { await result.current.send('How congested is SFO?') })
    await act(async () => { await result.current.send('and Boston?') })

    const [{ history }] = sendChat.mock.calls[1]
    expect(JSON.stringify(history)).not.toContain('get_congestion')
    expect(history.every((m) => !('trace' in m))).toBe(true)
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/__tests__/useChat.test.jsx`
Expected: FAIL — `Cannot read properties of undefined (reading 'id')` (`traces` is undefined)

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/hooks/useChat.js`, add the state beside `charts`:

```jsx
  const [traces, setTraces] = useState({})
```

Inside the `try` block, after the `setCharts` call, add:

```jsx
      // Deliberately NOT in llmHistory: that ref is replayed to the server every
      // turn, so a trace in there would be re-uploaded on every message and would
      // become model input — the agent reading its own timings back.
      if (body.trace) setTraces((prior) => ({ ...prior, [answerId]: body.trace }))
```

Note the ordering: `answerId` is already defined above the `setCharts` call at line 30, so this goes after it.

Add `traces` to the returned object:

```jsx
  return { messages, charts, traces, selectedChartId, status, error: null,
           send, selectChart, retry }
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/__tests__/useChat.test.jsx`
Expected: PASS

- [ ] **Step 5: Add the read-API client**

Append to `frontend/src/api/chat.js`:

```js
// The debug page reads past turns back. The key travels in a header, never in
// the query string: the page takes it from the URL fragment, which browsers do
// not transmit, so it stays out of the server's access logs.
async function readTraces(path, key) {
  const response = await fetch(path, { headers: { 'X-Trace-Key': key } })
  if (!response.ok) {
    throw new ChatError(
      response.status === 404
        ? 'No traces here — check the key in the URL.'
        : `The server returned an error (${response.status}).`)
  }
  return response.json()
}

export function fetchTraces(key, { limit = 50, offset = 0 } = {}) {
  return readTraces(`/api/traces?limit=${limit}&offset=${offset}`, key)
}

export function fetchTrace(key, id) {
  return readTraces(`/api/traces/${encodeURIComponent(id)}`, key)
}
```

- [ ] **Step 6: Run the frontend suite and commit**

Run (from `frontend/`): `npm test`
Expected: PASS — all green

```bash
git add frontend/src/api/chat.js frontend/src/hooks/useChat.js frontend/src/__tests__/useChat.test.jsx
git commit -m "feat(frontend): keep each turn's trace out of the replayed history"
```

---

### Task 7: The step list component

**Files:**
- Create: `frontend/src/components/TraceSteps.jsx`
- Test: `frontend/src/__tests__/TraceSteps.test.jsx`

**Interfaces:**
- Consumes: a `steps` array as produced by Task 2.
- Produces: `<TraceSteps steps={[...]} />` — steps grouped by round. Used by both Task 8 (inline) and Task 11 (debug page); this shared component is why the two surfaces are one piece of work.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/TraceSteps.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import TraceSteps from '../components/TraceSteps'

const STEPS = [
  { kind: 'model', round: 1, ms: 1240, text: '', calls: ['get_congestion'] },
  { kind: 'tool', round: 1, ms: 1810, name: 'get_congestion',
    args: { airport: 'SFO' }, result: { load_factor: 80.9 }, error: null },
  { kind: 'tool', round: 2, ms: 620, name: 'get_growth',
    args: { airport: 'SFO' }, result: null, error: 'RuntimeError: BTS is down' },
]

describe('TraceSteps', () => {
  it('groups steps by round', () => {
    render(<TraceSteps steps={STEPS} />)
    expect(screen.getByText('Round 1')).toBeInTheDocument()
    expect(screen.getByText('Round 2')).toBeInTheDocument()
  })

  it('names each tool with its arguments and duration', () => {
    render(<TraceSteps steps={STEPS} />)
    expect(screen.getByText('get_congestion')).toBeInTheDocument()
    expect(screen.getByText('airport=SFO')).toBeInTheDocument()
    expect(screen.getByText('1.8s')).toBeInTheDocument()
  })

  it('labels the model step by how long the model took', () => {
    render(<TraceSteps steps={STEPS} />)
    expect(screen.getByText('model')).toBeInTheDocument()
    expect(screen.getByText('1.2s')).toBeInTheDocument()
  })

  it('marks a failed step with its error', () => {
    render(<TraceSteps steps={STEPS} />)
    expect(screen.getByText('RuntimeError: BTS is down')).toBeInTheDocument()
  })

  it('hides the raw payload behind a second toggle', async () => {
    render(<TraceSteps steps={STEPS} />)
    // The full BTS payload is what you want when debugging and what you do not
    // want unfurling into the chat by default.
    expect(screen.queryByText(/load_factor/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('raw'))
    expect(screen.getByText(/load_factor/)).toBeInTheDocument()
  })

  it('renders nothing for an empty step list', () => {
    const { container } = render(<TraceSteps steps={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/__tests__/TraceSteps.test.jsx`
Expected: FAIL — cannot resolve `../components/TraceSteps`

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/TraceSteps.jsx`:

```jsx
// The steps of one turn, grouped by round. Shared by the inline disclosure and
// the debug page, which is what keeps those two surfaces from drifting apart.

const seconds = (ms) => `${((ms || 0) / 1000).toFixed(1)}s`

const argsLine = (args) =>
  Object.entries(args || {})
    .map(([key, value]) => `${key}=${Array.isArray(value) ? value.join(',') : value}`)
    .join('  ')

function Step({ step }) {
  const failed = Boolean(step.error)
  return (
    <li className={`trace-step ${step.kind} ${failed ? 'failed' : ''}`}>
      <div className="trace-step-head">
        <span className="trace-step-name">{step.name || step.kind}</span>
        <span className="trace-step-ms">{seconds(step.ms)}</span>
      </div>
      {step.kind === 'tool' && (
        <div className="trace-step-args">{argsLine(step.args)}</div>
      )}
      {failed && <div className="trace-step-error">{step.error}</div>}
      {step.kind === 'tool' && step.result != null && (
        <details className="trace-raw">
          <summary>raw</summary>
          <pre>{JSON.stringify(step.result, null, 2)}</pre>
        </details>
      )}
    </li>
  )
}

export default function TraceSteps({ steps }) {
  if (!steps || !steps.length) return null

  const rounds = []
  steps.forEach((step) => {
    const round = rounds.find((r) => r.round === step.round)
    if (round) round.steps.push(step)
    else rounds.push({ round: step.round, steps: [step] })
  })

  return (
    <div className="trace-steps">
      {rounds.map((round) => (
        <div className="trace-round" key={round.round}>
          <div className="trace-round-label">Round {round.round}</div>
          <ol>
            {round.steps.map((step, index) => (
              <Step step={step} key={`${round.round}-${index}`} />
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/__tests__/TraceSteps.test.jsx`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TraceSteps.jsx frontend/src/__tests__/TraceSteps.test.jsx
git commit -m "feat(frontend): shared step-list rendering for traces"
```

---

### Task 8: The inline disclosure

**Files:**
- Create: `frontend/src/components/TraceDisclosure.jsx`
- Modify: `frontend/src/components/ChatColumn.jsx`
- Modify: `frontend/src/App.jsx:24-31`
- Modify: `frontend/src/theme.css` (append)
- Modify: `backend/TESTS.md:17-32`
- Test: `frontend/src/__tests__/TraceDisclosure.test.jsx`

**Interfaces:**
- Consumes: `TraceSteps` (Task 7), `traces` from `useChat` (Task 6).
- Produces: `<TraceDisclosure trace={...} />`, rendered inside `MessageBubble` for agent messages.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/TraceDisclosure.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import TraceDisclosure from '../components/TraceDisclosure'

const TRACE = {
  id: 't1',
  latency_ms: 4210,
  error: null,
  steps: [
    { kind: 'model', round: 1, ms: 1240, text: '', calls: ['get_congestion'] },
    { kind: 'tool', round: 1, ms: 1810, name: 'get_congestion',
      args: { airport: 'LAX' }, result: { score: 0.81 }, error: null },
    { kind: 'tool', round: 2, ms: 620, name: 'get_growth',
      args: { airport: 'LAX' }, result: { cagr: 3.9 }, error: null },
  ],
}

describe('TraceDisclosure', () => {
  it('summarises signals, rounds and total time', () => {
    render(<TraceDisclosure trace={TRACE} />)
    expect(screen.getByText('2 signals · 2 rounds · 4.2s')).toBeInTheDocument()
  })

  it('is collapsed by default so it never competes with the answer', () => {
    render(<TraceDisclosure trace={TRACE} />)
    expect(screen.queryByText('Round 1')).not.toBeInTheDocument()
  })

  it('expands to the step list', async () => {
    render(<TraceDisclosure trace={TRACE} />)
    await userEvent.click(screen.getByText('2 signals · 2 rounds · 4.2s'))
    expect(screen.getByText('Round 1')).toBeInTheDocument()
    expect(screen.getByText('get_growth')).toBeInTheDocument()
  })

  it('says so when no tool ran — the finding worth watching for', () => {
    render(<TraceDisclosure trace={{ ...TRACE, steps: [TRACE.steps[0]] }} />)
    expect(screen.getByText(/no signal was measured/i)).toBeInTheDocument()
  })

  it('renders nothing without a trace', () => {
    const { container } = render(<TraceDisclosure trace={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/__tests__/TraceDisclosure.test.jsx`
Expected: FAIL — cannot resolve `../components/TraceDisclosure`

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/TraceDisclosure.jsx`:

```jsx
import TraceSteps from './TraceSteps'

// Collapsed by default: the answer is what the analyst came for, and the work
// behind it should be one click away rather than in the way. Native <details>
// so it needs no state and stays keyboard-accessible.

export default function TraceDisclosure({ trace }) {
  if (!trace) return null

  const tools = (trace.steps || []).filter((s) => s.kind === 'tool')
  const rounds = new Set((trace.steps || []).map((s) => s.round)).size
  const seconds = ((trace.latency_ms || 0) / 1000).toFixed(1)
  const summary =
    `${tools.length} signal${tools.length === 1 ? '' : 's'} · ` +
    `${rounds} round${rounds === 1 ? '' : 's'} · ${seconds}s`

  return (
    <details className="trace">
      <summary>{summary}</summary>
      {tools.length === 0 && (
        // The finding worth watching for: the answer came from training
        // knowledge, not from BTS data.
        <p className="trace-empty">
          No signal was measured — this answer did not come from the data.
        </p>
      )}
      <TraceSteps steps={trace.steps} />
      {trace.error && <p className="trace-step-error">{trace.error}</p>}
    </details>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/__tests__/TraceDisclosure.test.jsx`
Expected: PASS — 5 passed

- [ ] **Step 5: Wire it into the chat column**

In `frontend/src/components/ChatColumn.jsx`, add the import:

```jsx
import TraceDisclosure from './TraceDisclosure'
```

Add `traces` to the props:

```jsx
export default function ChatColumn({ messages, charts, traces, selectedChartId,
                                     onSelectChart, status, onPickStarter }) {
```

And render it as the last child inside `MessageBubble`, after the inline charts:

```jsx
            <TraceDisclosure trace={(traces || {})[message.id]} />
```

In `frontend/src/App.jsx`, pass it through:

```jsx
            traces={chat.traces}
```

- [ ] **Step 6: Style it**

Append to `frontend/src/theme.css`:

```css
/* --- trace -------------------------------------------------------------- */
.trace { margin-top: 0.6rem; font-size: 0.82rem; }
.trace > summary {
  cursor: pointer; color: var(--muted, #6b7280);
  list-style: none; padding: 0.15rem 0;
}
.trace > summary::marker, .trace > summary::-webkit-details-marker { display: none; }
.trace > summary::before { content: '▸ '; }
.trace[open] > summary::before { content: '▾ '; }
.trace-empty { color: #b45309; margin: 0.4rem 0; }
.trace-steps { margin-top: 0.4rem; }
.trace-round { margin-bottom: 0.5rem; }
.trace-round-label {
  text-transform: uppercase; letter-spacing: 0.04em;
  font-size: 0.7rem; color: var(--muted, #6b7280); margin-bottom: 0.2rem;
}
.trace-steps ol { list-style: none; margin: 0; padding: 0; }
.trace-step {
  border-left: 2px solid #d1d5db; padding: 0.2rem 0 0.2rem 0.6rem;
  margin-bottom: 0.3rem;
}
.trace-step.model { border-left-color: #c7d2fe; }
.trace-step.failed { border-left-color: #ef4444; }
.trace-step-head { display: flex; justify-content: space-between; gap: 1rem; }
.trace-step-name { font-family: ui-monospace, monospace; }
.trace-step-ms { color: var(--muted, #6b7280); font-variant-numeric: tabular-nums; }
.trace-step-args { color: var(--muted, #6b7280); font-family: ui-monospace, monospace; }
.trace-step-error { color: #b91c1c; }
.trace-raw > summary { cursor: pointer; color: var(--muted, #6b7280); }
.trace-raw pre {
  max-height: 14rem; overflow: auto; background: rgba(0, 0, 0, 0.04);
  padding: 0.4rem; border-radius: 4px; font-size: 0.75rem;
}
```

- [ ] **Step 7: Replace the stale debug-panel documentation**

`backend/TESTS.md:17-32` documents a `(debug)` panel that no longer exists in
`frontend/src/components/`. Replace that whole "Seeing what actually ran" section
with:

```markdown
## Seeing what actually ran

Every answer carries a collapsed trace line beneath it — `3 signals · 2 rounds ·
4.2s`. Click it for the tools that ran, in rounds, with their arguments, their
durations and their raw JSON (behind a second `raw` toggle).

It is read from the server's record of the turn, not from the model — asking the
model what it used lets it misremember or invent a call it never made.

**`No signal was measured` is the finding to watch for.** It means the answer
came from training knowledge, not your data. That's what produced the bad "best
airports in the US" answer: confident prose, zero measurements.

Past turns, including failed ones, are at `/#traces?key=...` when `TRACE_KEY` is
set. See the tracing section of the README.
```

Also update the demo-sequence table's last row, which says `(debug)`:

```markdown
| + | Is SFO growing but losing ground? | `get_growth` + `get_national_rank` | curve + scale; open the trace line for the raw calls |
```

And the sentence below the table that reads "the same `trace` the debug panel shows" — change "the debug panel" to "the trace line".

- [ ] **Step 8: Run the full frontend suite**

Run (from `frontend/`): `npm test`
Expected: PASS — `ChatColumn.test.jsx` and `App.test.jsx` must still be green

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/TraceDisclosure.jsx frontend/src/components/ChatColumn.jsx frontend/src/App.jsx frontend/src/theme.css frontend/src/__tests__/TraceDisclosure.test.jsx backend/TESTS.md
git commit -m "feat(frontend): collapsed per-answer trace disclosure"
```

---

### Task 9: The debug page

**Files:**
- Create: `frontend/src/components/TracesPage.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/theme.css` (append)
- Modify: `README.md`
- Test: `frontend/src/__tests__/TracesPage.test.jsx`

**Interfaces:**
- Consumes: `fetchTraces`, `fetchTrace` (Task 6); `TraceSteps` (Task 7).
- Produces: `<TracesPage traceKey="..." />`, reached at `/#traces?key=...`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/TracesPage.test.jsx`:

```jsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TracesPage from '../components/TracesPage'
import { fetchTrace, fetchTraces } from '../api/chat'

vi.mock('../api/chat', () => ({
  fetchTraces: vi.fn(),
  fetchTrace: vi.fn(),
}))

const SUMMARIES = {
  traces: [
    { id: 't2', ts: '2026-08-15T12:00:00.000Z', question: 'Is LAX growing?',
      answer: 'Yes, 3.9% a year.', latency_ms: 4210, error: null, step_count: 2 },
    { id: 't1', ts: '2026-08-15T11:00:00.000Z', question: 'How congested is SFO?',
      answer: 'About 81% full.', latency_ms: 3050, error: null, step_count: 2 },
  ],
}

describe('TracesPage', () => {
  beforeEach(() => {
    fetchTraces.mockReset()
    fetchTrace.mockReset()
  })

  it('lists past turns newest first', async () => {
    fetchTraces.mockResolvedValue(SUMMARIES)
    render(<TracesPage traceKey="s3cret" />)

    await waitFor(() => expect(screen.getByText('Is LAX growing?')).toBeInTheDocument())
    expect(screen.getByText('How congested is SFO?')).toBeInTheDocument()
    expect(fetchTraces).toHaveBeenCalledWith('s3cret', { limit: 50, offset: 0 })
  })

  it('loads one turn in full when a row is opened', async () => {
    fetchTraces.mockResolvedValue(SUMMARIES)
    fetchTrace.mockResolvedValue({
      id: 't2', latency_ms: 4210, error: null,
      steps: [{ kind: 'tool', round: 1, ms: 1810, name: 'get_growth',
                args: { airport: 'LAX' }, result: { cagr: 3.9 }, error: null }],
    })
    render(<TracesPage traceKey="s3cret" />)

    await waitFor(() => expect(screen.getByText('Is LAX growing?')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Is LAX growing?'))

    await waitFor(() => expect(screen.getByText('get_growth')).toBeInTheDocument())
    expect(fetchTrace).toHaveBeenCalledWith('s3cret', 't2')
  })

  it('explains a rejected key instead of showing an empty list', async () => {
    fetchTraces.mockRejectedValue(new Error('No traces here — check the key in the URL.'))
    render(<TracesPage traceKey="wrong" />)

    await waitFor(() =>
      expect(screen.getByText(/check the key in the URL/)).toBeInTheDocument())
  })

  it('asks for a key when the URL has none', async () => {
    render(<TracesPage traceKey="" />)

    expect(screen.getByText(/add \?key=/i)).toBeInTheDocument()
    expect(fetchTraces).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/__tests__/TracesPage.test.jsx`
Expected: FAIL — cannot resolve `../components/TracesPage`

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/TracesPage.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { fetchTrace, fetchTraces } from '../api/chat'
import TraceSteps from './TraceSteps'

// Past turns, across sessions. Reached at /#traces?key=... — see App.jsx for why
// this is a hash route rather than a real one.

export default function TracesPage({ traceKey }) {
  const [rows, setRows] = useState([])
  const [openId, setOpenId] = useState(null)
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!traceKey) return
    let live = true
    fetchTraces(traceKey, { limit: 50, offset: 0 })
      .then((body) => { if (live) setRows(body.traces || []) })
      .catch((e) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [traceKey])

  const show = (id) => {
    if (openId === id) { setOpenId(null); setOpen(null); return }
    setOpenId(id)
    setOpen(null)
    fetchTrace(traceKey, id).then(setOpen).catch((e) => setError(e.message))
  }

  if (!traceKey) {
    return (
      <div className="traces-page">
        <h1>Traces</h1>
        <p className="trace-empty">
          Add ?key=… to the address (after the #) to read stored traces.
        </p>
      </div>
    )
  }

  return (
    <div className="traces-page">
      <h1>Traces</h1>
      {error && <p className="trace-step-error">{error}</p>}
      {!error && !rows.length && <p className="trace-empty">No turns recorded yet.</p>}
      <ol className="traces-list">
        {rows.map((row) => (
          <li key={row.id} className={row.error ? 'traces-row failed' : 'traces-row'}>
            <button type="button" className="traces-row-head" onClick={() => show(row.id)}>
              <span className="traces-question">{row.question}</span>
              <span className="traces-meta">
                {row.step_count} steps · {((row.latency_ms || 0) / 1000).toFixed(1)}s
                {' · '}{row.ts.slice(0, 19).replace('T', ' ')}
              </span>
            </button>
            {row.error && <div className="trace-step-error">{row.error}</div>}
            {openId === row.id && open && (
              <div className="traces-detail">
                <p className="traces-answer">{open.answer}</p>
                <TraceSteps steps={open.steps} />
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/__tests__/TracesPage.test.jsx`
Expected: PASS — 4 passed

- [ ] **Step 5: Route to it from App**

In `frontend/src/App.jsx`, add the import and a hash-route hook. Add to the imports:

```jsx
import { useEffect, useState } from 'react'
import TracesPage from './components/TracesPage'
```

(the `useState` import already exists — extend it with `useEffect`.)

Add above `export default function App()`:

```jsx
// A hash route, not a real one, and not a router dependency. FastAPI serves the
// build through StaticFiles(html=True), which does NOT fall back to index.html
// for unknown paths — so /traces would 404 on refresh without a server-side
// catch-all. The fragment buys a second property worth having: browsers never
// transmit it, so a key pasted into /#traces?key=... stays out of the server's
// access logs.
function useHash() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return hash
}

function keyFromHash(hash) {
  const query = hash.indexOf('?')
  if (query === -1) return ''
  return new URLSearchParams(hash.slice(query + 1)).get('key') || ''
}
```

And at the top of the `App` body, before `const chat = useChat()`:

```jsx
  const hash = useHash()
```

Then immediately after the hooks (all hooks must run unconditionally, so this
guard goes below them, above the `return`):

```jsx
  if (hash.startsWith('#traces')) return <TracesPage traceKey={keyFromHash(hash)} />
```

Place it after the `useSpeech` call so no hook is skipped between renders.

- [ ] **Step 6: Style it**

Append to `frontend/src/theme.css`:

```css
/* --- traces page -------------------------------------------------------- */
.traces-page { max-width: 52rem; margin: 0 auto; padding: 2rem 1rem; }
.traces-page h1 { font-size: 1.2rem; margin-bottom: 1rem; }
.traces-list { list-style: none; margin: 0; padding: 0; }
.traces-row { border-bottom: 1px solid #e5e7eb; padding: 0.5rem 0; }
.traces-row.failed { border-left: 2px solid #ef4444; padding-left: 0.6rem; }
.traces-row-head {
  display: flex; flex-direction: column; gap: 0.15rem; width: 100%;
  background: none; border: 0; padding: 0; text-align: left; cursor: pointer;
  font: inherit; color: inherit;
}
.traces-question { font-weight: 600; }
.traces-meta { font-size: 0.78rem; color: var(--muted, #6b7280); }
.traces-answer { margin: 0.5rem 0; color: var(--muted, #6b7280); }
.traces-detail { padding: 0.5rem 0 0.2rem; }
```

- [ ] **Step 7: Document it**

Add to `README.md`, in a new `## Tracing` section:

```markdown
## Tracing

Every turn is recorded: the tools the agent chose, the arguments it chose them
with, what each returned, and how long each took. Scoring stays deterministic
code — the trace shows which signals ran, never a model's account of itself.

Each answer carries a collapsed line beneath it (`3 signals · 2 rounds · 4.2s`)
that expands into the step list.

Turns are also written to SQLite and readable across sessions:

| Env var | Default | Effect |
|---|---|---|
| `TRACE_DB` | `traces.db` | Where the table lives |
| `TRACE_MAX_ROWS` | `2000` | Oldest rows are dropped past this |
| `TRACE_KEY` | unset | Enables the read API and `/#traces` |

With `TRACE_KEY` set, past turns are at `/#traces?key=<your key>`. **Without it
the read routes are not registered at all**, so a fresh checkout exposes
nothing. The key sits in the URL fragment, which browsers do not send to the
server — it stays out of access logs. This is a demo-grade guard, not
authentication.

Two sinks record each turn on purpose: the SQLite table, and one JSON line per
turn on stdout. Render's free tier wipes the disk on redeploy, so the log stream
is what survives when the database does not.

Note that traces are stored server-side. The chat itself remains stateless — the
browser holds its own history — but the trace table does retain every question
asked of a deployed instance, bounded by `TRACE_MAX_ROWS`.
```

- [ ] **Step 8: Run both suites**

Run (from `frontend/`): `npm test`
Run (from repo root): `python -m pytest -v`
Expected: PASS — both fully green

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/TracesPage.jsx frontend/src/App.jsx frontend/src/theme.css frontend/src/__tests__/TracesPage.test.jsx README.md
git commit -m "feat(frontend): hash-routed traces page for past turns"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Trace record shape | 1 (recorder fields), 4 (`make_record`, wire types) |
| Model + tool steps, per-step and top-level `error` | 1, 2 |
| `backend/recorder.py`, `Recorder` / `NULL` | 1 |
| Three call sites in `agent.py` | 2 |
| `conversation_factory` keeps zero-arg contract | 4 |
| Partial trace from the exception handler | 4 |
| SQLite schema, no secondary index, WAL, busy timeout | 3 |
| Per-call connections, rowid retention | 3 |
| `TRACE_DB` / `TRACE_MAX_ROWS` / `TRACE_KEY` | 3, 5, 9 (docs) |
| `tracing.py` docstring amendment | 3 |
| `/api/traces` gated, 404 not 403, unregistered when unset | 5 |
| `TraceDisclosure`, collapsed, nested raw toggle | 7, 8 |
| `useChat` traces map, never in `llmHistory` | 6 |
| `/#traces` hash route, key from fragment | 9 |
| Shared step-list component | 7 |
| All six load-bearing tests | 2 (×2), 3 (×2), 4, 5, 6 |

No gaps.

**Placeholder scan:** No TBDs, no "add error handling", no "similar to Task N". Every code step carries the actual code.

**Type consistency checked:**
- `Recorder.step(kind, **fields)` / `Step.set(**fields)` — consistent across Tasks 1, 2, 4.
- `make_record(question, answer, model, steps, latency_ms, error=None)` — same signature in Tasks 3, 4.
- `recent()` returns `step_count`; consumed under that name in Tasks 5 and 9.
- `fetchTraces(key, {limit, offset})` / `fetchTrace(key, id)` — defined Task 6, consumed Task 9.
- `TraceSteps({ steps })` — defined Task 7, consumed Tasks 8 and 9.
- Step field names `kind`/`round`/`ms`/`name`/`args`/`result`/`error`/`text`/`calls` — identical in the recorder (1), the schema (4), and both components (7, 8).

**One deviation from the spec, recorded here:** the table carries a `step_count`
column the spec's schema did not name, written at insert time and returned by
`recent()`. The list view needs the number, and recomputing it would mean reading
back every `steps` blob — defeating the whole point of excluding that column from
the summary query. Denormalised deliberately; `steps` is immutable once written,
so the two cannot drift.
