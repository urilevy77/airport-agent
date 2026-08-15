#!/usr/bin/env python3
"""
selftest.py — one command to check the whole data layer against live BTS.

Replaces the five per-signal CLI printers. Run it after touching kpis.py, bts.py or
tools.py, and before any deploy.

    python3 selftest.py              all five signals on default airports
    python3 selftest.py SFO JFK      the single-airport signals on these codes

It checks INVARIANTS, not exact values — BTS adds a month at a time, so hardcoded
numbers would rot. What must always hold:

  * a load factor is a percentage, and the reported average equals the mean of
    the monthly series the chart draws
  * growth years are complete and consecutive-ish, and the last one is the year
    quoted in the answer
  * a ranking is sorted, and its length is the "of N airports" figure
  * international share is 0-100, and a weighted average trip is plausible
  * a bad airport code returns found=False, never a zeroed-out result
"""
import json
import sys
import time

from bts import (DEFAULT_MONTHS, by_year, fetch_all_months, fetch_recent_months,
                 newest_month)
from kpis import (WEIGHTS, congestion, growth, haul, latest_complete_year, mix,
                  national_rank, profile, reference, score, tier_of, verdict)
from llm import MODEL, MODEL_EFFORTS, MODELS
from prompts import SYSTEM, system_prompt
from tools import (FLOOR, TOOL_SCHEMAS, TOOLS, find_candidates, get_candidate,
                   get_congestion, get_growth, get_national_rank,
                   get_traffic_mix, screen)

ok = fail = 0


