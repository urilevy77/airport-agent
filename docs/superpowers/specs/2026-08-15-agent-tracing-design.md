# Agent tracing — design

Full tracing for the Airport Investment Intelligence Agent: capture what the
agent did on every turn, persist it, and show it in two places — inline under
each answer, and on a protected cross-session debug page.

## Goal

An analyst reading an answer can see which signals ran, with which arguments,
in what order, and how long each took. A developer can look back at past turns —
including failed ones — without redeploying or scraping logs.

## What exists today

- `server/tracing.py` writes one JSON line per event to stdout. Render captures
  it; a redeploy loses it.
- `server/charts.py:16` already reconstructs `{tool, args, data}` per dispatched
  call, in call order, read from the recorded messages rather than asked of the
  model. This ships to the browser on every turn as `ChatResponse.charts`.
- `backend/agent.py` runs the loop: up to `MAX_ROUNDS` (5) iterations, each one
  model call plus zero or more tool calls.
- No timing data exists anywhere per call, and nothing is persisted.

## Decisions

**Not Langfuse.** The requirement is to render traces in *this* app's React UI,
which means reading them back out. Langfuse's strength is its own dashboard;
using it here would mean instrumenting the same seams anyway, plus an SDK, an
account, a network hop, and querying their API back for our own UI. Owning one
SQLite table is less code than integrating Langfuse *and* reading from it.

**Instrument the loop; don't reconstruct after the fact.** Tool names,
arguments, results and round boundaries are all recoverable from the message
list — `charts.py` proves it. Durations are not: nothing writes them down. The
tools hit a live Socrata endpoint with no SLA, so "which step was slow" is the
question a trace most needs to answer here. Reconstruction would also drift
silently if the loop's shape ever changed.

**Cost accepted:** `backend/agent.py` gains a second concern. Held to one
optional constructor argument with a null-object default, so the CLI, the REPL
and `run()` are unaffected and `backend/` still runs standalone.

**Reasoning means tool choices, not thinking blocks.** `llm.py` passes no
`thinking` parameter, so extended thinking is off and no thinking blocks are
produced. The trace shows what the model *did* — tools chosen, arguments chosen,
interstitial text — which is a real decision trace. We do not ask the model to
narrate its own rationale; that is self-report, not reasoning, and presenting it
as reasoning would be dishonest.

**SQLite, best-effort.** Stdlib `sqlite3`, no new dependency. Survives restarts
locally; resets on Render free-tier redeploys. The stdout JSONL sink stays as
the durable backstop.

## Data model

One record per turn (per `/chat` call). A flat, ordered step list, not a nested
span tree: the loop is genuinely flat (≤5 rounds, each one model call plus tool
calls), so a `round` integer per step reproduces the grouping and keeps the
stored JSON readable by eye.

```json
{
  "id": "uuid4",
  "ts": "2026-08-15T12:34:56.789Z",
  "model": "claude-opus-5",
  "question": "Compare LA and Santa Ana congestion",
  "answer": "LAX has the stronger congestion signal ...",
  "latency_ms": 4210,
  "error": null,
  "steps": [
    {"kind": "model", "round": 1, "ms": 1240, "text": "",
     "calls": ["congestion_signal", "congestion_signal"]},
    {"kind": "tool", "round": 1, "ms": 1810, "name": "congestion_signal",
     "args": {"airport": "LAX", "months": 24},
     "result": {"score": 0.81}, "error": null}
  ]
}
```

Model steps are recorded as well as tool steps so the UI can split model latency
from BTS latency. That split is the main thing the timings buy.

`error` appears in two places deliberately:

- **per-step** — a tool that failed but the loop recovered from. `agent.py:40`
  turns tool exceptions into `{"error": ...}` the model reads and continues
  past, so a successful turn can legitimately contain failed steps.
- **top-level** — the turn itself died.

## Backend instrumentation

### New: `backend/recorder.py`

Two objects sharing one interface:

