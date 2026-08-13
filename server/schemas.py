"""The wire contract. One endpoint, three fields each way."""
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = ""
    history: list[Any] = Field(default_factory=list)   # untrusted; see sanitize.py


class Chart(BaseModel):
    tool: str | None
    args: dict = Field(default_factory=dict)
    data: Any                      # the tool's JSON dict, or its raw text on failure


class ChatResponse(BaseModel):
    answer: str
    charts: list[Chart]
    history: list[Any]
