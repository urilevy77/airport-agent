#!/usr/bin/env python3
"""
tools.py — the five tools the model can activate, and their schemas.

Each tool is a thin wrapper that turns a signal module into STRUCTURED data
(a dict), never printed text: the model reads these results, so they must be
small, self-describing, and honest about failure.

TWO EXPORTS the agent needs:
  TOOLS         name -> function, for dispatching what the model asked for
  TOOL_SCHEMAS  the routing menu sent to the model on every call

Add a signal by writing one wrapper + one schema() entry — nothing else changes.
"""
from bts import (by_year, fetch_all_months, fetch_recent_months, full_year,
                 national_table)
from kpis import (congestion, growth, haul, latest_complete_year, mix,
                  national_rank, percentiles, profile, reference, score,
                  screen_metrics, verdict)

def rnd(v, digits=1):
    """Round floats for the model; pass ints/None/strings through untouched."""
    return round(v, digits) if isinstance(v, float) else v

def not_found(airport):
    """No rows for this code. Say so explicitly — a zeroed result would read as
    a real but quiet airport, and the model would report it as fact."""
    return {"airport": airport, "found": False,
            "error": f"No BTS data for '{airport}'. It may not be a valid IATA "
                     "origin-airport code, or it has no T-100 traffic. Check the "
                     "code and retry (e.g. NYC is a city, not an airport: use "
                     "JFK, LGA or EWR)."}

# ---------- the tools ----------
def get_congestion(airport):
    rows = fetch_recent_months(airport)
    if not rows:
        return not_found(airport)
    m = congestion(rows)
    return {"airport": airport, "found": True,
            "months": m["n"],
            "avg_load_factor": rnd(m["avg"]),
            "verdict": m["verdict"],
            "peak_month": m["peak"][0],
            "peak_load_factor": rnd(m["peak"][1]),
            # The monthly values behind the average. The model is told to quote the
            # sentences, not this; the web UI charts it so the reader can see the
            # seasonal swing an average hides.
            "monthly": [{"month": mo, "load_factor": rnd(v)} for mo, v in m["series"]]}

def millions(pax):
    """34_200_000 -> '34.2M'. A raw 9-digit number tells the reader nothing."""
    return f"{pax / 1e6:.1f}M"

def recovery_phrase(vs19):
    """The sign of vs_2019 is the whole meaning, so spell it out in words."""
    if vs19 is None:
        return "No 2019 baseline in the data, so recovery is unknown."
    if vs19 >= 0:
        return f"Busier than before the pandemic - {vs19:.1f}% ABOVE its 2019 level."
    return (f"Still {abs(vs19):.1f}% BELOW its 2019 level - it has not fully "
            "recovered yet.")

def momentum_phrase(trajectory):
    """'fading' alone is cryptic; carry the two rates that produced the label."""
    if not trajectory:
        return "Not enough years to tell whether growth is speeding up or slowing."
    first, last, label = trajectory
    trend = {"accelerating": "speeding up", "fading": "slowing down",
             "steady": "holding steady"}[label]
    return (f"Growth is {trend}: yearly growth went from {first:+.1f}% to "
            f"{last:+.1f}%.")

def airline_response_phrase(gap):
    """THE investment signal. A positive gap means passengers are outgrowing the
    seats airlines supply — demand the airport cannot absorb. Negative means
    airlines are already fixing it themselves, so a terminal adds less."""
    if gap is None:
        return "Not enough years to compare passenger growth against seat growth."
    if gap > 0.5:
        return (f"Passengers are growing FASTER than airlines add seats "
                f"({gap:+.1f} points/year) - flights keep getting fuller, a sign "
                "of demand the airport cannot absorb.")
    if gap < -0.5:
        return (f"Airlines are adding seats FASTER than passengers grow "
                f"({gap:+.1f} points/year) - the crowding is easing on its own.")
    return (f"Passenger growth and added seats are roughly in step "
            f"({gap:+.1f} points/year).")

