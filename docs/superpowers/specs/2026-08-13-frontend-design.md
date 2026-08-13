# Frontend Design — Airport Investment Intelligence Agent

**Date:** 2026-08-13
**Status:** Approved in brainstorming; awaiting implementation plan.

## Goal

A deployed web frontend for the existing Python agent in `backend/`: a
clean, professional dashboard with a chat interface, voice input, and
per-answer charts drawn from real tool data. One Render service, one URL,
same hosting shape as the previous app.

## Decisions (agreed with the user)

- **Voice:** input only, via the browser Web Speech API. No spoken replies.
- **STT:** browser-native (no audio touches the server). Mic hidden where
  unsupported (Firefox); typing always works.
- **Answers:** arrive whole (no token streaming); a status line shows which
  tools are running while the user waits.
- **Charts:** one per tool that ran, rendered from the tool's returned JSON,
  never from answer text.
- **Chat history:** held by the browser and resent each turn; the server is
  stateless.
- **Tracing:** every `/chat` call logged server-side as one structured JSON
  record via a single `trace()` function (stdout → Render log viewer;
  swappable later for SQLite or a hosted service).
- **Look:** clean professional dashboard — light, data-forward, fintech-report
  feel.
- **Deployment:** Render, single service; FastAPI serves both API and the
  built React app.

## Architecture

```
airport-agent/
  backend/     existing agent (agent.py, tools.py, kpis.py, bts.py, prompts.py) — unchanged
  server/      NEW: FastAPI app — POST /chat, GET /health, serves frontend build
  frontend/    NEW: React app (Vite + Recharts)
  render.yaml  NEW: build (npm run build + pip install) and run config
```

Request flow: browser sends `{history, question}` → FastAPI wraps the
existing agent loop → agent picks tools, queries BTS, writes the answer →
server returns `{answer, charts, history}` → browser stores history, renders
answer + charts.

The agent code in `backend/` is reused as-is; the server is a thin wrapper.
No changes to agent logic, tools, or KPI functions.

## API contract

`POST /chat`

Request:
```json
{ "history": [ ... prior messages, empty on first turn ... ],
  "question": "Is JFK congested?" }
```

Response:
```json
{ "answer": "JFK's load factor averaged 84%...",
  "charts": [ { "tool": "congestion",
                "args": { "airport": "JFK" },
                "data": { ... tool's untouched JSON ... } } ],
  "history": [ ... updated full history ... ] }
```

- `charts`: one entry per tool the agent ran; empty when no tools ran.
- Errors: proper HTTP error codes with a human-readable message; the
  frontend shows them as a system bubble. History survives because the
  browser holds it.
- `GET /health`: liveness for Render.
- Static: the React build served at `/`.

Three routes total.

## Tracing

One structured JSON record per `/chat` call: timestamp, question, tools
called with arguments, tool results (or errors), final answer, latency.
Emitted by a single `trace()` function so the sink can later change from
stdout to SQLite or a hosted tracing service without touching the app.
Note: Render free-tier disk is ephemeral — that is why stdout, not SQLite,
is the deployed sink.

## UI layout

Single page, two columns on desktop:

- **Header:** app name, About link.
- **Left — chat column:** user/agent bubbles. Answers that ran tools show
  chips ("Congestion · JFK"); clicking a chip shows that chart in the right
  panel. Newest answer's chart auto-selects.
- **Right — chart panel:** one large chart at a time with a caption (what it
  measures, which airport, date range). On mobile the panel collapses and
  charts render inline under each answer.
- **Composer (bottom):** text input, mic button, Send. Input locks while the
  agent works; a status line reports actual tool activity ("running
  congestion for JFK…").
- **Empty state:** a few suggested starter questions.
- **Style:** light theme, white/neutral surfaces, one accent color, generous
  spacing, tabular numbers. No chatbot-toy styling.

## Voice input behavior

- Tap mic → pulsing/recording state; first use triggers the browser mic
  permission prompt; live transcription streams into the input box.
- Stop talking → final text sits in the input; **user reviews and presses
  Send** (no auto-send — speech recognition mishears airport codes).
- Tap mic while listening → cancel. Re-tap to re-dictate.
- No speech support detected → mic button hidden entirely.
- Permission denied → small hint ("microphone blocked — check browser
  settings"); typing unaffected.

## Charts

| Tool | Chart |
|---|---|
| Congestion | Monthly load-factor columns, last 12 months, threshold band lines |
| Growth | Passenger curve by year, 2019 pre-COVID level marked |
| Candidate ranking | Horizontal ranked bars per airport, scores labeled |
| Traffic mix | Split bars: domestic vs international share, avg trip distance |
| National rank | Position on a log scale across all ~1,300 airports |

Rules:
- Data source is the tool's returned JSON only.
- Every chart carries a caption sufficient for a standalone screenshot.
- Recharts, styled to the dashboard (one accent color, muted grid, tabular
  numbers).
- Tool error → error message in the chart panel, never an empty/partial chart.

## Error handling

- **BTS down/slow:** tool errors already become `{"error": ...}` the model
  explains; full request failure → system bubble with retry; the typed
  question stays in the composer.
- **LLM API errors:** clean HTTP error, honest UI message, trace record.
- **Render cold start:** first request shows "waking the server up…".

## Testing

1. **Data logic:** existing `backend/selftest.py` invariant checks remain the
   source of truth. Untouched.
2. **API:** pytest + FastAPI test client — response shape, error codes,
   history round-trip. LLM faked; fast and free.
3. **Frontend:** Vitest component tests — message rendering, chip → chart
   selection, composer lock state, mic hidden without speech support.
   Voice recognition itself: manual checklist (real mic, real browsers).

## Out of scope

- Spoken replies / realtime voice conversation.
- Server-side sessions or a database for chat memory.
- Whisper or any server-side STT.
- Token streaming.
- Auth, multi-user accounts.
