"""The wire contract for /chat and the trace read API."""
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


class ChatResponse(BaseModel):
    answer: str
    charts: list[Chart]
    history: list[Any]
    trace: Trace