def get_growth(airport):
    rows = fetch_all_months(airport)
    if not rows:
        return not_found(airport)
    y = by_year(rows)
    g = growth(y)
    if not g:
        return {"airport": airport, "found": True,
                "error": "Airport exists but has fewer than 2 complete years of "
                         "data, so growth cannot be computed."}
    cagr = g["cagr"]
    return {
        "airport": airport, "found": True,
        "through_year": g["Y"],
        "passengers_latest_year": millions(y[g["Y"]]["pax"]),
        "growth_per_year_pct": rnd(cagr),
        "growth_meaning": (
            f"Passengers grew {cagr:+.1f}% per year on average over the last 3 "
            f"years ({g['Y'] - 3} to {g['Y']})."
            if cagr is not None else
            "Fewer than 4 years of data, so an average growth rate is not reliable."),
        "vs_prepandemic_pct": rnd(g["vs19"]),
        "recovery": recovery_phrase(g["vs19"]),
        "momentum": momentum_phrase(g["trajectory"]),
        "airline_response": airline_response_phrase(g["gap"]),
        # Passengers per year, for charting the actual curve behind the rates.
        # COMPLETE years only: the table always holds a partial current year, and
        # plotting it would draw a collapse that never happened.
        "yearly": [{"year": yr, "passengers": int(y[yr]["pax"])}
                   for yr in sorted(y) if full_year(y, yr)],
    }

# ---------- Signal 3: the national screen, shared by both candidate tools ----------
FLOOR = 500_000     # default minimum annual passengers to SUGGEST an airport
TOP_N = 10

def screen():
    """(year, metrics-for-every-US-airport) as of the newest complete year.

    ONE cached query behind both candidate tools, so discovery and ranking can
    never disagree, and asking a second candidate question costs nothing.
    """
    year = latest_complete_year()
    base = year - 3
    return year, screen_metrics(national_table([2019, base, year]), year, base)

def pct_of(p, key):
    """A percentile as a whole number — 87, not 87.32. The extra digits imply a
    precision a rank among 144 airports does not have."""
    return int(round(p[key])) if key in p else None

def entry(code, m, ref):
    """One ranked airport: every score component as a raw value AND a percentile.

    Both, deliberately. The raw number is the fact; the percentile is what makes
    it mean anything ("82.4%" is meaningless until you know the country sits
    between 74 and 82).
    """
    p = percentiles(m, ref)
    return {"airport": code,
            "score": rnd(score(m, ref)),
            "verdict": verdict(m, ref),
            "passengers": int(m["pax"]),
            # ANNUAL, unlike get_congestion's rolling 6 months. Named so the
            # model cannot quietly treat the two as the same measurement.
            "annual_load_factor": rnd(m["lf"]),
            "load_factor_percentile": pct_of(p, "lf"),
            "growth_per_year_pct": rnd(m["cagr"]),
            "growth_percentile": pct_of(p, "cagr"),
            # A SENTENCE, not a number: the model read the bare gap as a
            # capacity level and reported "demand is below seated capacity
            # (-0.8%)", inverting the meaning. It is a rate comparison, so it
            # has to arrive already interpreted.
            "demand_vs_seats": airline_response_phrase(m["gap"]),
            "demand_percentile": pct_of(p, "gap"),
            "vs_2019_pct": rnd(m["vs19"])}

def ranking_of(codes, metrics, ref, year, floor, limit=None):
    """Shared tail of both tools: score, sort, and describe the population."""
    ranked = sorted((c for c in codes if score(metrics[c], ref) is not None),
                    key=lambda c: score(metrics[c], ref), reverse=True)
    if limit:
        ranked = ranked[:limit]
    return {"as_of_year": year,
            "population": {"airports": reference(metrics, floor)[1],
                           "min_annual_passengers": floor,
                           "note": f"Scores are percentiles against US airports "
                                   f"with at least {floor:,} passengers in {year}."},
            "ranked": [entry(c, metrics[c], ref) for c in ranked]}

