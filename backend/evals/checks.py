#!/usr/bin/env python3
"""
checks.py — deterministic pass/fail checks for one eval case's outcome.

Every check is a function (Result) -> (passed: bool, detail: str), so run.py
can report WHY a case failed, not just that it did. Checks stay black-box on
WHAT the agent did (which tools it called, what the answer says) and never on
HOW a prompt variant phrases the rule that produced that behaviour — that is
what lets the same case set score two very differently-worded prompts fairly.

This mirrors kpis.py's own testing philosophy (backend/selftest.py): invariant
checks against live behaviour, never a fixed expected string.
"""
import re
from dataclasses import dataclass, field

MONTH_PATTERN = re.compile(
    r"\b(19|20)\d{2}-\d{2}\b"                                         # 2025-11
    r"|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(19|20)\d{2}\b",
    re.IGNORECASE)


@dataclass
class Result:
    """What one turn actually did, for checks to inspect."""
    answer: str
    tools_called: list = field(default_factory=list)   # tool names, in call order


def calls_tool(name, at_least=1):
    """The tool was called at least `at_least` times this turn. Use at_least=2
    for a question that names two airports (e.g. Denver vs JFK) — the model
    nominating only one is a routing bug this default of 1 would miss."""
    def check(result):
        n = result.tools_called.count(name)
        ok = n >= at_least
        detail = "" if ok else f"expected >= {at_least} call(s) to {name}, got {n} (tools called: {result.tools_called or 'none'})"
        return ok, detail
    check.__name__ = f"calls_tool({name}, at_least={at_least})"
    return check


def calls_no_tool():
    """For scope declines: no tool ran at all, regardless of what the answer
    says or how it's worded."""
    def check(result):
        ok = not result.tools_called
        return ok, ("" if ok else f"expected no tool call, got {result.tools_called}")
    check.__name__ = "calls_no_tool"
    return check


def answer_excludes(*phrases):
    """None of `phrases` may appear in the answer, case-insensitive. For rules
    the system prompt states explicitly: raw field names ("CAGR"), calling a
    not-found airport "small"/"quiet", claiming stale data is "this week"."""
    def check(result):
        low = result.answer.lower()
        hit = next((p for p in phrases if p.lower() in low), None)
        return hit is None, (f"answer contains banned phrase {hit!r}" if hit else "")
    check.__name__ = f"answer_excludes{phrases}"
    return check


def answer_includes_any(*phrases):
    """At least one of `phrases` appears, case-insensitive. Looser than
    answer_excludes on purpose — for checking the agent admitted a limit
    ("no delay data", "don't have"), where several honest phrasings are fine."""
    def check(result):
        low = result.answer.lower()
        ok = any(p.lower() in low for p in phrases)
        return ok, ("" if ok else f"answer contains none of {phrases}")
    check.__name__ = f"answer_includes_any{phrases}"
    return check


def answer_shorter_than(words):
    """A scope decline should be brief — "one short sentence declining plus
    what you CAN do" — not a paragraph."""
    def check(result):
        n = len(result.answer.split())
        ok = n <= words
        return ok, ("" if ok else f"answer is {n} words, expected <= {words}")
    check.__name__ = f"answer_shorter_than({words})"
    return check


def answer_names_a_month():
    """The answer names an actual month ("2025-11" or "November 2025"), not
    just the word "recent" left unqualified — the data-currency rule."""
    def check(result):
        ok = MONTH_PATTERN.search(result.answer) is not None
        return ok, ("" if ok else "answer never names an actual month")
    check.__name__ = "answer_names_a_month"
    return check
