"""Turn the messages a turn produced into the chart payload.

The charts render from these results, so a chart can never disagree with the
prose: nothing here reads the answer text.
"""
import json


def _parse(raw, fallback):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return fallback


def charts_from_messages(fresh_messages):
    """One entry per tool the loop really dispatched, in call order.

    Read from the recorded messages rather than asked of the model, which can
    misreport which tools it used.
    """
    results = {m.get("tool_call_id"): m.get("content", "")
               for m in fresh_messages if m.get("role") == "tool"}
    charts = []
    for message in fresh_messages:
        for call in (message.get("tool_calls") or []):
            function = call.get("function", {})
            charts.append({
                "tool": function.get("name"),
                "args": _parse(function.get("arguments"), {}),
                "data": _parse(results.get(call.get("id"), ""),
                               results.get(call.get("id"), "")),
            })
    return charts
