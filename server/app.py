"""HTTP layer for the Airport Investment Intelligence Agent.

STATELESS by design: the browser keeps its own history and replays it each
turn, so no visitor can see another's conversation, any process can answer any
request, and a restart never wipes a conversation mid-demo.
"""
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from server.charts import charts_from_messages
from server.sanitize import MAX_HISTORY, clean_history, clip_question
from server.schemas import ChatRequest, ChatResponse
from server.tracing import trace


def create_app(conversation_factory=None):
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
        convo.messages += clean_history(request.history)[-MAX_HISTORY:]
        convo.trim()                 # never leave a tool message orphaned

        # Mark existing messages BY IDENTITY, not by index: ask() calls trim(),
        # which drops messages off the front, so a saved length would point at the
        # wrong place once a conversation gets long — and the charts would come back
        # empty exactly when the demo has been running a while.
        seen = {id(m) for m in convo.messages}
        started = time.monotonic()
        try:
            answer = convo.ask(question)
        except Exception as e:
            trace("chat_error", question=question, error=f"{type(e).__name__}: {e}")
            # 502 with a readable message, not a 500 page: the chat stays usable
            # and the user can retry.
            return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=502)

        fresh = [m for m in convo.messages if id(m) not in seen]
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

    return app


app = create_app()
