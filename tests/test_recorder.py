"""backend/recorder.py accumulates one dict per timed step.

The recorder sits inside the agent loop, so the tests that matter are about
what it does when things go wrong: it must record a step whose block raised,
and it must never raise anything of its own.
"""
import server.agent_bridge  # noqa: F401  — puts backend/ on sys.path

import pytest  # noqa: E402

from recorder import NULL, Recorder  # noqa: E402


def test_records_kind_round_and_ms():
    rec = Recorder()
    rec.start_round()
    with rec.step("tool", name="get_congestion"):
        pass

    assert len(rec.steps) == 1
    step = rec.steps[0]
    assert step["kind"] == "tool"
    assert step["round"] == 1
    assert step["name"] == "get_congestion"
    assert isinstance(step["ms"], int) and step["ms"] >= 0


def test_start_round_groups_steps():
    rec = Recorder()
    rec.start_round()
    with rec.step("model"):
        pass
    rec.start_round()
    with rec.step("model"):
        pass

    assert [s["round"] for s in rec.steps] == [1, 2]


def test_set_merges_fields_into_the_step():
    rec = Recorder()
    rec.start_round()
    with rec.step("tool", name="get_growth") as step:
        step.set(result={"score": 0.81}, error=None)

    assert rec.steps[0]["result"] == {"score": 0.81}
    assert rec.steps[0]["error"] is None


def test_a_raising_block_still_records_its_step():
    """This is what makes a partial trace possible when ask() dies mid-turn."""
    rec = Recorder()
    rec.start_round()
    with pytest.raises(ValueError):
        with rec.step("tool", name="get_candidate"):
            raise ValueError("boom")

    assert len(rec.steps) == 1
    assert rec.steps[0]["name"] == "get_candidate"


def test_the_block_exception_is_not_swallowed():
    rec = Recorder()
    with pytest.raises(ValueError, match="boom"):
        with rec.step("model"):
            raise ValueError("boom")


def test_null_recorder_records_nothing_and_supports_the_full_interface():
    NULL.start_round()
    with NULL.step("tool", name="get_congestion") as step:
        step.set(result={"anything": 1})

    assert list(NULL.steps) == []