- `Recorder` — `start_round()` bumps a counter. `step(kind, **fields)` is a
  context manager that times the block and appends on exit. It catches nothing
  from the wrapped block (exceptions propagate to the loop's own handling) but
  swallows any error of its own: a trace must never break a request, the rule
  `server/tracing.py:19` already sets.
- `NULL` — module-level null object, same methods, does nothing.

### Changed: `backend/agent.py`

Exactly three call sites:

1. `__init__(self, model=None, recorder=None)` → `self.recorder = recorder or NULL`
2. `ask()` — `start_round()` at the top of each loop iteration; each
   `call_tool(call)` wrapped in `self.recorder.step("tool", ...)`
3. `_next_message()` — `self.client.complete(...)` wrapped in
   `self.recorder.step("model", ...)`

`call_tool` keeps its current signature and body. Timing wraps it from `ask()`,
where the recorder already lives, so the tool-dispatch guard stays as written.

### Changed: `server/app.py`

`conversation_factory()` keeps its zero-argument contract — existing test doubles
in `tests/conftest.py` continue to work unchanged. The server constructs a
`Recorder` and assigns `convo.recorder` after construction.

Because `app.py` holds the recorder reference before calling `ask()`, the
existing `except` at `app.py:80` can write a trace row containing every step
that completed before the failure. Today that path logs only the exception
message.

The trace is added to `ChatResponse` as a `trace` field, alongside `charts`.

## Storage

### New: `server/trace_store.py`

```sql
CREATE TABLE IF NOT EXISTS traces (
  id TEXT PRIMARY KEY, ts TEXT NOT NULL, model TEXT,
  question TEXT, answer TEXT, latency_ms INTEGER, error TEXT,
  steps TEXT NOT NULL           -- the step list, as JSON
);
```

No secondary index. Every read is "newest first", which is a reverse scan of the
implicit `rowid` — already ordered, and the table is capped at a few thousand
rows.

Steps are a JSON blob, not a child table. A child table would enable SQL
aggregates like "average duration of `congestion_signal`", but nothing in scope
asks for that — both surfaces load a whole trace and render it — and one table
means no join and no migration when a step gains a field.

Four functions:

- `init()` — create table, set `journal_mode=WAL` and `busy_timeout=5000`
- `write(record)` — insert, then retention delete
- `recent(limit, offset)` — summaries **without** the `steps` column, newest
  first, so the list view doesn't drag every BTS payload across the wire
- `get(id)` — one full record

A fresh connection per call: `sqlite3` connections have thread affinity and
FastAPI runs sync endpoints in a threadpool. Per-call connections sidestep that
entirely at this volume.

Retention: delete all but the newest `TRACE_MAX_ROWS` rows on insert, ordered by
`rowid` **not** `ts` — timestamps can collide at millisecond resolution, rowids
cannot. This doubles as the retention policy: the server now remembers every
question anyone asks the deployed demo, and the cap bounds that.

Every write is wrapped so a failure degrades to the existing stdout JSONL and
never touches the response.

`server/tracing.py`'s docstring is amended to record that two sinks for the same
event is deliberate — the log stream survives the redeploys that wipe the SQLite
file, so the duplication *is* the free-tier durability story — and must not be
"cleaned up".

### Configuration

| Env var | Default | Effect |
|---|---|---|
| `TRACE_DB` | `traces.db` in repo root | SQLite file path |
| `TRACE_MAX_ROWS` | `2000` | Retention cap |
| `TRACE_KEY` | unset | Gates the read API; **unset means the read routes are not registered at all** |

## Read API

Registered **only** when `TRACE_KEY` is set, so a fresh checkout exposes nothing
by default.

- `GET /api/traces?limit=&offset=` → summaries, newest first
- `GET /api/traces/{id}` → one full trace

The key arrives as an `X-Trace-Key` header and is compared with
`hmac.compare_digest`. A mismatch returns **404, not 403**, so a prober cannot
distinguish "wrong key" from "no such route".

The `/api` prefix matters: `"/"` is a `StaticFiles` mount (`app.py:108`), and
keeping the API namespace distinct leaves `/traces` free for the UI.

### Why this needs a guard at all

The app is currently stateless by design — "no visitor can see another's
conversation" (`server/app.py:3`) is true because nothing is stored, not because
anything checks. Persisting traces ends that, so the property now has to be
defended deliberately. The inline surface is safe by construction (a trace rides
back in the same response as the answer the requester asked for). The debug view
is the exposure: by design it returns rows the requester did not create.

This is a demo-grade guard, not authentication.

## Frontend

### Inline: `TraceDisclosure.jsx`

Renders under an agent bubble. Collapsed by default to a summary line
(`3 signals · 2 rounds · 4.2s`); expands to the grouped step list:

```
v 3 signals · 2 rounds · 4.2s

  Round 1
  * congestion_signal        1.8s
    airport=LAX  months=24
    -> score 0.81 · 412k ops
  * congestion_signal        1.7s
    airport=SNA  months=24
    -> score 0.44 · 91k ops

  Round 2
  * capacity_signal          0.6s
    airport=LAX  months=24
    -> load_factor 0.84
```

Tool results render as a one-line summary with raw JSON behind a second, nested
toggle. The full BTS payload is exactly what you want when debugging and exactly
what you don't want unfurling into the chat by default.

### `useChat.js`

Gains a `traces` map keyed by the answer's message id, populated from
`body.trace`, held in React state alongside `charts`.

**The trace must never enter `llmHistory`.** That ref is replayed to the server
every turn (`useChat.js:27`), so a trace inside it would be re-uploaded
quadratically across a session *and* become model input, letting the agent read
its own timings. One-line mistake, silent and expensive failure mode.

### Debug page: `/#traces`

A hash route — no router dependency. Not laziness: `StaticFiles(html=True)` does
not serve `index.html` for unknown paths, so a real path route would 404 on
refresh and need a server-side catch-all to fix.

The hash buys a second property: the fragment is never transmitted to the
server, so a key pasted into `/#traces?key=...` stays out of Render's access
logs — the main weakness of a URL-borne token. The page reads the key from the
hash and sends it as `X-Trace-Key`.

The page lists recent turns and expands one into full detail, reusing the same
step-list component as the inline panel. That shared component is why these are
one piece of work rather than two.

## Testing

Follows the existing split: `tests/` for the server, `backend/TESTS.md`
conventions for the agent.

Load-bearing:

- **`NULL` recorder leaves `Conversation` behavior identical** (fake client).
  This is the entire justification for accepting the coupling in `agent.py`; if
  it isn't tested it isn't true.
- **A failing tool still produces a recorded step, and the turn still
  succeeds** — the recovery path at `agent.py:40` is easy to break while
  wrapping it.
- **A raised `ask()` writes a partial trace** — the benefit that motivated
  holding the recorder in `app.py`.
- **`useChat` keeps the trace out of `llmHistory`.**
- **`/api/traces` is absent without `TRACE_KEY`, 404s on a wrong one** — fails
  closed.
- **An unwritable or corrupt DB does not break `/chat`** — the premise of a
  best-effort sink.

Ordinary: store round-trip, retention cap, recorder rounds and timings,
disclosure collapsed-then-expanded, summaries exclude `steps`.

## Out of scope

- Extended thinking / thinking blocks (would change model config, cost and
  latency on every turn)
- Token counts and cost accounting
- Streaming traces mid-turn — the trace arrives with the answer
- Aggregate analytics over traces (p50 latency, tool frequency)
- Real authentication for the debug page
