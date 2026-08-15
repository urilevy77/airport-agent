#!/usr/bin/env python3
"""
cases.py — the eval case set for backend/evals/run.py.

Every case here is lifted straight from backend/TESTS.md's manual QA map (the
"question -> expected tool / must-not-say" table a human has been checking by
hand). Turning a documented row into a Case is the whole extension mechanism:
copy a row, write its check with checks.py's helpers, done — TESTS.md stays
the source of truth for WHAT correct behaviour looks like, this file is just
that same knowledge made runnable.

`context` turns run first and are NOT checked — only `question`'s outcome is.
Use them for follow-up / memory cases (TESTS.md section 6).
"""
from dataclasses import dataclass, field

import checks as c


@dataclass
class Case:
    id: str
    question: str
    checks: list
    context: list = field(default_factory=list)


CASES = [
    # ---- 1. Routing — one tool each ----------------------------------
    Case("congestion_question_calls_get_congestion",
         "How congested is SFO?",
         [c.calls_tool("get_congestion")]),

    Case("growth_question_calls_get_growth",
         "Is LAX growing?",
         [c.calls_tool("get_growth")]),

    Case("open_ended_investment_question_calls_find_candidates",
         "Which US airports should we invest in?",
         # The one TESTS.md calls out explicitly: get_candidate instead means
         # the model nominated the airports itself, from memory.
         [c.calls_tool("find_candidates")]),

    Case("named_airports_call_get_candidate_not_find_candidates",
         "Rank BOS, PVD and MHT as expansion candidates",
         [c.calls_tool("get_candidate")]),

    Case("international_question_calls_get_traffic_mix",
         "Is JFK an international airport?",
         [c.calls_tool("get_traffic_mix")]),

    Case("major_airport_question_calls_get_national_rank",
         "Is PWM a major airport?",
         [c.calls_tool("get_national_rank")]),

    # ---- 2. Routing — two tools, one turn -----------------------------
    Case("comparing_two_named_airports_calls_the_tool_twice",
         "Should Denver or JFK get an international terminal expansion?",
         [c.calls_tool("get_traffic_mix", at_least=2)]),

    Case("growing_but_losing_ground_calls_both_growth_and_rank",
         "Is SFO growing but losing ground to other airports?",
         [c.calls_tool("get_growth"), c.calls_tool("get_national_rank")]),

    Case("nyc_congestion_calls_congestion_for_each_nyc_airport",
         "How congested is NYC?",
         [c.calls_tool("get_congestion", at_least=3)]),

    # ---- 3. Plain English — no jargon leaks ---------------------------
    Case("growth_answer_avoids_internal_field_names",
         "Is EWR growing?",
         [c.calls_tool("get_growth"),
          c.answer_excludes("CAGR", "trajectory", "demand-capacity gap")]),

    Case("demand_gap_question_is_answered_in_prose_not_a_labelled_number",
         "What's the demand-capacity gap at BOS?",
         [c.answer_excludes("demand-capacity gap")]),

    # ---- 4. Not-found — must ask, never invent ------------------------
    Case("bogus_airport_code_is_not_hallucinated_as_quiet_or_small",
         "How congested is MYC?",
         [c.calls_tool("get_congestion"),
          c.answer_excludes("small", "quiet")]),

    Case("bogus_airport_in_a_ranking_is_not_silently_swapped",
         "Rank BOS, PVD, and MYC as expansion candidates",
         [c.calls_tool("get_candidate"),
          c.answer_excludes("BDL")]),

    # ---- 4b. Data currency — must name the months ----------------------
    Case("recent_months_question_names_the_actual_window",
         "How busy is SFO recently?",
         [c.answer_names_a_month()]),

    Case("this_month_question_does_not_claim_current_data",
         "How is SFO doing this month?",
         [c.answer_excludes("this month")]),

    # ---- 5. Coverage limits — must refuse, never guess -----------------
    Case("delay_question_admits_no_delay_data",
         "What are the delays at ORD?",
         [c.answer_includes_any("no delay", "don't have", "do not have", "not available", "no data")]),

    Case("fare_question_admits_no_fare_data",
         "What are ticket prices at LAX?",
         [c.answer_includes_any("no fare", "don't have", "do not have", "not available", "no data")]),

    # ---- 6. Off-topic — must decline briefly ---------------------------
    Case("off_topic_request_is_declined_without_a_tool_call",
         "Write me a short poem about airplanes.",
         [c.calls_no_tool(), c.answer_shorter_than(40)]),

    # ---- 7. Memory — a follow-up reuses context ------------------------
    Case("follow_up_airport_reference_still_calls_the_right_tool",
         "and Boston?",
         [c.calls_tool("get_congestion")],
         context=["How congested is SFO?"]),
]
