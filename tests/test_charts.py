from server.charts import charts_from_messages


def _assistant(call_id, name, arguments):
    return {"role": "assistant", "tool_calls": [
        {"id": call_id, "type": "function",
         "function": {"name": name, "arguments": arguments}}]}


def test_pairs_each_tool_call_with_its_result():
    messages = [
        _assistant("c1", "get_congestion", '{"airport": "JFK"}'),
        {"role": "tool", "tool_call_id": "c1",
         "content": '{"airport": "JFK", "found": true, "avg_load_factor": 84.2}'},
        {"role": "assistant", "content": "JFK is busy."},
    ]
    assert charts_from_messages(messages) == [
        {"tool": "get_congestion",
         "args": {"airport": "JFK"},
         "data": {"airport": "JFK", "found": True, "avg_load_factor": 84.2}},
    ]


def test_returns_empty_list_when_no_tools_ran():
    assert charts_from_messages([{"role": "assistant", "content": "You're welcome."}]) == []


def test_keeps_one_entry_per_call_in_order():
    messages = [
        _assistant("c1", "get_congestion", '{"airport": "BOS"}'),
        {"role": "tool", "tool_call_id": "c1", "content": '{"airport": "BOS"}'},
        _assistant("c2", "get_growth", '{"airport": "JFK"}'),
        {"role": "tool", "tool_call_id": "c2", "content": '{"airport": "JFK"}'},
    ]
    assert [c["tool"] for c in charts_from_messages(messages)] == [
        "get_congestion", "get_growth"]


def test_unparseable_arguments_become_empty_dict():
    messages = [
        _assistant("c1", "get_congestion", "not json"),
        {"role": "tool", "tool_call_id": "c1", "content": '{"airport": "JFK"}'},
    ]
    assert charts_from_messages(messages)[0]["args"] == {}


def test_non_json_tool_result_is_passed_through_as_text():
    messages = [
        _assistant("c1", "get_congestion", '{"airport": "JFK"}'),
        {"role": "tool", "tool_call_id": "c1", "content": "BTS timed out"},
    ]
    assert charts_from_messages(messages)[0]["data"] == "BTS timed out"


def test_parallel_tool_calls_in_one_message_both_produce_charts():
    """Real models can emit two tool_calls in a single assistant message, not
    just across separate turns — charts_from_messages iterates the whole
    tool_calls list per message, so both must come back, in call order."""
    messages = [
        {"role": "assistant", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "get_congestion",
                          "arguments": '{"airport": "JFK"}'}},
            {"id": "c2", "type": "function",
             "function": {"name": "get_growth",
                          "arguments": '{"airport": "BOS"}'}},
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": '{"airport": "JFK"}'},
        {"role": "tool", "tool_call_id": "c2", "content": '{"airport": "BOS"}'},
    ]
    charts = charts_from_messages(messages)
    assert charts == [
        {"tool": "get_congestion", "args": {"airport": "JFK"},
         "data": {"airport": "JFK"}},
        {"tool": "get_growth", "args": {"airport": "BOS"},
         "data": {"airport": "BOS"}},
    ]


def test_tool_error_results_are_still_returned():
    """The frontend shows the error in the chart slot, so it must arrive."""
    messages = [
        _assistant("c1", "get_congestion", '{"airport": "NYC"}'),
        {"role": "tool", "tool_call_id": "c1",
         "content": '{"airport": "NYC", "found": false, "error": "No BTS data"}'},
    ]
    data = charts_from_messages(messages)[0]["data"]
    assert data["found"] is False and "error" in data
