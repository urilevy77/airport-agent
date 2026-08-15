"""/chat carries a trace, and stores one — including when the turn dies.

The fake Conversation in conftest.py does not run a real loop, so these tests
drive the recorder the way the real Conversation would: server/app.py assigns
convo.recorder, and the fake fills it.
"""
import pytest
from fastapi.testclient import TestClient

from server import trace_store
from server.app import create_app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACE_DB", str(tmp_path / "traces.db"))


class RecordingConversation:
    """A fake that writes into whatever recorder app.py assigns."""

    raises = None
    model = "fake-model"

    def __init__(self):
        self.messages = [{"role": "system", "content": "system prompt"}]
        self.recorder = None

    def trim(self):
        pass

    def ask(self, question):
        self.messages.append({"role": "user", "content": question})
        self.recorder.start_round()
        with self.recorder.step("model") as step:
            step.set(text="", calls=["get_congestion"])
        with self.recorder.step("tool", name="get_congestion",
                                args={"airport": "SFO"}) as step:
            step.set(result={"load_factor": 80.9}, error=None)
        if type(self).raises:
            raise type(self).raises
        self.messages.append({"role": "assistant", "content": "About 81% full."})
        return "About 81% full."


@pytest.fixture
def recording():
    RecordingConversation.raises = None
    yield RecordingConversation


@pytest.fixture
def rec_client(recording):
    return TestClient(create_app(conversation_factory=recording))


def test_the_response_carries_the_trace(rec_client):
    body = rec_client.post("/chat", json={"question": "How congested is SFO?",
                                          "history": []}).json()

    trace = body["trace"]
    assert trace["question"] == "How congested is SFO?"
    assert trace["answer"] == "About 81% full."
    assert trace["error"] is None
    assert trace["latency_ms"] >= 0
    assert [s["kind"] for s in trace["steps"]] == ["model", "tool"]
    assert trace["steps"][1]["name"] == "get_congestion"
    assert trace["steps"][1]["args"] == {"airport": "SFO"}
    assert trace["steps"][1]["result"] == {"load_factor": 80.9}


def test_the_turn_is_persisted(rec_client):
    body = rec_client.post("/chat", json={"question": "How congested is SFO?",
                                          "history": []}).json()

    stored = trace_store.get(body["trace"]["id"])
    assert stored["question"] == "How congested is SFO?"
    assert len(stored["steps"]) == 2


def test_a_failed_turn_stores_a_partial_trace(rec_client, recording):
    """The benefit that motivated holding the recorder in app.py: the steps that
    completed before the failure are exactly what you want to look at."""
    recording.raises = RuntimeError("BTS timed out")
    response = rec_client.post("/chat", json={"question": "How congested is SFO?",
                                              "history": []})
    assert response.status_code == 502

    rows = trace_store.recent()
    assert len(rows) == 1
    assert rows[0]["error"] == "RuntimeError: BTS timed out"
    assert rows[0]["question"] == "How congested is SFO?"
    assert trace_store.get(rows[0]["id"])["steps"][1]["name"] == "get_congestion"


def test_a_broken_store_does_not_break_chat(rec_client, monkeypatch, tmp_path):
    monkeypatch.setenv("TRACE_DB", str(tmp_path / "nope" / "traces.db"))
    response = rec_client.post("/chat", json={"question": "How congested is SFO?",
                                              "history": []})

    assert response.status_code == 200
    assert response.json()["answer"] == "About 81% full."


def test_existing_response_fields_are_untouched(client):
    """conftest's plain FakeConversation has no recorder attribute of its own —
    app.py must still work with the pre-existing test double."""
    body = client.post("/chat", json={"question": "hi", "history": []}).json()

    assert body["answer"] == "A plain-English answer."
    assert body["charts"] == []
    assert body["history"][-1]["content"] == "A plain-English answer."
