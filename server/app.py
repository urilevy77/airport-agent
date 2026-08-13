"""HTTP layer for the Airport Investment Intelligence Agent.

STATELESS by design: the browser keeps its own history and replays it each
turn, so no visitor can see another's conversation, any process can answer any
request, and a restart never wipes a conversation mid-demo.
"""
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.charts import charts_from_messages
from server.sanitize import clip_question, prepare_history
from server.schemas import ChatRequest, ChatResponse
from server.tracing import trace

DEFAULT_STATIC = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app(conversation_factory=None, static_dir=DEFAULT_STATIC):
    """Build the app. `conversation_factory` is injectable so tests can run the
    whole endpoint without an OpenAI key or a network call."""
    if conversation_factory is None:
        from server.agent_bridge import Conversation
        conversation_factory = Conversation

    app = FastAPI(title="Airport Investment Intelligence Agent")

    @app.post("/chat")
    def chat(request: ChatRequest):
        question = clip_question(request.question)
        if not question:
            return JSONResponse({"error": "Ask a question first."}, status_code=400)

        convo = conversation_factory()
        # prepare_history() (server/sanitize.py) is what guarantees no orphaned
        # 'tool' message reaches the model — Conversation.trim() below cannot
        # provide that guarantee at this call site, because its orphan-strip
        # sits behind a `len(rest) <= MAX_MESSAGES` guard that always fires
        # here (MAX_MESSAGES == MAX_HISTORY == 40, and we never append more
        # than 40 client messages). trim() is kept only in case a future
        # change makes conversations grow past that cap within a single call.
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
            trace("chat_error", question=question, error=f"{type(e).__name__}: {e}")
            # 502 with a readable message, not a 500 page: the chat stays usable
            # and the user can retry.
            return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=502)

        fresh = [m for m in convo.messages if id(m) not in seen]
        del retained  # safe to release now that `fresh` no longer depends on ids
        charts = charts_from_messages(fresh)
        trace("chat", question=question, answer=answer,
              tools=[c["tool"] for c in charts],
              tool_results=[c["data"] for c in charts],
              latency_ms=int((time.monotonic() - started) * 1000))

        # Everything except the system prompt: the client stores this and replays
        # it next turn, and our prompt is rebuilt server-side each time.
        return ChatResponse(answer=answer, charts=charts, history=convo.messages[1:])

    @app.get("/health")
    def health():
        """Render polls this to decide whether the container is alive."""
        return {"ok": True}

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
