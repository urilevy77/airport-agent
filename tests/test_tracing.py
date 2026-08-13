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


class BrokenRepr:
    """A value whose __repr__ itself raises."""
    def __repr__(self):
        raise RuntimeError("repr is broken")


def test_trace_never_raises_even_when_field_repr_raises(capsys):
    """Trace must not raise even if a field's __repr__ raises.

    This covers the case where json.dumps(default=repr) calls repr() on a
    non-serialisable value, and that repr() itself raises. The trace call
    must complete without raising, even if it means no output.
    """
    # This must not raise, despite BrokenRepr.__repr__ raising.
    trace("chat", bad=BrokenRepr())
    # We don't assert on output here because the exception silently fails
    # to serialize. The key contract is: trace() did not raise.
