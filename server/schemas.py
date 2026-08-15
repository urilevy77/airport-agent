"""The wire contract for /chat, /export and the trace read API."""
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = ""
    history: list[Any] = Field(default_factory=list)   # untrusted; see sanitize.py
    # Both optional; None means "use the server default". Checked against
    # llm.MODELS / llm.MODEL_EFFORTS in server/app.py — never passed to the
    # API unvalidated, and effort is checked against the CHOSEN model, since
    # not every model accepts one (Haiku 4.5 accepts none at all).
    model: str | None = None
    effort: str | None = None


class Chart(BaseModel):
    tool: str | None
    args: dict = Field(default_factory=dict)
    data: Any                      # the tool's JSON dict, or its raw text on failure


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


class ExportStat(BaseModel):
    """One tile from StatRow, ALREADY FORMATTED — '84.2%', not 84.2. The
    formatting lives in frontend/src/charts/stats.js, so the document and the
    screen show the same figure by construction rather than by agreement."""
    label: str = ""
    value: str = ""
    note: str | None = None


class ExportBar(BaseModel):
    """One segment of a part-to-whole bar the browser could not photograph,
    because the chart was drawn in CSS rather than SVG. `pct` is the width as
    DRAWN — the true figure is spelled out in the label."""
    label: str = ""
    pct: float = 0.0
    color: str = ""


class ExportChart(BaseModel):
    """A chart card flattened for print: the text read out of the DOM, and the
    plot itself as a base64 PNG the browser rasterized from its <svg>."""
    title: str = ""
    caption: str = ""
    source: str = ""
    stats: list[ExportStat] = Field(default_factory=list)
    bars: list[ExportBar] = Field(default_factory=list)
    png_b64: str = ""              # untrusted; decoded defensively in docx_export


class ExportTurn(BaseModel):
    question: str = ""
    answer: str = ""
    charts: list[ExportChart] = Field(default_factory=list)


class ExportRequest(BaseModel):
    """Everything the document needs. The server holds no conversation, so an
    export — like a chat turn — is whatever the client can prove it has."""
    title: str = "Airport Investment Intelligence"
    generated_at: str = ""
    model: str | None = None
    turns: list[ExportTurn] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    charts: list[Chart]
    history: list[Any]
    trace: Trace
