# Airport Investment Intelligence Agent

An LLM agent that answers one question: **where in the US would a terminal
renovation actually pay off?** Ask in plain English — by typing or by voice —
and the agent picks which analysis to run, queries live BTS data, and answers
with a chart drawn from the numbers it actually measured.

## Run it locally

Put your key in a `.env` file in the project root (gitignored, loaded
automatically via `python-dotenv`):

```
ANTHROPIC_API_KEY=sk-ant-...
```

macOS / Linux:

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
./run.sh                 # API on :5001, app on http://localhost:5173
```

Windows (PowerShell) — `run.sh` is bash-only; use the PowerShell twin. Run it
from a terminal, not by double-clicking:

```powershell
pip install -r requirements.txt
cd frontend; npm install; cd ..
.\run.ps1                # API on :5001, app on http://localhost:5173
```

If scripts are blocked by the execution policy, use
`powershell -ExecutionPolicy Bypass -File .\run.ps1`. To start the two
processes by hand instead, run `python -m uvicorn server.app:app --port 5001
--reload` in one terminal and `cd frontend; npm run dev` in another.

## Layout

```
backend/     the agent: conversation loop, six tools, KPI calculations (pure)
             llm.py is the only file that talks to a model provider (Claude)
server/      FastAPI: POST /chat, GET /health, serves the built frontend
frontend/    React + Vite dashboard: chat, voice input, Recharts charts
docs/        design spec, implementation plan, voice test checklist
```

## How it fits together

The browser holds the conversation and replays it each turn, so the server is
stateless — any process can answer any request, and a restart never wipes a
session mid-demo. `POST /chat` returns three things: the answer, the raw JSON
each tool returned, and the updated history.

Charts render **from that tool JSON, never from the answer text**. A chart is a
second claim about the data, and when a chart and a sentence disagree the reader
believes the chart — so nothing in the rendering parses prose.

Scoring and ranking are deterministic Python (`backend/kpis.py`). The model's
judgement is in *which* tool to call, *which* airport codes to use ("New
England" → BOS, BDL, PVD, MHT), and *how* to explain the result.

## Voice

Voice is **input only**, using the browser's built-in speech recognition — no
audio reaches the server. Dictation fills the input box and stops there: you
press Send. That review step is deliberate, because recognition mishears
airport codes. The mic button is hidden in browsers without support (Firefox).
See `docs/VOICE-MANUAL-TESTS.md`.

## Tests

```bash
python3 -m pytest              # server: sanitize, charts, tracing, /chat, static
cd frontend && npm test        # UI: chat state, composer, voice, charts
python3 backend/selftest.py    # 54 invariant checks against live BTS (no key needed)
```

On Windows, replace `python3` with `python` and swap `&&` for `;` in PowerShell.

`backend/selftest.py` asserts invariants, not fixed numbers — BTS adds a month
at a time, so hardcoded values would rot.

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

## What this cannot answer

Four raw BTS columns cannot produce delays, terminal/gate capacity, fares, or
route-level detail. The agent refuses those rather than reaching for the nearest
tool. Load factor measures how full the *aircraft* are — an airline decision —
not how full the building is; it is the closest proxy the data offers and the
biggest caveat in the model.
