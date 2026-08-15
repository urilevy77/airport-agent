"""HTTP layer for the Airport Investment Intelligence Agent.

STATELESS by design: the browser keeps its own history and replays it each
turn, so no visitor can see another's conversation, any process can answer any
request, and a restart never wipes a conversation mid-demo.
"""
import hmac
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server import trace_store
from server.charts import charts_from_messages
from server.sanitize import clip_question, prepare_history
from server.schemas import ChatRequest, ChatResponse
from server.tracing import trace

DEFAULT_STATIC = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app(conversation_factory=None, static_dir=DEFAULT_STATIC):
    """Build the app. `conversation_factory` is injectable so tests can run the
    whole endpoint without an API key or a network call."""
    if conversation_factory is None:
        from server.agent_bridge import Conversation
        conversation_factory = Conversation

    from server.agent_bridge import Conversation  # noqa: F401 — puts backend/ on sys.path
    from recorder import Recorder

    app = FastAPI(title="Airport Investment Intelligence Agent")

    @app.post("/chat")
    def chat(request: ChatRequest):
        question = clip_question(request.question)
        if not question:
            return JSONResponse({"error": "Ask a question first."}, status_code=400)

        # Conversation.__init__ builds the Anthropic client eagerly (backend/llm.py),
        # so a missing or malformed API key raises at construction time, not at
        # ask() time. This needs its own guard to surface as a readable JSON 502
        # instead of an unhandled 500 — especially critical for the first-deploy
        # mistake of forgetting to set ANTHROPIC_API_KEY on Render.
        try:
            convo = conversation_factory()
        except Exception as e:
            trace("construction_error", error=f"{type(e).__name__}: {e}")
            return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=502)

        # prepare_history() (server/sanitize.py) is what guarantees no orphaned
        # 'tool' message reaches the model — Conversation.trim() below cannot
        # provide that guarantee at this call site, because its orphan-strip
        # sits behind a `len(rest) <= MAX_MESSAGES` guard that always fires
        # here (MAX_MESSAGES == MAX_HISTORY == 40, and we never append more
        # than 40 client messages). trim() is kept only in case a future
        # change makes conversations grow past that cap within a single call.
        # Assigned rather than passed: conversation_factory keeps its zero-argument
        # contract, so the existing test doubles in tests/conftest.py still work.
        recorder = Recorder()
        convo.recorder = recorder

        convo.messages += prepare_history(request.history)
        convo.trim()

        # Mark existing messages BY IDENTITY, not by index: ask() calls trim(),
        # which drops messages off the front, so a saved length would point at the
        # wrong place once a conversation gets long — and the charts would come back
        # empty exactly when the demo has been running a while.
        #
        # `retained` keeps a strong reference to every pre-ask() message dict alive
        # for the rest of this request. Without it, trim() inside ask() could let a
        # dropped dict get garbage-collected while ask() is still running, and
        # CPython is then free to hand its id() to a brand-new dict created later
        # in the same call — which would wrongly look "seen" and silently drop a
        # chart. Keeping the objects alive means their ids can never be recycled
        # until after `fresh` is computed below.
        retained = list(convo.messages)
        seen = {id(m) for m in retained}
        started = time.monotonic()
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

    @app.get("/health")
    def health():
        """Render polls this to decide whether the container is alive."""
        return {"ok": True}

    # Registered only when TRACE_KEY is set, so a fresh checkout exposes nothing.
    # The app is otherwise stateless by design (see the module docstring); storing
    # traces ends that, and this is where the property is defended.
    trace_key = os.environ.get("TRACE_KEY")
    if trace_key:

        def authorised(request):
            given = request.headers.get("X-Trace-Key", "")
            return hmac.compare_digest(trace_key, given)

        # 404, never 403, and the SAME 404 Starlette raises for a genuinely
        # unmatched route (body {"detail": "Not Found"}) — a custom body here
        # would let a prober tell "wrong key" apart from "no such route" even
        # though both are status 404. Raising, not returning, is what gets the
        # identical body: FastAPI's default handler renders any HTTPException
        # this way, so this is indistinguishable from routing's own 404.
        def missing():
            raise HTTPException(status_code=404)

        @app.get("/api/traces")
        def list_traces(request: Request, limit: int = 50, offset: int = 0):
            if not authorised(request):
                missing()
            # Clamp both ends: SQLite treats a negative LIMIT as "no limit",
            # which would silently defeat the 200-row cap.
            return {"traces": trace_store.recent(limit=max(1, min(limit, 200)),
                                                 offset=max(offset, 0))}

        @app.get("/api/traces/{trace_id}")
        def one_trace(request: Request, trace_id: str):
            if not authorised(request):
                missing()
            record = trace_store.get(trace_id)
            if not record:
                missing()
            return record

    # LAST: mounting "/" ahead of the routes above would shadow them. Conditional
    # because a fresh checkout and CI have no build, and an unconditional mount
    # raises at import time and takes the API tests down with it.
    static_dir = Path(static_dir)
    if (static_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    else:
        trace("frontend_missing", path=str(static_dir))

    return app


app = create_app()
