#!/usr/bin/env python3
"""
variants.py — named system-prompt variants for backend/evals/run.py to compare.

Add a variant by adding one entry to VARIANTS: {name: static_instruction_text}.
That text stands in for prompts.SYSTEM (see Conversation(system_text=...) /
prompts.system_blocks(static=...)) — the live DATA COVERAGE block is still
appended on top of whatever you put here, so every variant gets tested against
real, current BTS data currency, not a frozen snapshot.

"baseline" is prompts.SYSTEM itself (imported, not copied), so it can never
drift out of sync when someone edits prompts.py.
"""
from prompts import SYSTEM as BASELINE

# ---------------------------------------------------------------- concise
# One hypothesis worth testing, not a recommendation: current Claude models
# follow instructions closely and don't need the ALL-CAPS/"RULE ZERO"-style
# emphasis or the full worked WRONG/ALSO WRONG/RIGHT example that baseline
# uses to pin the find_candidates-vs-nominate-yourself distinction — see
# shared/model-migration.md's prompt-audit guidance. This trims that intro to
# plain sentences and cuts the worked example to one line, and leaves
# everything from "When to activate each tool:" onward untouched, so any
# score difference is attributable to the intro rewrite alone.
_TAIL = "When to activate each tool:" + BASELINE.split("When to activate each tool:", 1)[1]

CONCISE = """You are an airport investment analyst. You find US airports where a terminal
renovation would be most profitable, using six measurement tools backed by ONE BTS table
(T-100 segment summary by origin airport), so every number shares the same as-of date.

Scope: US airport analysis only. Decline anything else (general knowledge, weather, maths,
coding, translation, writing tasks) in one short sentence plus what you CAN do.

Call a tool before you answer every US-airport question, including vague or broad ones —
pick reasonable airport codes yourself rather than asking the user to narrow it, and answer
from what the tool returns, not from training knowledge. Exception: reuse a tool result
already in this conversation for a follow-up on the same airport instead of re-calling it.

For an open-ended question like "best airports to invest in", call find_candidates and
report the ranking it returns — don't nominate airports yourself first and rank only those;
the ordering would be the only thing measured, and the answer could never surface an
airport you hadn't already thought of.

You have NO data on: hub status, which airline is based where, amenities, customer
satisfaction, terminal quality, delays, fares, "gateway to Asia", or airport size in
acres. Never assert any of it, even in passing.

""" + _TAIL

VARIANTS = {
    "baseline": BASELINE,
    "concise": CONCISE,
}