def check(label, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ok    {label}")
    else:
        fail += 1
        print(f"  FAIL  {label}   {detail}")


def head(title):
    print(f"\n{title}\n" + "-" * len(title))


# ---------------------------------------------------------------- Signals 1-4
def kpi_checks(code):
    head(f"{code}")
    rows = fetch_recent_months(code)
    check(f"{code}: recent months returned", bool(rows), f"got {len(rows)}")
    if not rows:
        return

    c = congestion(rows)                                             # Signal 1
    mean = sum(v for _, v in c["series"]) / len(c["series"])
    check("Signal 1  load factor in 0-100", 0 < c["avg"] <= 100, f"{c['avg']:.1f}")
    # The chart draws `series`; the answer quotes `avg`. They must agree, or the
    # picture contradicts the text.
    check("Signal 1  avg == mean of charted series", abs(c["avg"] - mean) < 0.05,
          f"{c['avg']:.3f} vs {mean:.3f}")
    check("Signal 1  peak >= avg", c["peak"][1] >= c["avg"])

    y = by_year(fetch_all_months(code))
    g = growth(y)                                                    # Signal 2
    check("Signal 2  growth computed", g is not None)
    if g:
        check("Signal 2  anchored on a complete year", y[g["Y"]]["months"] >= 12,
              f"{g['Y']} has {y[g['Y']]['months']} months")
        if g["gap"] is not None and g["cagr"] is not None:
            check("Signal 2  gap == pax cagr - seat cagr",
                  abs(g["gap"] - (g["cagr"] - g["seat_cagr"])) < 1e-9)

    m = mix(rows)                                                    # Signal 4
    check("Signal 4  international share 0-100", 0 <= m["intl_pct"] <= 100,
          f"{m['intl_pct']:.1f}")
    # Weighted, never summed: a summed average once produced tens of thousands.
    check("Signal 4  avg trip plausible (50-9000 mi)", 50 < m["avg_miles"] < 9000,
          f"{m['avg_miles']:.0f}")
    check("Signal 4  profile + haul labelled",
          bool(profile(m["intl_pct"])[0]) and bool(haul(m["avg_miles"])[0]))


# ---------------------------------------------------------------- Signal 5
def rank_checks(code):
    head("Signal 5  national rank")
    year = latest_complete_year()
    check("year is complete and recent", 2014 <= year <= 2100, str(year))
    r = national_rank(code)
    check(f"{code} found", r["found"])
    if r["found"]:
        check("rank within 1..N", 1 <= r["rank"] <= r["of_airports"],
              f"{r['rank']} of {r['of_airports']}")
        check("tier matches rank", r["tier"] == tier_of(r["rank"]))
        check("~1300 airports ranked", 500 < r["of_airports"] < 3000,
              str(r["of_airports"]))


# ---------------------------------------------------------------- Signal 3
def screen_checks():
    """The national screen: the population, the percentiles, and the score.

    Checks PROPERTIES, not places. Which airport ranks first changes with every
    BTS release; that a fuller, faster-growing airport outranks an emptier one
    must not.
    """
    head("Signal 3  national screen")
    year, metrics = screen()
    ref, n = reference(metrics, FLOOR)
    check("weights sum to 1", abs(sum(WEIGHTS.values()) - 1) < 1e-9, str(WEIGHTS))
    check("whole country screened", len(metrics) > 800, f"{len(metrics)} airports")
    check("investable population is a sane slice", 40 < n < 400, f"{n} above floor")

    scored = {c: score(m, ref) for c, m in metrics.items()
              if score(m, ref) is not None}
    check("scores are percentages", all(0 <= s <= 100 for s in scored.values()))

    # Raising the floor can only ever shrink the reference population.
    sizes = [reference(metrics, f)[1] for f in (0, FLOOR, 5_000_000, 20_000_000)]
    check("a higher floor never grows the population", sizes == sorted(sizes, reverse=True),
          str(sizes))

    # THE regression. GUM once ranked 2nd on a 69.6% load factor because an
    # unbounded growth outlier outweighed it. A sub-25th-percentile load factor
    # now caps the score below any plausible leader, by arithmetic.
    cap = WEIGHTS["lf"] * 25 + WEIGHTS["cagr"] * 100 + WEIGHTS["gap"] * 100
    weak_lf = sorted(ref["lf"])[:max(len(ref["lf"]) // 4, 1)]
    worst = [c for c, m in metrics.items()
             if c in scored and m["lf"] <= weak_lf[-1] and m["pax"] >= FLOOR]
    check("an empty airport cannot top the ranking",
          all(scored[c] <= cap for c in worst),
          f"{len(worst)} airports below the 25th percentile on load factor")

    top = max(scored, key=scored.get)
    check("the leader is not below-average on fullness",
          metrics[top]["lf"] >= sorted(ref["lf"])[len(ref["lf"]) // 2],
          f"{top} lf {metrics[top]['lf']:.1f}")
    check("the leader gets a phrase, not a bare number",
          isinstance(verdict(metrics[top], ref), str) and verdict(metrics[top], ref))
    check("an unscorable airport says so rather than ranking last",
          "not enough" in verdict({"lf": 80.0, "cagr": None, "gap": None,
                                   "pax": 1e6, "vs19": None}, ref).lower())
    check("as-of year is the newest complete one", year == latest_complete_year())


# ---------------------------------------------------------------- data coverage
def coverage_checks():
    """The prompt must describe the window the tools really return."""
    head("data coverage (what the prompt tells the model)")
    newest = newest_month()
    check("newest month looks like YYYY-MM", len(newest) == 7 and newest[4] == "-",
          newest)

    prompt = system_prompt()
    check("coverage block is appended to the static rules",
          prompt.startswith(SYSTEM) and "DATA COVERAGE" in prompt)
    check("the static rules are unchanged by building it",
          "DATA COVERAGE" not in SYSTEM)
    check("the prompt names the newest month", newest in prompt, newest)

    # The prompt claims a window; the tool returns one. They must be the same,
    # or the agent describes months it is not holding.
    rows = fetch_recent_months("SFO")
    first = rows[0]["reporting_month"][:7]
    last = rows[-1]["reporting_month"][:7]
    check("prompt window == what fetch_recent_months returns",
          f"{first} through {last}" in prompt, f"tool gave {first}..{last}")
    check("window is DEFAULT_MONTHS long", len(rows) == DEFAULT_MONTHS, str(len(rows)))


# ---------------------------------------------------------------- model picker
def model_checks():
    """MODELS and MODEL_EFFORTS back the /config endpoint and the /chat
    validation in server/app.py — if they ever fall out of sync, either the
    UI offers a model /chat can't look up an effort list for (KeyError, a
    500), or a model silently gets no effort options without anyone noticing.
    """
    head("model picker (server/app.py's /config + /chat validation)")
    check("MODEL_EFFORTS has exactly the same models as MODELS",
          set(MODEL_EFFORTS) == set(MODELS), str(set(MODELS) ^ set(MODEL_EFFORTS)))
    check("the default model (ANTHROPIC_MODEL / llm.MODEL) is one of MODELS",
          MODEL in MODELS, MODEL)


# ---------------------------------------------------------------- tools layer
def tool_checks():
    head("tools layer (what the model actually calls)")
    check("6 tools registered", len(TOOLS) == 6, str(sorted(TOOLS)))
    check("6 schemas", len(TOOL_SCHEMAS) == 6)
    for s in TOOL_SCHEMAS:
        # Flat name/description/input_schema — the shape the Messages API wants.
        # This block used to read s["function"]["parameters"] and died on a
        # KeyError, so none of it ran.
        check(f"schema {s['name']}: named + described + params",
              s["name"] in TOOLS and len(s["description"]) > 40
              and "properties" in s["input_schema"])
        # strict: True needs additionalProperties: False alongside it, or the
        # API rejects the tool definition outright.
        check(f"schema {s['name']}: strict",
              s.get("strict") is True
              and s["input_schema"].get("additionalProperties") is False)
    finder = [s for s in TOOL_SCHEMAS if s["name"] == "find_candidates"][0]
    check("find_candidates is callable with no arguments",
          finder["input_schema"]["required"] == [])

    # Every result must survive json.dumps — it is sent to the model and browser.
    for name, res in [("get_congestion", get_congestion("SFO")),
                      ("get_growth", get_growth("SFO")),
                      ("get_traffic_mix", get_traffic_mix("JFK")),
                      ("get_national_rank", get_national_rank("PWM")),
                      ("get_candidate", get_candidate(["BOS", "PVD"])),
                      ("find_candidates", find_candidates())]:
        try:
            json.dumps(res)
            check(f"{name} JSON-serialisable", True)
        except (TypeError, ValueError) as e:
            check(f"{name} JSON-serialisable", False, str(e))

    # The two chart arrays the web UI needs.
    c = get_congestion("SFO")
    check("get_congestion returns monthly[] for the chart",
          len(c.get("monthly", [])) == c["months"])
    g = get_growth("SFO")
    yrs = [p["year"] for p in g.get("yearly", [])]
    check("get_growth returns yearly[] for the chart", len(yrs) > 2, str(len(yrs)))
    check("yearly ends at the year quoted in the answer",
          yrs and yrs[-1] == g["through_year"], f"{yrs[-1:]} vs {g['through_year']}")
    check("yearly is sorted ascending", yrs == sorted(yrs))

    # Ranking must be ordered, or "#1" is meaningless.
    rk = get_candidate(["BOS", "PVD", "MHT", "BDL"])["ranked"]
    scores = [a["score"] for a in rk]
    check("get_candidate sorted best-first", scores == sorted(scores, reverse=True),
          str(scores))

    # Discovery: the tool that answers "which airports should we invest in".
    found = find_candidates(limit=7)
    ranked = found["ranked"]
    check("find_candidates honours limit", len(ranked) <= 7, str(len(ranked)))
    check("find_candidates sorted best-first",
          [a["score"] for a in ranked] == sorted((a["score"] for a in ranked),
                                                 reverse=True))
    check("find_candidates returns only airports above the floor",
          all(a["passengers"] >= FLOOR for a in ranked),
          str([a["passengers"] for a in ranked]))
    check("every candidate carries raw value AND percentile",
          all(a["load_factor_percentile"] is not None
              and a["annual_load_factor"] is not None for a in ranked))
    check("a raised floor returns bigger airports",
          min(a["passengers"] for a in find_candidates(
              min_annual_passengers=5_000_000)["ranked"]) >= 5_000_000)

    # Both tools must agree: one scoring path, or the ranking contradicts itself.
    shared = ranked[0]["airport"]
    named = get_candidate([shared])["ranked"][0]
    check("find_candidates and get_candidate agree on a score",
          named["score"] == ranked[0]["score"],
          f"{shared}: {named['score']} vs {ranked[0]['score']}")


def failure_checks():
    head("failure modes (must not invent data)")
    bad = get_congestion("MYC")
    check("bad code -> found=False", bad.get("found") is False)
    check("bad code -> no fake load factor", "avg_load_factor" not in bad)
    check("bad code -> explains itself", len(bad.get("error", "")) > 20)
    for fn in (get_growth, get_traffic_mix, get_national_rank):
        check(f"{fn.__name__} rejects a bad code",
              fn("ZZZZ").get("found") is False)
    mixed = get_candidate(["BOS", "MYC"])
    check("mixed batch ranks only real airports",
          [a["airport"] for a in mixed["ranked"]] == ["BOS"])
    check("mixed batch lists the missing one", mixed.get("not_found") == ["MYC"])

    # A small airport is a DIFFERENT finding from a missing one. It still gets
    # measured and ranked; it is only flagged as too small to suggest.
    tiny = get_candidate(["BOS", "HII"])
    check("a below-floor airport is still scored, not dropped",
          "HII" in [a["airport"] for a in tiny["ranked"]],
          str([a["airport"] for a in tiny["ranked"]]))
    check("a below-floor airport is flagged as such",
          tiny.get("below_investment_floor") == ["HII"],
          str(tiny.get("below_investment_floor")))
    check("a below-floor airport is NOT reported as missing",
          "HII" not in (tiny.get("not_found") or []))


if __name__ == "__main__":
    codes = [a.upper() for a in sys.argv[1:]] or ["SFO", "JFK"]
    t0 = time.time()
    print(f"SELFTEST — live BTS, airports: {', '.join(codes)}")
    for code in codes:
        kpi_checks(code)
    rank_checks(codes[0])
    screen_checks()
    coverage_checks()
    model_checks()
    tool_checks()
    failure_checks()
    print(f"\n{ok} passed, {fail} failed   ({time.time() - t0:.1f}s)")
    sys.exit(1 if fail else 0)
