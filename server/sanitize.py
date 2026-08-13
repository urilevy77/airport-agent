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
