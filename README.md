# Airport Investment Intelligence Agent

An LLM agent that answers one question: **where in the US would a terminal
renovation actually pay off?** Ask in plain English — by typing or by voice —
and the agent picks which analysis to run, queries live BTS data, and answers
with a chart drawn from the numbers it actually measured.

## Run it locally

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
export OPENAI_API_KEY=...
./run.sh                 # API on :5001, app on http://localhost:5173
```

## Layout

```
backend/     the agent: conversation loop, five tools, KPI calculations (pure)
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

`backend/selftest.py` asserts invariants, not fixed numbers — BTS adds a month
at a time, so hardcoded values would rot.

## Tracing

Every `/chat` call emits one JSON line on stdout (question, tools called, tool
results, answer, latency), visible in Render's log viewer. It all goes through
`trace()` in `server/tracing.py`, so switching to SQLite or a hosted tracing
service is a one-function change. Render's free disk is ephemeral, which is why
the default sink is stdout and not a file.

## What this cannot answer

Four raw BTS columns cannot produce delays, terminal/gate capacity, fares, or
route-level detail. The agent refuses those rather than reaching for the nearest
tool. Load factor measures how full the *aircraft* are — an airline decision —
not how full the building is; it is the closest proxy the data offers and the
biggest caveat in the model.