def find_candidates(min_annual_passengers=FLOOR, limit=TOP_N):
    """Screen EVERY US airport and return the best expansion candidates.

    The tool that makes the headline question answerable from data: without it
    the model has to nominate the airports itself, from memory, and only the
    ranking of that guess is measured.
    """
    floor = max(int(min_annual_passengers or FLOOR), 0)
    limit = min(max(int(limit or TOP_N), 1), 50)
    year, metrics = screen()
    ref, _ = reference(metrics, floor)
    pool = [c for c, m in metrics.items() if m["pax"] >= floor]
    return ranking_of(pool, metrics, ref, year, floor, limit)

def get_candidate(airports):
    """Rank codes the USER named, against the same national population.

    Airports are separated into three buckets rather than one ranking, because
    "no data", "too small to suggest" and "low scoring" are three different
    findings and collapsing them would let the model report a missing airport
    as a bad one.
    """
    codes = [a.strip().upper() for a in airports]
    year, metrics = screen()
    ref, _ = reference(metrics, FLOOR)

    known = [c for c in codes if c in metrics]
    missing = [c for c in codes if c not in metrics]
    thin = [c for c in known if score(metrics[c], ref) is None]
    below = [c for c in known if metrics[c]["pax"] < FLOOR]

    result = ranking_of(known, metrics, ref, year, FLOOR)
    if missing:
        result["not_found"] = missing
        result["note"] = ("No BTS data for these codes - they are excluded from the "
                          "ranking, NOT ranked low. Verify them and retry.")
    if below:
        result["below_investment_floor"] = below
        result["floor_note"] = (
            f"These are scored and ranked, but carry fewer than {FLOOR:,} "
            f"passengers a year - small enough that a terminal project is "
            f"probably not the right question. Say so.")
    if thin:
        result["insufficient_history"] = thin
        result["history_note"] = ("Too few years of data to score these. They are "
                                  "listed, NOT ranked low.")
    return result

def get_national_rank(airport):
    """Signal 5: where this airport sits among ALL US airports, and which way it moved.

    Ranked live from the same table as Signal 1-3, so every airport gets a real
    rank out of ~1,300 — small airports included — as of the same year.
    """
    r = national_rank(airport)
    if not r["found"]:
        return not_found(airport)

    moved, direction = r["places_moved_10y"], r["direction"]
    if moved is None:
        movement = ("No data from 10 years ago, so we cannot say whether it is "
                    "gaining or losing ground nationally.")
    elif direction == "climbing":
        movement = (f"It has CLIMBED {moved} places in 10 years (was rank "
                    f"{r['rank_10y_ago']}) - it is winning passengers faster than "
                    "other US airports.")
    elif direction == "falling":
        movement = (f"It has FALLEN {abs(moved)} places in 10 years (was rank "
                    f"{r['rank_10y_ago']}) - other airports grew faster, so it is "
                    "losing ground nationally even if its own traffic rose.")
    else:
        movement = (f"Its national position is unchanged in 10 years (rank "
                    f"{r['rank_10y_ago']} then, {r['rank']} now).")

    return {**r,
            "size": f"Rank {r['rank']} of {r['of_airports']} US airports by "
                    f"passengers in {r['year']} - a {r['tier']}.",
            "movement": movement}

def get_traffic_mix(airport):
    """Signal 4: what KIND of passenger, which decides what kind of terminal."""
    rows = fetch_recent_months(airport)
    if not rows:
        return not_found(airport)
    m = mix(rows)
    if not m:
        # Rows exist but carry no passengers — a freight-only or dormant month.
        # Dereferencing None here used to raise, and the model saw a raw
        # TypeError instead of something it could explain.
        return {"airport": airport, "found": True,
                "error": f"{airport} has rows but no passengers in the last "
                         f"{len(rows)} months, so there is no traffic mix to "
                         "report. It may be freight-only or currently dormant."}
    label, why = profile(m["intl_pct"])
    hl, hwhy = haul(m["avg_miles"])
    return {"airport": airport, "found": True,
            "months": m["n"],
            "international_share_pct": rnd(m["intl_pct"]),
            "airport_type": label,
            "terminal_implication": why,
            "avg_trip_miles": int(m["avg_miles"]),
            "trip_length": hl,
            "trip_implication": hwhy}

