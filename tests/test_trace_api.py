"""The read API fails closed.

The app is otherwise stateless by design — "no visitor can see another's
conversation" is true because nothing is stored. Persisting traces ends that,
so this route is the one place the property now has to be defended.
"""
import pytest
from fastapi.testclient import TestClient

from server import trace_store
from server.app import create_app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACE_DB", str(tmp_path / "traces.db"))


def stored(question="How congested is SFO?"):
    record = trace_store.make_record(
        question=question, answer="About 81% full.", model="claude-opus-5",
        steps=[{"kind": "tool", "round": 1, "ms": 1810, "name": "get_congestion",
                "args": {"airport": "SFO"}, "result": {"load_factor": 80.9},
                "error": None}],
        latency_ms=3050)
    trace_store.write(record)
    return record


def keyed(monkeypatch, fake, key="s3cret"):
    monkeypatch.setenv("TRACE_KEY", key)
    return TestClient(create_app(conversation_factory=fake))


def test_the_routes_do_not_exist_without_a_key(monkeypatch, fake):
    monkeypatch.delenv("TRACE_KEY", raising=False)
    client = TestClient(create_app(conversation_factory=fake))
    stored()

    assert client.get("/api/traces").status_code == 404


def test_a_wrong_key_is_404_not_403(monkeypatch, fake):
    """404 so a prober cannot tell 'wrong key' from 'no such route'."""
    client = keyed(monkeypatch, fake)
    stored()

    assert client.get("/api/traces",
                      headers={"X-Trace-Key": "wrong"}).status_code == 404


def test_a_missing_header_is_404(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    stored()

    assert client.get("/api/traces").status_code == 404


def test_the_right_key_lists_summaries_newest_first(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    stored("first")
    stored("second")

    body = client.get("/api/traces", headers={"X-Trace-Key": "s3cret"}).json()
    assert [row["question"] for row in body["traces"]] == ["second", "first"]
    assert "steps" not in body["traces"][0]
    assert body["traces"][0]["step_count"] == 1


def test_limit_and_offset_pass_through(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    for question in ["a", "b", "c"]:
        stored(question)

    body = client.get("/api/traces?limit=1&offset=1",
                      headers={"X-Trace-Key": "s3cret"}).json()
    assert [row["question"] for row in body["traces"]] == ["b"]


def test_one_trace_comes_back_whole(monkeypatch, fake):
    client = keyed(monkeypatch, fake)
    record = stored()

    body = client.get(f"/api/traces/{record['id']}",
                      headers={"X-Trace-Key": "s3cret"}).json()
    assert body["steps"][0]["name"] == "get_congestion"
    assert body["steps"][0]["result"] == {"load_factor": 80.9}


def test_an_unknown_trace_id_is_404(monkeypatch, fake):
    client = keyed(monkeypatch, fake)

    assert client.get("/api/traces/no-such-id",
                      headers={"X-Trace-Key": "s3cret"}).status_code == 404
