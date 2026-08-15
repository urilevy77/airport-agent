# Airport Investment Intelligence Agent

An LLM agent that answers one question: **where in the US would a terminal
renovation actually pay off?** Ask in plain English — by typing or by voice —
and the agent picks which analysis to run, queries live BTS data, and answers
with a chart drawn from the numbers it actually measured.

**[Web APP]: https://airport-agent-if0p.onrender.com/**
📐 **[Architecture](https://claude.ai/code/artifact/05598eeb-a8ff-4112-a7f2-b82da83f6755)** —
one page: how a question becomes a measured answer, the six tools, and the
single table underneath them.

## What you can ask

Six signals, one table. The model's job is picking which one to run and on
which airports — never computing the result.

| Signal | Ask it | What comes back |
|---|---|---|
| `get_congestion` | *"How congested is JFK?"* | Load factor over recent months, plus the monthly series behind the average |
| `get_growth` | *"Is Austin growing, and has it recovered past 2019?"* | Yearly passenger growth, recovery vs. 2019, whether growth is speeding up, seats vs. demand |
| `find_candidates` | *"Which US airports should we invest in?"* | Searches and ranks all ~1,500 US airports — used when you name none |
| `get_candidate` | *"Compare BOS, PVD and BDL as expansion candidates."* | Scores the airports you did name, against the same national population |
| `get_traffic_mix` | *"What kind of traffic does Miami have?"* | International share and trip length → customs halls vs. domestic gates |
| `get_national_rank` | *"Is Nashville a major airport, and is it climbing?"* | Rank among all ~1,300 US airports, and how it moved over ten years |

Signals 1/2/3/5 answer **whether** to build; `get_traffic_mix` answers **what**
to build. Follow-ups work — the conversation carries, so *"and how does that
compare to Providence?"* resolves against the previous turn.

## Run it locally

Put your key in a `.env` file in the project root (gitignored, loaded
automatically via `python-dotenv`):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Windows (PowerShell) — run it from a terminal, not by double-clicking:

```powershell
pip install -r requirements.txt
cd frontend; npm install; cd ..
.\run.ps1                # API on :5001, app on http://localhost:5173
```

If scripts are blocked by the execution policy, use
`powershell -ExecutionPolicy Bypass -File .\run.ps1`. To start the two
processes by hand instead, run `python -m uvicorn server.app:app --port 5001
--reload` in one terminal and `cd frontend; npm run dev` in another.

There is also a terminal client, if you want the agent without the UI:

```powershell
python backend/agent.py "Compare LA and Santa Ana congestion"
python backend/agent.py             # interactive
```

## Layout

```
backend/     the agent: conversation loop, six tools, KPI calculations (pure)
             agent.py   the loop and the memory — nothing else
             tools.py   the six tools + the schemas that do the routing
             kpis.py    all scoring; pure functions, rows in / dict out
             bts.py     the only module that queries BTS, cached by URL
             prompts.py the system prompt, rebuilt per request
             llm.py     the only file that talks to a model provider (Claude)
server/      FastAPI: POST /chat, POST /export, GET /config, GET /health,
             key-gated GET /api/traces, and it serves the built frontend
             docx_export.py lays a conversation out as Word — no domain logic
frontend/    React + Vite dashboard: chat, voice input, Recharts charts
             session.js the conversation, kept in localStorage
             export/    chart capture and the document payload builder
```

## How it fits together

The browser holds the conversation and replays it each turn, so the server is
stateless — any process can answer any request, and a restart never wipes a
session mid-demo. `POST /chat` returns three things: the answer, the raw JSON
each tool returned, and the updated history.

That same history is mirrored to `localStorage` (`frontend/src/session.js`), so
a refresh resumes the conversation without the server storing anyone's chat. If
the browser quota is hit, the ten most recent turns are kept and the rest is
dropped on a turn boundary — a half-turn history is what the model API rejects.

Charts render **from that tool JSON, never from the answer text**. A chart is a
second claim about the data, and when a chart and a sentence disagree the reader
believes the chart — so nothing in the rendering parses prose. Answer prose
itself goes through a small hand-written Markdown subset
(`frontend/src/components/Markdown.jsx`) that emits React nodes rather than
HTML, so model output never reaches `dangerouslySetInnerHTML`.

Scoring and ranking are deterministic Python (`backend/kpis.py`). The model's
judgement is in *which* tool to call, *which* airport codes to use ("New
England" → BOS, BDL, PVD, MHT), and *how* to explain the result.

## Models

The default is `claude-sonnet-5`; override it with `ANTHROPIC_MODEL`. The UI
picker also offers Opus 5 and Haiku 4.5, with a low/medium/high effort control
on the two models that accept one — Haiku 4.5 rejects the parameter outright, so
it is offered none.

That allowlist lives in `backend/llm.py` and reaches the frontend through
`GET /config`, so the UI can never offer a model or an effort that `/chat` would
then reject. `llm.py` is the only module that knows a provider exists: everything
else speaks one flat message format, which is what lets the browser store the
history, the sanitiser validate it, and the charts read it. Swapping providers
means editing that one file.

## Voice

Voice is **input only**, using the browser's built-in speech recognition — no
audio reaches the server. Dictation fills the input box and stops there: you
press Send. That review step is deliberate, because recognition mishears
airport codes. The mic button is hidden in browsers without support (Firefox).

## Export

The Export button turns the conversation on screen into a `.docx`: each
question, its answer, and beneath it the stat tiles and charts that answer was
drawn from. The browser rasterizes its own charts to PNG and posts the whole
description to `POST /export`; `server/docx_export.py` only decides where things
sit on the page.

Two properties are deliberate. **The export is not a tool the agent can call** —
assembling the document is deterministic work, the same category as scoring, and
routing it through the model would let it re-author numbers it should only be
reporting. And **the figures come from the same `charts/stats.js` the screen
renders from**, so the document and the app cannot drift. The route touches
neither BTS nor the model, rejects payloads over its size cap with a `413`, and
a chart whose capture fails costs that one picture rather than the export.

Not every chart is an `<svg>`: the traffic mix is two CSS rectangles, so there
is nothing to photograph. Those send their shares instead and the document
redraws them as a shaded table row — which is why `docx_export.py` knows what a
proportion bar is but still nothing about airports.

## Tests

```powershell
python -m pytest               # server: sanitize, charts, tracing, /chat, /export, static
cd frontend; npm test; cd ..   # UI: chat state, session, composer, voice, charts, export
python backend/selftest.py     # 54 invariant checks against live BTS (no key needed)
```

`backend/selftest.py` asserts invariants, not fixed numbers — BTS adds a month
at a time, so hardcoded values would rot. It is also the first thing to run when
an answer looks wrong: it checks the numbers without involving the model at all,
so if it passes, the bug is in routing or the prompt.

Routing is the part a prompt edit breaks silently, and no automated test covers
it — it costs a live conversation per case. `backend/TESTS.md` is the manual
map: *question → expected tool*, with a must-not-say list per case, and it says
where a routing bug lives (a tool `description` in `tools.py`, or the routing
block in `prompts.py` — never `agent.py`). Walk it before shipping a prompt
change.

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

## Deploy

`render.yaml` defines one Render web service that serves both the API and the
React build. Two constraints are deliberate and easy to trip over:

- **One uvicorn worker.** `bts.py` caches BTS responses in-process, and a cold
  national ranking costs ~16s. Extra workers would each hold a separate cache
  and re-pay that; every request here is I/O-bound on BTS anyway, so async
  handling covers the concurrency.
- **`frontend/dist` is committed** and the build command never runs npm — the
  Python image is not guaranteed to carry a Node new enough for Vite. The cost
  is that **you must rebuild and commit `dist` after any UI change**, or the
  deployed app keeps serving the old bundle.

`ANTHROPIC_API_KEY` and `TRACE_KEY` are `sync: false`: set them in the Render
dashboard, never in git. Leaving `TRACE_KEY` unset is what keeps the trace API
off a public deployment.

## What this cannot answer

Four raw BTS columns cannot produce delays, terminal/gate capacity, fares, or
route-level detail. The agent refuses those rather than reaching for the nearest
tool. Load factor measures how full the *aircraft* are — an airline decision —
not how full the building is; it is the closest proxy the data offers and the
biggest caveat in the model.
