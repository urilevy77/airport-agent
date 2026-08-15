#!/usr/bin/env python3
"""
run.py — compare system-prompt variants against the case set, on the REAL API.

Every (variant, case) pair is one live conversation — this costs real API
calls and needs ANTHROPIC_API_KEY set, same as the app itself.

    python3 evals/run.py                              # every variant, every case
    python3 evals/run.py --only baseline,concise
    python3 evals/run.py --model claude-haiku-4-5 --effort low
    python3 evals/run.py --case congestion_question_calls_get_congestion

Add a case: backend/TESTS.md documents the behaviour by hand; copy a row into
cases.py as a Case with a checks.py helper. Add a variant: one entry in
variants.py. Nothing here needs to change for either.

Read the FAIL lines, not just the pass count: a variant that scores lower
because it caught something baseline missed (an over-broad answer_excludes,
say) is a bug in the CASE, not evidence the variant is worse — the deterministic
checks are a floor on correctness, not a full quality judgment. For that, read
a few transcripts yourself; this harness tells you where to look, not the
whole story.
"""
import argparse
import os
import sys
import time

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.dirname(os.path.abspath(__file__))
for path in (BACKEND, EVALS):
    if path not in sys.path:
        sys.path.insert(0, path)

from agent import Conversation  # noqa: E402
from cases import CASES  # noqa: E402
from checks import Result  # noqa: E402
from llm import MODEL_EFFORTS, MODELS  # noqa: E402
from variants import VARIANTS  # noqa: E402


def tools_called_since(messages, before):
    """Every tool name an assistant turn asked for, from `before` onward — the
    same 'what actually ran' the trace line in the UI reads from, not
    anything the model claims in its own text."""
    names = []
    for message in messages[before:]:
        if message.get("role") == "assistant":
            for call in message.get("tool_calls") or []:
                names.append(call["function"]["name"])
    return names


def run_case(case, system_text, model, effort):
    """One case, one variant: a fresh Conversation, `case.context` turns run
    and discarded, then `case.question` is the turn every check inspects."""
    convo = Conversation(model=model, effort=effort, system_text=system_text)
    for turn in case.context:
        convo.ask(turn)
    before = len(convo.messages)
    started = time.monotonic()
    answer = convo.ask(case.question)
    ms = int((time.monotonic() - started) * 1000)
    result = Result(answer=answer, tools_called=tools_called_since(convo.messages, before))
    outcomes = [(check.__name__, *check(result)) for check in case.checks]
    return all(ok for _, ok, _ in outcomes), ms, outcomes


def run_variant(name, system_text, cases, model, effort):
    print(f"\n=== {name} ===")
    passed_n, total_ms = 0, 0
    for case in cases:
        passed, ms, outcomes = run_case(case, system_text, model, effort)
        total_ms += ms
        print(f"  {'ok  ' if passed else 'FAIL'}  {case.id}  ({ms}ms)")
        for check_name, ok, detail in outcomes:
            if not ok:
                print(f"          {check_name}: {detail}")
        passed_n += passed
    avg = total_ms // len(cases) if cases else 0
    print(f"  -- {passed_n}/{len(cases)} passed, avg {avg}ms/case")
    return passed_n


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated variant names (default: all)")
    parser.add_argument("--case", help="comma-separated case ids (default: all)")
    parser.add_argument("--model", choices=sorted(MODELS), default=None,
                        help="default: backend/llm.py's own default (ANTHROPIC_MODEL)")
    parser.add_argument("--effort", default=None,
                        help="must be valid for --model; default: none")
    args = parser.parse_args()

    names = args.only.split(",") if args.only else list(VARIANTS)
    unknown = [n for n in names if n not in VARIANTS]
    if unknown:
        sys.exit(f"Unknown variant(s): {', '.join(unknown)}. "
                 f"Known: {', '.join(VARIANTS)}")

    cases = CASES
    if args.case:
        wanted = set(args.case.split(","))
        cases = [c for c in CASES if c.id in wanted]
        missing = wanted - {c.id for c in cases}
        if missing:
            sys.exit(f"Unknown case id(s): {', '.join(missing)}")

    # Fail fast on an invalid model/effort pair (e.g. Haiku + any effort) —
    # this is exactly server/app.py's own validation, run here so a typo
    # doesn't burn a variant's worth of API calls before erroring out.
    if args.model and args.effort and args.effort not in MODEL_EFFORTS[args.model]:
        sys.exit(f"Effort '{args.effort}' isn't available for model '{args.model}'. "
                 f"Available: {', '.join(MODEL_EFFORTS[args.model]) or '(none)'}")

    print(f"EVAL — {len(names)} variant(s) x {len(cases)} case(s), "
          f"model={args.model or 'default'}, effort={args.effort or 'default'}")
    summary = [(name, run_variant(name, VARIANTS[name], cases, args.model, args.effort))
              for name in names]

    print("\n=== summary ===")
    for name, passed in sorted(summary, key=lambda s: -s[1]):
        print(f"  {name:20s} {passed}/{len(cases)}")


if __name__ == "__main__":
    main()
