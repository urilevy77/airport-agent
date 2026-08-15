"""backend/llm.py is the seam between our flat message format and Claude's.

Every test here is about that translation, which is the one place a shape
mistake turns into a 400 from the API instead of a visible bug. No key and no
network: nothing below constructs a client.
"""
import json

import pytest

import server.agent_bridge  # noqa: F401  — puts backend/ on sys.path

import llm  # noqa: E402
from llm import PROVIDER_CONTENT, from_provider, to_provider  # noqa: E402


class FakeBlock:
    """Stands in for an SDK content block: all the tests need is model_dump()."""

    def __init__(self, **fields):
        self.fields = fields

    def model_dump(self, exclude_none=True):
        return dict(self.fields)


class FakeResponse:
    def __init__(self, blocks, stop_reason="end_turn"):
        self.content = blocks
        self.stop_reason = stop_reason


class Keyless:
    api_key = None
    auth_token = None


def tool_call(call_id, name, **arguments):
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}


# ---------- our format -> Claude's ----------
def test_plain_turns_become_user_and_assistant_messages():
    out = to_provider([{"role": "user", "content": "Is JFK busy?"},
                       {"role": "assistant", "content": "Yes."}])
    assert out == [{"role": "user", "content": "Is JFK busy?"},
                   {"role": "assistant",
                    "content": [{"type": "text", "text": "Yes."}]}]


def test_a_tool_result_becomes_a_tool_result_block_in_a_user_message():
    """The shape difference that matters: role 'tool' does not exist here."""
    out = to_provider([
        {"role": "user", "content": "Is JFK busy?"},
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", airport="JFK")]},
        {"role": "tool", "tool_call_id": "c1", "content": '{"avg": 84.2}'},
    ])
    assert out[1] == {"role": "assistant", "content": [
        {"type": "tool_use", "id": "c1", "name": "get_congestion",
         "input": {"airport": "JFK"}}]}
    assert out[2] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "c1", "content": '{"avg": 84.2}'}]}


def test_parallel_results_arrive_in_one_user_message():
    """Splitting them across messages teaches the model to stop calling tools
    in parallel, which would double the latency of every comparison question."""
    out = to_provider([
        {"role": "user", "content": "DEN or JFK?"},
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_traffic_mix", airport="DEN"),
                        tool_call("c2", "get_traffic_mix", airport="JFK")]},
        {"role": "tool", "tool_call_id": "c1", "content": "{}"},
        {"role": "tool", "tool_call_id": "c2", "content": "{}"},
    ])
    results = [m for m in out if m["role"] == "user"][-1]
    assert [b["tool_use_id"] for b in results["content"]] == ["c1", "c2"]
    assert len(out) == 3


def test_an_unanswered_tool_call_is_dropped():
    """server/sanitize.py can strip a tool result the client tampered with. The
    tool_use it answered must go too, or the API rejects the whole turn."""
    out = to_provider([
        {"role": "user", "content": "Is JFK busy?"},
        {"role": "assistant", "content": "Checking.",
         "tool_calls": [tool_call("c1", "get_congestion", airport="JFK")]},
    ])
    assert out[1]["content"] == [{"type": "text", "text": "Checking."}]


def test_an_assistant_turn_left_with_nothing_to_say_is_dropped():
    out = to_provider([
        {"role": "user", "content": "Is JFK busy?"},
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", airport="JFK")]},
    ])
    assert out == [{"role": "user", "content": "Is JFK busy?"}]


def test_an_orphaned_tool_message_is_dropped():
    out = to_provider([{"role": "tool", "tool_call_id": "gone", "content": "{}"},
                       {"role": "user", "content": "hi"}])
    assert out == [{"role": "user", "content": "hi"}]


def test_history_always_opens_on_a_user_turn():
    """trim() cuts from the front, so it can leave an assistant turn first —
    which the API rejects."""
    out = to_provider([{"role": "assistant", "content": "an older answer"},
                       {"role": "user", "content": "and Boston?"}])
    assert out == [{"role": "user", "content": "and Boston?"}]


def test_provider_blocks_are_replayed_verbatim():
    """Thinking blocks must go back unchanged, so the recorded blocks win over
    the flat projection beside them."""
    blocks = [{"type": "thinking", "thinking": "", "signature": "abc"},
              {"type": "text", "text": "Yes."}]
    out = to_provider([{"role": "user", "content": "Is JFK busy?"},
                       {"role": "assistant", "content": "Yes.",
                        PROVIDER_CONTENT: blocks}])
    assert out[1]["content"] == blocks


# ---------- Claude's reply -> ours ----------
def test_a_reply_is_projected_into_text_and_tool_calls():
    message = from_provider(FakeResponse([
        FakeBlock(type="text", text="Let me check."),
        FakeBlock(type="tool_use", id="c1", name="get_congestion",
                  input={"airport": "JFK"}),
    ]))
    assert message["role"] == "assistant"
    assert message["content"] == "Let me check."
    call = message["tool_calls"][0]
    assert call["id"] == "c1"
    assert call["function"]["name"] == "get_congestion"
    # A JSON *string*, because that is what server/charts.py parses.
    assert json.loads(call["function"]["arguments"]) == {"airport": "JFK"}
    assert len(message[PROVIDER_CONTENT]) == 2


def test_a_text_only_reply_carries_no_tool_calls_key():
    message = from_provider(FakeResponse([FakeBlock(type="text", text="Yes.")]))
    assert "tool_calls" not in message


def test_an_empty_refusal_still_says_something():
    """A safety classifier declines with a 200 and no content; an empty string
    would render as a blank answer bubble."""
    message = from_provider(FakeResponse([], stop_reason="refusal"))
    assert message["content"]
    assert "tool_calls" not in message


def test_a_missing_key_fails_at_construction(monkeypatch):
    """server/app.py returns its readable 502 by catching the factory, so the
    key check has to happen here and not on the first question."""
    monkeypatch.delenv(llm.FEDERATION, raising=False)
    monkeypatch.setattr(llm.anthropic, "Anthropic", lambda *a, **k: Keyless())
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        llm.Client()


def test_a_reply_round_trips_back_through_to_provider():
    """The two halves have to agree: what from_provider records must be
    something to_provider can send back."""
    message = from_provider(FakeResponse([
        FakeBlock(type="text", text="Let me check."),
        FakeBlock(type="tool_use", id="c1", name="get_congestion",
                  input={"airport": "JFK"}),
    ]))
    out = to_provider([{"role": "user", "content": "Is JFK busy?"}, message,
                       {"role": "tool", "tool_call_id": "c1", "content": "{}"}])
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert out[1]["content"][1]["input"] == {"airport": "JFK"}