# ---------- schemas: the routing menu the model sees ----------
ONE_AIRPORT = {"airport": {"type": "string", "description": "IATA code, e.g. SFO"}}
MANY_AIRPORTS = {"airports": {"type": "array", "items": {"type": "string"},
                              "description": "IATA codes, e.g. ['BOS','BDL','PVD']"}}

SCREEN_ARGS = {
    "min_annual_passengers": {
        "type": "integer",
        "description": "Smallest airport worth suggesting, by passengers per "
                       "year. Default 500000. Raise it (e.g. 5000000) when the "
                       "user clearly means large airports."},
    "limit": {"type": "integer",
              "description": "How many airports to return. Default 10."}}

def schema(fn, description, properties, required=None):
    """Wrap one tool in the shape the Messages API expects.

    `required` defaults to every property — right for the airport-code tools,
    where a missing code means the model guessed. Pass it explicitly for tools
    with real defaults, so the model can call them with no arguments at all.
    """
    return {"name": fn.__name__,
            "description": description,
            "input_schema": {"type": "object", "properties": properties,
                             "required": list(properties) if required is None
                                         else required}}

TOOL_SCHEMAS = [
    schema(get_congestion,
           "Signal 1. How full an airport's flights are (load factor) over recent months. "
           "Use for congestion / how busy / how full.",
           ONE_AIRPORT),
    schema(get_growth,
           "Signal 2. Whether an airport is growing: average yearly passenger growth, "
           "whether it has recovered past 2019, whether growth is speeding up or "
           "slowing, and whether airlines are adding seats fast enough to keep up. "
           "Returns plain-English sentences - quote them rather than the raw numbers.",
           ONE_AIRPORT),
    schema(find_candidates,
           "Signal 3a. SEARCH every US airport for the best terminal-expansion "
           "candidates and return the top ones ranked. Use this whenever the user "
           "has NOT named specific airports - 'which airports should we invest in', "
           "'find me candidates', 'where should we build', 'best expansion "
           "opportunities'. Do NOT nominate airports yourself and rank those: this "
           "tool measures all ~1,500 of them, which is the entire point.",
           SCREEN_ARGS, required=[]),
    schema(get_candidate,
           "Signal 3b. Score/rank the SPECIFIC airports the user named as "
           "terminal-expansion candidates (full now + growing + demand outrunning "
           "capacity), against the same national population find_candidates uses. "
           "Use when codes or places are given - 'compare BOS and PVD', 'rank the "
           "New England airports'. If no airports were named, use find_candidates.",
           MANY_AIRPORTS),
    schema(get_traffic_mix,
           "Signal 4. What KIND of traffic an airport has: international vs domestic "
           "share and average trip length, and what that implies for the terminal "
           "(customs halls, wide-body gates, dwell time). Use for 'international', "
           "'domestic', 'long-haul', 'what kind of airport', or WHAT to build once "
           "another signal shows expansion is justified.",
           ONE_AIRPORT),
    schema(get_national_rank,
           "Signal 5. How the airport ranks among ALL ~1,300 US airports by passengers, "
           "and whether it has climbed or fallen over 10 years. Use for size, "
           "national standing, market share, 'is it a major airport', or to "
           "sanity-check growth: an airport can grow yet still lose rank. Returns "
           "plain-English sentences (size, movement) - quote those.",
           ONE_AIRPORT),
]

TOOLS = {fn.__name__: fn for fn in
         (get_congestion, get_growth, find_candidates, get_candidate,
          get_traffic_mix, get_national_rank)}
