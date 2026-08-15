"""backend/agent.py, instrumented.

The load-bearing test here is the LAST one: the whole justification for putting
a recorder inside the loop is that it costs nothing when absent. If the null
default ever changes behaviour, the tradeoff this design accepted stops being
worth it.

No key and no network: FakeClient stands in for llm.Client.
"""
import json

import server.agent_bridge  # noqa: F401  — puts backend/ on sys.path

import agent  # noqa: E402
from recorder import Recorder  # noqa: E402


class FakeClient:
    """Returns scripted assistant messages, one per complete() call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.model = "fake-model"
        self.calls = 0

    def complete(self, system, messages, tools):
        self.calls += 1
        return self.replies.pop(0)


def tool_call(call_id, name, args):
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def build(monkeypatch, replies, recorder=None):
    """A Conversation whose client is scripted."""
    monkeypatch.setattr(agent, "Client", lambda model=None: FakeClient(replies))
    return agent.Conversation(recorder=recorder)


ANSWER = {"role": "assistant", "content": "SFO runs about 81% full."}


def test_records_a_model_step_per_round(monkeypatch):
    rec = Recorder()
    convo = build(monkeypatch, [ANSWER], recorder=rec)
    convo.ask("How congested is SFO?")

    models = [s for s in rec.steps if s["kind"] == "model"]
    assert len(models) == 1
    assert models[0]["round"] == 1
    assert models[0]["text"] == "SFO runs about 81% full."
    assert models[0]["calls"] == []


def test_records_tool_name_args_and_result(monkeypatch):
    monkeypatch.setattr(agent, "TOOLS",
                        {"get_congestion": lambda airport: {"load_factor": 80.9}})
    rec = Recorder()
    convo = build(monkeypatch, [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"})]},
        ANSWER,
    ], recorder=rec)
    convo.ask("How congested is SFO?")

    tools = [s for s in rec.steps if s["kind"] == "tool"]
    assert len(tools) == 1
    assert tools[0]["name"] == "get_congestion"
    assert tools[0]["args"] == {"airport": "SFO"}
    assert tools[0]["result"] == {"load_factor": 80.9}
    assert tools[0]["error"] is None
    assert tools[0]["round"] == 1


def test_the_model_step_lists_the_tools_it_asked_for(monkeypatch):
    monkeypatch.setattr(agent, "TOOLS",
                        {"get_congestion": lambda airport: {"load_factor": 80.9}})
    rec = Recorder()
    convo = build(monkeypatch, [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"}),
                        tool_call("c2", "get_congestion", {"airport": "BOS"})]},
        ANSWER,
    ], recorder=rec)
    convo.ask("SFO or BOS?")

    assert rec.steps[0]["calls"] == ["get_congestion", "get_congestion"]


def test_a_failing_tool_is_recorded_and_the_turn_still_succeeds(monkeypatch):
    """agent.py turns a tool exception into an {"error": ...} the model reads and
    recovers from, so a SUCCESSFUL turn can legitimately contain a failed step."""
    def explode(airport):
        raise RuntimeError("BTS is down")

    monkeypatch.setattr(agent, "TOOLS", {"get_congestion": explode})
    rec = Recorder()
    convo = build(monkeypatch, [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"})]},
        ANSWER,
    ], recorder=rec)
    answer = convo.ask("How congested is SFO?")

    assert answer == "SFO runs about 81% full."
    tools = [s for s in rec.steps if s["kind"] == "tool"]
    assert tools[0]["error"] == "RuntimeError: BTS is down"
    assert tools[0]["result"] == {"error": "RuntimeError: BTS is down"}


def test_rounds_increment_across_tool_rounds(monkeypatch):
    monkeypatch.setattr(agent, "TOOLS",
                        {"get_congestion": lambda airport: {"load_factor": 80.9}})
    rec = Recorder()
    convo = build(monkeypatch, [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"})]},
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c2", "get_congestion", {"airport": "BOS"})]},
        ANSWER,
    ], recorder=rec)
    convo.ask("SFO then BOS")

    assert [s["round"] for s in rec.steps] == [1, 1, 2, 2, 3]


def test_null_recorder_leaves_behaviour_identical(monkeypatch):
    """The entire justification for the coupling in agent.py. If this fails, the
    tradeoff the design accepted no longer holds."""
    monkeypatch.setattr(agent, "TOOLS",
                        {"get_congestion": lambda airport: {"load_factor": 80.9}})
    replies = [
        {"role": "assistant", "content": "",
         "tool_calls": [tool_call("c1", "get_congestion", {"airport": "SFO"})]},
        ANSWER,
    ]
    plain = build(monkeypatch, [dict(r) for r in replies])
    answer = plain.ask("How congested is SFO?")

    assert answer == "SFO runs about 81% full."
    assert [m["role"] for m in plain.messages] == [
        "system", "user", "assistant", "tool", "assistant"]
    assert plain.messages[3]["content"] == json.dumps({"load_factor": 80.9})
    assert plain.messages[3]["tool_call_id"] == "c1"
