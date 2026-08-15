"""HTTP layer for the Airport Investment Intelligence Agent.

STATELESS by design: the browser keeps its own history and replays it each
turn, so no visitor can see another's conversation, any process can answer any
request, and a restart never wipes a conversation mid-demo. This applies to
the /chat endpoint's own conversation state only — every turn is now also
persisted server-side to a SQLite trace store (server/trace_store.py) and
readable across sessions through a key-gated /api/traces API; see the
"Registered only when TRACE_KEY is set" block below for how that's defended.
"""
import hmac
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from server import trace_store
from server.charts import charts_from_messages
from server.docx_export import build_document
from server.sanitize import clip_question, prepare_history
from server.schemas import ChatRequest, ChatResponse, ExportRequest
from server.tracing import trace

DEFAULT_STATIC = Path(__file__).resolve().parent.parent / "frontend" / "dist"

DOCX_MEDIA_TYPE = ("application/vnd.openxmlformats-officedocument"
                   ".wordprocessingml.document")
# Generous enough for a long conversation of 2x-scale chart captures, small
# enough that one request cannot exhaust a free host's memory.
MAX_EXPORT_BYTES = 32 * 1024 * 1024


def _export_filename():
    return f"airport-intelligence-{datetime.now(timezone.utc):%Y-%m-%d}.docx"


