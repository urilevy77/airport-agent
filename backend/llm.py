#!/usr/bin/env python3
"""
llm.py — the ONLY module that talks to a model provider.

Provider: Anthropic (Claude), via the official `anthropic` SDK.

Everything else in this project speaks one message format: flat dicts with a
role and a content string, plus `tool_calls` / `tool_call_id` for a tool round
trip. That format is the app's wire format — the browser stores it, replays it
each turn (server/app.py), the sanitiser validates it (server/sanitize.py) and
the charts read it (server/charts.py). This module translates between it and
the provider's own shape, which is why swapping providers means editing this
file and nothing else.

SETUP   pip install anthropic
        export ANTHROPIC_API_KEY=...        # and optionally ANTHROPIC_MODEL
"""
import json
import os

import anthropic

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_TOKENS = 8192

# The models and effort levels a user is allowed to pick from the UI. An
# explicit allowlist, never a client-supplied string passed straight through:
# an unknown model 404s mid-conversation and an unknown effort 400s the whole
# turn, so server/app.py checks a request's choices against these before
# handing them to Conversation.
MODELS = {
    "claude-sonnet-5": "Sonnet 5 - balanced (default)",
    "claude-opus-5": "Opus 5 - most capable, higher cost and latency",
    "claude-haiku-4-5": "Haiku 4.5 - fastest and cheapest, no effort control",
}
# Not every model accepts `effort` — Haiku 4.5 rejects the parameter outright
# (400), so its allowed set is empty and the frontend must not offer one.
# Keyed by the SAME ids as MODELS (backend/selftest.py checks the two agree).
MODEL_EFFORTS = {
    "claude-sonnet-5": ("low", "medium", "high"),
    "claude-opus-5": ("low", "medium", "high"),
    "claude-haiku-4-5": (),
}

# Where an assistant message keeps the provider's own content blocks, verbatim.
# The flat `content` / `tool_calls` beside it are a projection of these for the
# rest of the app; this key is what goes back to the API.
PROVIDER_CONTENT = "_provider_content"


def loads(raw):
    """Tool arguments arrive as a JSON string in our format; never crash on one."""
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


# ---------- our format -> the provider's ----------
def assistant_content(message, answered):
    """One assistant turn as provider content blocks.

    Prefer the blocks the provider itself returned: they carry the thinking
    blocks the API wants handed back unchanged when a conversation continues on
    the same model. Rebuild from the flat fields only for messages that never
    came from us — a tampered client history, or one recorded by another
    provider.

    A tool_use block whose result went missing (sanitised away, trimmed off the
    front) is a 400, so only blocks `answered` by a tool result survive.
    """
    blocks = message.get(PROVIDER_CONTENT)
    if blocks is None:
        blocks = []
        if message.get("content"):
            blocks.append({"type": "text", "text": message["content"]})
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            blocks.append({"type": "tool_use", "id": call.get("id"),
                           "name": fn.get("name"),
                           "input": loads(fn.get("arguments"))})
    kept = [b for b in blocks
            if b.get("type") != "tool_use" or b.get("id") in answered]
    # A turn of nothing but thinking is not a valid message to send back, and
    # dropping it also drops the tool results that answered its lost calls.
    if not any(b.get("type") in ("text", "tool_use") for b in kept):
        return []
    return kept


def to_provider(messages):
    """Our flat history -> the provider's messages array (no system prompt).

    Two shape differences do the work here:
      - a tool result is a `tool_result` block inside a USER message, not a
        message with role 'tool';
      - every result from one assistant turn belongs in ONE user message.
        Splitting parallel results across several messages teaches the model to
        stop making parallel calls.
    """
    out = []
    i = 0
    while i < len(messages):
        message = messages[i]
        role = message.get("role")

        if role == "assistant":
            answered, j = {}, i + 1
            while j < len(messages) and messages[j].get("role") == "tool":
                answered[messages[j].get("tool_call_id")] = messages[j].get("content", "")
                j += 1
            content = assistant_content(message, answered)
            if content:
                out.append({"role": "assistant", "content": content})
                if answered:
                    out.append({"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": call_id,
                         "content": result}
                        for call_id, result in answered.items()]})
            i = j
        elif role == "tool":
            i += 1          # orphan: no assistant turn for it to answer
        else:
            out.append({"role": "user", "content": message.get("content", "")})
            i += 1

    # The array must open on a user turn. Trimming can cut into the middle of an
    # exchange, so drop whatever is stranded at the front.
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


# ---------- the provider's reply -> ours ----------
REFUSED = ("The model declined to answer that one. Rephrasing usually helps.")


def from_provider(response):
    """The reply as one assistant message in our format.

    Keeps the provider's blocks whole (PROVIDER_CONTENT) and projects the two
    things the rest of the app reads out of them: the text, and the tool calls.
    """
    blocks = [b.model_dump(exclude_none=True) for b in response.content]
    text = "".join(b["text"] for b in blocks if b["type"] == "text")
    calls = [{"id": b["id"], "type": "function",
              "function": {"name": b["name"],
                           "arguments": json.dumps(b.get("input") or {})}}
             for b in blocks if b["type"] == "tool_use"]

    message = {"role": "assistant", "content": text, PROVIDER_CONTENT: blocks}
    if calls:
        message["tool_calls"] = calls
    elif not text:
        # A safety classifier can decline with a 200 and no content at all;
        # returning "" would show the user an empty answer bubble.
        message["content"] = REFUSED if response.stop_reason == "refusal" else (
            "No answer came back from the model. Please try again.")
    return message


class Client:
    """One model client. Constructing it is what validates the API key."""

    def __init__(self, model=None):
        # Eager on purpose: a missing key raises HERE, at construction, which is
        # what lets server/app.py turn it into a readable 502 instead of failing
        # halfway through a question. The SDK itself no longer checks at
        # construction — it resolves ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN
        # into attributes and defers the complaint to the first request — so the
        # check has to live here.
        self.client = anthropic.Anthropic()
        if not (self.client.api_key or self.client.auth_token):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Put it in .env or the environment.")
        self.model = model or MODEL

    def complete(self, system, messages, tools, model=None, effort=None):
        """One round trip. Returns one assistant message in our format.

        `model` and `effort` are per-call overrides of this Client's own
        defaults: Conversation carries the user's picks on self.model /
        self.effort and passes them in fresh every round, so a plain
        Client (CLI, REPL, no picks made) is untouched.
        """
        extra = {"output_config": {"effort": effort}} if effort else {}
        response = self.client.messages.create(
            model=model or self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=to_provider(messages),
            tools=tools,
            **extra,
        )
        return from_provider(response)
