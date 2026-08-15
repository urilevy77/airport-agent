"""server/trace_store.py — one capped SQLite table of turns.

Best-effort by contract: every failure mode here must degrade to the stdout
sink rather than reach the request.
"""
import sqlite3

import pytest

from server import trace_store


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "traces.db")


def record(question="How congested is SFO?", steps=None):
    return trace_store.make_record(
        question=question,
        answer="About 81% full.",
        model="claude-opus-5",
        steps=steps if steps is not None else [
            {"kind": "model", "round": 1, "ms": 1240, "text": "",
             "calls": ["get_congestion"]},
            {"kind": "tool", "round": 1, "ms": 1810, "name": "get_congestion",
             "args": {"airport": "SFO"}, "result": {"load_factor": 80.9},
             "error": None},
        ],
        latency_ms=3050)


def test_make_record_stamps_an_id_and_a_timestamp():
    made = record()
    assert made["id"]
    assert made["ts"].endswith("Z")
    assert made["error"] is None
    assert made["latency_ms"] == 3050


def test_write_then_get_round_trips_the_steps(db):
    made = record()
    trace_store.write(made, path=db)

    got = trace_store.get(made["id"], path=db)
    assert got["question"] == "How congested is SFO?"
    assert got["answer"] == "About 81% full."
    assert got["model"] == "claude-opus-5"
    assert got["steps"][1]["args"] == {"airport": "SFO"}
    assert got["steps"][1]["result"] == {"load_factor": 80.9}


def test_get_returns_none_for_an_unknown_id(db):
    trace_store.write(record(), path=db)
    assert trace_store.get("no-such-id", path=db) is None


def test_recent_is_newest_first_and_omits_steps(db):
    for question in ["first", "second", "third"]:
        trace_store.write(record(question=question), path=db)

    rows = trace_store.recent(path=db)
    assert [r["question"] for r in rows] == ["third", "second", "first"]
    assert "steps" not in rows[0]
    # The summary still carries what the list view renders.
    assert rows[0]["latency_ms"] == 3050
    assert rows[0]["step_count"] == 2


def test_recent_honours_limit_and_offset(db):
    for question in ["a", "b", "c", "d"]:
        trace_store.write(record(question=question), path=db)

    assert [r["question"] for r in trace_store.recent(limit=2, path=db)] == ["d", "c"]
    assert [r["question"] for r in
            trace_store.recent(limit=2, offset=2, path=db)] == ["b", "a"]


def test_retention_keeps_only_the_newest_rows(db, monkeypatch):
    monkeypatch.setenv("TRACE_MAX_ROWS", "3")
    for question in ["a", "b", "c", "d", "e"]:
        trace_store.write(record(question=question), path=db)

    rows = trace_store.recent(path=db)
    assert [r["question"] for r in rows] == ["e", "d", "c"]


def test_write_survives_an_unwritable_database(tmp_path):
    """The premise of a best-effort sink: /chat must not care that this failed."""
    unwritable = str(tmp_path / "no-such-dir" / "traces.db")
    trace_store.write(record(), path=unwritable)   # must not raise


def test_write_survives_a_corrupt_database(db):
    with open(db, "w") as fh:
        fh.write("this is not a database")
    trace_store.write(record(), path=db)           # must not raise


def test_reads_survive_a_missing_database(tmp_path):
    missing = str(tmp_path / "never-written.db")
    assert trace_store.recent(path=missing) == []
    assert trace_store.get("anything", path=missing) is None


def test_path_comes_from_the_environment_when_not_given(tmp_path, monkeypatch):
    configured = str(tmp_path / "from-env.db")
    monkeypatch.setenv("TRACE_DB", configured)
    made = record()
    trace_store.write(made)

    assert trace_store.get(made["id"])["question"] == "How congested is SFO?"
    with sqlite3.connect(configured) as con:
        assert con.execute("SELECT COUNT(*) FROM traces").fetchone()[0] == 1
