"""A fake Conversation, so the endpoint tests need no API key and no network."""
import json

import pytest
from fastapi.testclient import TestClient

from server.app import create_app

SYSTEM = {"role": "system", "content": "system prompt"}


class FakeConversation:
    """Mimics backend.agent.Conversation: a system prompt, a message list, ask()."""

    scripted_tool = None      # (tool_name, args_dict, result_dict) or None
    raises = None             # an Exception instance to raise from ask()
    answer = "A plain-English answer."

    def __init__(self):
        self.messages = [dict(SYSTEM)]

    def trim(self):
        """Faithfully mirror backend.agent.Conversation.trim(), length guard
        included. Real trim() only strips orphaned leading tool messages after
        dropping down to the newest MAX_MESSAGES (40) — and /chat's own
        MAX_HISTORY cap is also 40, so at that call site `len(rest) <=
        MAX_MESSAGES` is always true and trim() returns before it ever strips
        anything. A lenient fake (unconditional strip, no length guard) would
        make tests pass for reasons the real Conversation can't back up —
        orphan protection at the /chat call site lives in
        server.sanitize.prepare_history(), not here. Do not simplify this back
        to an unconditional strip."""
        MAX_MESSAGES = 40  # mirrors backend.agent.MAX_MESSAGES; kept in sync by hand
        system, rest = self.messages[0], self.messages[1:]
        if len(rest) <= MAX_MESSAGES:
            return
        kept = rest[-MAX_MESSAGES:]
        while kept and kept[0]["role"] == "tool":
            kept.pop(0)
        self.messages = [system] + kept

    def ask(self, question):
        self.messages.append({"role": "user", "content": question})
        if type(self).raises:
            raise type(self).raises
        if type(self).scripted_tool:
            name, args, result = type(self).scripted_tool
            self.messages.append({"role": "assistant", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args)}}]})
            self.messages.append({"role": "tool", "tool_call_id": "call_1",
                                  "content": json.dumps(result)})
        self.messages.append({"role": "assistant", "content": type(self).answer})
        return type(self).answer


@pytest.fixture
def fake():
    """Reset the class-level script between tests."""
    FakeConversation.scripted_tool = None
    FakeConversation.raises = None
    FakeConversation.answer = "A plain-English answer."
    yield FakeConversation


@pytest.fixture
def client(fake):
    return TestClient(create_app(conversation_factory=fake))
