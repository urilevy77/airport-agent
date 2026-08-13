import json

from server.tracing import trace


def test_trace_writes_one_json_line_with_event_and_timestamp(capsys):
    trace("chat", question="Is JFK busy?", tools=["get_congestion"], latency_ms=812)
    line = capsys.readouterr().out.strip()
    record = json.loads(line)
    assert record["event"] == "chat"
    assert record["question"] == "Is JFK busy?"
    assert record["tools"] == ["get_congestion"]
    assert record["latency_ms"] == 812
    assert record["ts"].endswith("Z")


def test_trace_survives_unserialisable_values(capsys):
    """A trace call must never be the thing that breaks a request."""
    trace("chat", weird=object())
    record = json.loads(capsys.readouterr().out.strip())
    assert record["event"] == "chat"
