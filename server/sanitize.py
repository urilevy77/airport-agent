"""Everything the client sends is untrusted. This module is the only place
that decides what survives.
"""
MAX_HISTORY = 40         # messages accepted from a client, after the system prompt
MAX_QUESTION = 500       # characters — nothing useful is longer, and it caps abuse
CLIENT_ROLES = {"user", "assistant", "tool"}     # never "system"


def clean_history(history):
    """Keep only the roles a real conversation produces.

    A smuggled {"role": "system"} message would sit beside our own and override
    the agent's rules, and it survives trim(). Dropping the role is the fix.
    """
    if not isinstance(history, list):
        return []
    return [m for m in history
            if isinstance(m, dict) and m.get("role") in CLIENT_ROLES]


def clip_question(raw):
    """Normalise the question: a string, trimmed, length-capped."""
    if not isinstance(raw, str):
        return ""
    return raw.strip()[:MAX_QUESTION]


def prepare_history(history):
    """Turn raw client-supplied history into something safe to hand the model.

    This is the ONLY place that guarantees no orphaned `tool` message reaches
    the API. `Conversation.trim()` (backend/agent.py) cannot be relied on for
    this: its orphan-stripping line sits behind `if len(rest) <= MAX_MESSAGES:
    return`, and MAX_MESSAGES there equals MAX_HISTORY here (both 40) — so
    /chat never appends more than 40 client messages, that guard always
    fires, and trim() returns before it ever reaches the orphan-strip. Do not
    delete this function on the assumption trim() already covers it.

    Order matters: cap to the newest MAX_HISTORY messages FIRST, then drop
    invalid tool messages — slicing can itself orphan a tool message that was
    valid in the full list, if the cut falls between it and the assistant
    message holding its matching tool_calls.
    """
    capped = clean_history(history)[-MAX_HISTORY:]
    return _drop_invalid_tool_messages(capped)


def _drop_invalid_tool_messages(messages):
    """Keep a 'tool' message only if it answers a tool_call_id issued by the
    most recently seen assistant tool_calls message, and that assistant
    message hasn't since been closed out by a later non-tool message.

    A leading tool message ([tool, ...]) or one following a user message
    ([user, tool]) has no assistant tool_calls to answer, so it is dropped —
    the API 400s on an orphan like that. A genuine tool_calls message
    followed by its matching tool result is kept untouched, including when an
    assistant message carries several parallel tool_calls in one turn.
    """
    kept = []
    expected_ids = set()
    for message in messages:
        role = message.get("role")
        if role == "assistant":
            calls = message.get("tool_calls") or []
            expected_ids = {c.get("id") for c in calls
                            if isinstance(c, dict) and c.get("id")}
            kept.append(message)
        elif role == "tool":
            call_id = message.get("tool_call_id")
            if call_id is not None and call_id in expected_ids:
                kept.append(message)
                expected_ids.discard(call_id)
            # else: orphaned or mismatched tool result — drop it silently.
        else:
            expected_ids = set()
            kept.append(message)
    return kept