def create_app(conversation_factory=None, static_dir=DEFAULT_STATIC):
    """Build the app. `conversation_factory` is injectable so tests can run the
    whole endpoint without an API key or a network call."""
    if conversation_factory is None:
        from server.agent_bridge import Conversation
        conversation_factory = Conversation

    from server.agent_bridge import Conversation  # noqa: F401 — puts backend/ on sys.path
    from llm import MODEL, MODEL_EFFORTS, MODELS
    from recorder import Recorder

    app = FastAPI(title="Airport Investment Intelligence Agent")

    @app.get("/config")
    def config():
        """What the picker in the UI is allowed to offer — the single source of
        truth is llm.MODELS / llm.MODEL_EFFORTS, so the frontend never hardcodes
        (and drifts from) the allowlist /chat actually validates against, and
        can never offer an effort a given model doesn't support (e.g. Haiku 4.5,
        which takes none at all — an empty `efforts` list here)."""
        return {"default_model": MODEL,
                "models": [{"id": k, "label": v, "efforts": list(MODEL_EFFORTS[k])}
                          for k, v in MODELS.items()]}

    @app.post("/chat")
    def chat(request: ChatRequest):
        question = clip_question(request.question)
        if not question:
            return JSONResponse({"error": "Ask a question first."}, status_code=400)

        # Reject an unknown model, or an effort that model doesn't support,
        # before doing anything else — a tampered or stale client (or a picker
        # bug: this is exactly what caught Haiku + "high" reaching the API and
        # 400ing mid-turn) should get a clear 400 here instead.
        if request.model is not None and request.model not in MODELS:
            return JSONResponse({"error": f"Unknown model '{request.model}'."},
                                status_code=400)
        effective_model = request.model or MODEL
        if request.effort is not None and request.effort not in MODEL_EFFORTS[effective_model]:
            return JSONResponse(
                {"error": f"Effort '{request.effort}' isn't available for "
                          f"model '{effective_model}'."},
                status_code=400)

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

        # Assigned rather than passed: conversation_factory keeps its zero-argument
        # contract, so the existing test doubles in tests/conftest.py still work.
        recorder = Recorder()
        convo.recorder = recorder
        # Same reasoning for the user's model/effort pick — already validated
        # above. Only set when given, so a request with neither leaves
        # Conversation's own defaults (backend/llm.py MODEL, no effort) alone.
        if request.model is not None:
            convo.model = request.model
        if request.effort is not None:
            convo.effort = request.effort

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
        #
        # A trace must never break a request: if building the response with the
        # trace attached ever fails (e.g. a future schema mismatch on `record`),
        # a fully successful turn must still come back to the user — just
        # without the trace field — rather than 500ing on a technicality.
        try:
            return ChatResponse(answer=answer, charts=charts,
                                history=convo.messages[1:], trace=record)
        except Exception as e:
            trace("trace_response_error", error=f"{type(e).__name__}: {e}")
            return JSONResponse({"answer": answer, "charts": charts,
                                 "history": convo.messages[1:]})

    @app.post("/export")
    async def export(request: Request):
        """The conversation on screen as a .docx.

        Touches neither the model nor BTS: the browser has already resolved
        every word, number and pixel this document contains, so this route is
        pure layout. Deliberately NOT a tool the agent can call — assembling
        the document is deterministic work, the same category as scoring, and
        putting it behind the model would let it re-author what it should only
        be reporting.
        """
        # Checked BEFORE the body is read: the captures are base64 PNGs, so a
        # long conversation posts megabytes, and the point of the cap is to
        # not hold an outsized request in memory in the first place. The
        # len() check behind it covers a client that under-declares or omits
        # the header (chunked upload).
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_EXPORT_BYTES:
            return JSONResponse({"error": "That conversation is too large to export."},
                                status_code=413)
        body = await request.body()
        if len(body) > MAX_EXPORT_BYTES:
            return JSONResponse({"error": "That conversation is too large to export."},
                                status_code=413)

        try:
            payload = ExportRequest.model_validate_json(body)
        except ValidationError as e:
            return JSONResponse({"error": f"Malformed export request: {e.error_count()} "
                                          f"field(s) rejected."}, status_code=400)

        if not payload.turns:
            return JSONResponse({"error": "There is nothing to export yet."},
                                status_code=400)

        try:
            document = build_document(payload.model_dump())
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            trace("export_error", error=error)
            return JSONResponse({"error": error}, status_code=502)

        trace("export", turns=len(payload.turns),
              charts=sum(len(t.charts) for t in payload.turns), bytes=len(document))
        return Response(
            content=document,
            media_type=DOCX_MEDIA_TYPE,
            # ASCII-only filename on purpose: a non-ASCII one needs the RFC 5987
            # filename* form, and there is nothing here worth that.
            headers={"Content-Disposition":
                     f'attachment; filename="{_export_filename()}"'})

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
            # Anything that goes wrong while comparing — including a non-ASCII
            # byte in the header, which Starlette's latin-1 header decoding
            # lets through even though some HTTP clients refuse to send one —
            # must fail closed (False), not raise. hmac.compare_digest() raises
            # TypeError on non-ASCII strings, and an uncaught exception here
            # would surface as a 500 that a prober could tell apart from the
            # 404 a genuinely unmatched route returns — the same auth-bypass
            # oracle this whole block exists to close. Broad except on purpose.
            try:
                given = request.headers.get("X-Trace-Key", "")
                return hmac.compare_digest(trace_key, given)
            except Exception:
                return False

        # 404, never 403, and the SAME 404 Starlette raises for a genuinely
        # unmatched route (body {"detail": "Not Found"}) — a custom body here
        # would let a prober tell "wrong key" apart from "no such route" even
        # though both are status 404. Raising, not returning, is what gets the
        # identical body: FastAPI's default handler renders any HTTPException
        # this way, so this is indistinguishable from routing's own 404.
        def missing():
            raise HTTPException(status_code=404)

        @app.get("/api/traces")
        def list_traces(request: Request, limit: str = "50", offset: str = "0"):
            # limit/offset are typed str, not int: FastAPI would otherwise
            # reject a non-numeric value with its own automatic 422 BEFORE the
            # authorised() check below ever runs — a malformed query string
            # would then distinguish "TRACE_KEY is configured here" (422) from
            # "no tracing API at all" (404) without needing the key. Parsing
            # happens by hand, after the auth check, and a parse failure just
            # degrades to the default rather than raising.
            if not authorised(request):
                missing()
            try:
                limit = int(limit)
            except (TypeError, ValueError):
                limit = 50
            try:
                offset = int(offset)
            except (TypeError, ValueError):
                offset = 0
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
