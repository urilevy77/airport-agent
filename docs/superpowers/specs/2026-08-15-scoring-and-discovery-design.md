# Candidate scoring and discovery — design

Replace the expansion-candidate score with a percentile-normalised, explicitly
weighted one, and add a national screening tool so the agent can *find*
candidate airports instead of only ranking a list the model recalled.

## Goal

"Which US airports should we invest in?" should be answered by measuring all
~1,500 airports in the BTS table, not by the model naming ten famous airports
from training knowledge and scoring those. And the resulting ranking should
implement the methodology the system prompt claims it implements.

## What exists today

- `backend/kpis.py:99` — `score(b) = lf + cagr + max(gap, 0)`. Raw units,
  summed. Its own comment says "Needs normalizing".
- `backend/kpis.py:109` — `verdict(b)` against hardcoded cutoffs (82/78 load
  factor).
- `backend/tools.py:120` — `get_candidate(airports)` fetches full history per
  airport in parallel and ranks them. Requires the caller to already know which
  airports to ask about.
- `backend/prompts.py:66-79` — describes a four-signal methodology in a stated
  order of weight.
- No tool screens the national table. `kpis.py:190` (`ranking`) proves the
  query pattern works but is used only for size rank (Signal 5).

### The defect, measured

Against the 144 airports with ≥500k passengers in 2025:

| | p10 | p50 | p90 | min | max |
|---|---|---|---|---|---|
| load factor | 74.0 | 78.6 | 82.4 | 65.8 | 86.0 |
| 3-year passenger CAGR | 1.1 | 5.4 | 10.4 | −6.9 | 35.9 |

The components are summed in raw units, so each one's influence is set by its
*spread*, which nobody chose and which drifts as the data changes. Growth
currently dominates by accident (Spearman of score against CAGR 0.838, against
load factor 0.783, against the demand-vs-seats gap 0.383) — even though
`prompts.py:71` calls the gap "the strongest signal".

Unbounded outliers then decide the ranking. The current top 3:

- **PVU** — +35.9%/yr, worth 36 free points against a field whose whole
  interquartile range is a few points wide.
- **GUM** — ranked 2nd with a load factor of 69.6%, *below the 10th
  percentile*. Rule 1 of the documented methodology is "full now".
- **HVN** — ranked 3rd with a gap of −2.6, meaning airlines are already adding
  seats faster than passengers arrive. The prompt says that makes a terminal
  worth *less*.

Two of the top three are airports the stated methodology calls weak.

## Decisions

**Percentile normalisation, not z-scores or fixed min-max ranges.** Load factor
is bounded and left-skewed; growth has a long right tail (one airport at
+35.9%). Z-scores assume neither. Fixed min-max ranges would work, but the
range endpoints are arbitrary judgement calls — the same criticism as the
current hardcoded thresholds, relocated rather than answered. Percentiles are
derived from the data, cap outlier influence by construction, and produce the
language the prompt already wants: "88th percentile on fullness" rather than
"82.4%, which we call elevated".

**Weights are explicit and live in one constant:** load factor 0.40, passenger
growth 0.30, demand-vs-seats gap 0.30. Fullness is the largest single input;
growth and unmet demand together outweigh it. The below-2019 flag stays a
*qualifier* on the verdict, not a scored component — it changes how the growth
number should be read, it is not independent evidence.

Simulated against live 2025 data, this moves **GUM from 2nd to 49th** and
**HVN from 3rd to 90th**, and spreads scores across 41.6–99.6 instead of
clustering. ATL lands 44th: 91st percentile on fullness, 34th on growth — the
"peak that has already arrived" case, correctly identified.

**One scoring path for both tools.** `get_candidate` is re-pointed at the same
national table `find_candidates` uses, so discovery and ranking can never
disagree, and ranking N airports costs one cached query instead of N
full-history fetches.

*Cost accepted:* `get_candidate`'s load factor becomes **annual** rather than
the rolling 6-month window `blocks()` uses today, so it can differ slightly
from `get_congestion` for the same airport. Mitigated by naming the field
`load_factor_<year>` and stating the difference in the prompt.

**The size floor filters discovery, not scoring.** Percentiles are always
computed over the above-floor population, but any airport can be *placed* on
that population. So `find_candidates` will not *suggest* a 40,000-passenger
airfield, while `get_candidate("HVN")` still scores HVN and flags it as below
the investment floor rather than silently dropping it. Dropping a named
airport would repeat the bug in `TESTS.md` §4 — a missing airport must never be
presentable as a low-scoring one.

**No region parameter.** The table has no state or region column; city is
`'Boston (BOS)'`. Regions stay handled as they are now, with the model passing
codes to `get_candidate`.

**Known blind spot, documented rather than fixed: capacity endogeneity.** PVU
scores at the 100th percentile on all three signals, but Provo opened a new
terminal in 2022 — its 35.9%/yr growth *is* that terminal, not unmet demand for
one. In T-100, capacity that was just added and demand that cannot be served
look identical. No weighting fixes this; the agent must say so.

## Architecture

### `backend/bts.py`

Add `national_table(years)` — one Socrata query, grouped by airport and year,
returning passengers/seats/departures for every US origin airport. Verified:
2,677 rows across 1,524 airports in 2.4s. Goes through the existing `api()`, so
it is URL-cached for the life of the process and a second candidate question in
the same conversation is free.

Fetches three years: 2019 (recovery baseline), current−3 (growth baseline), and
the latest complete year from the existing `latest_complete_year()`.

### `backend/kpis.py`

Stays pure — rows in, dict out, no I/O — per CLAUDE.md.

- `screen_metrics(national_rows, min_pax)` → `{code: {pax, lf, cagr, seat_cagr, gap, vs19}}`
- `percentile(sorted_values, x)` → 0–100
- `score(metrics, population)` → weighted sum of the three percentiles, 0–100.
  Replaces the current `score(b)`.
- `verdict(metrics, population)` → banded on the composite score rather than the
  hardcoded 82/78 load-factor cutoffs: **STRONG candidate** at score ≥ 75,
  **moderate** at ≥ 55, **weak** below. The below-2019 qualifier
  ("(still recovering)") is appended as today.
- `WEIGHTS = {"lf": 0.40, "cagr": 0.30, "gap": 0.30}` — single source of truth
  for both the code and this document.

`blocks()` remains for the per-airport detail path used by `selftest.py`.

### `backend/tools.py`

Two tools, one shared helper, one output shape:

```
find_candidates(min_annual_passengers=500000, limit=10)   # national screen
get_candidate(airports)                                   # a named list
```

Both return:

```json
{"as_of_year": 2025,
 "population": {"airports": 144, "min_annual_passengers": 500000},
 "ranked": [{"airport": "SFO", "score": 81.6, "verdict": "...",
             "passengers": 26500000,
             "load_factor_2025": 82.3, "load_factor_percentile": 87,
             "growth_per_year_pct": 8.9, "growth_percentile": 79,
             "demand_vs_seats": "<sentence>", "demand_percentile": 77,
             "vs_2019_pct": 4.2}],
 "not_found": [], "below_floor": []}
```

Each entry carries the raw value *and* its percentile, so the model can ground a
claim in both. `demand_vs_seats` stays a pre-interpreted sentence via the
existing `airline_response_phrase()` — `tools.py:139` records why: the model
once read a bare gap as a capacity level and inverted its meaning.

`schema()` (`tools.py:203`) forces `required = list(properties)`; it needs an
optional-arguments path for the two defaulted parameters.

### `backend/prompts.py`

1. Routing: `find_candidates` when the user names no airports; `get_candidate`
   when they do. This is the edit that stops the headline question being
   answered from training recall.
2. Replace the signal ordering at `prompts.py:66-79` with the actual 40/30/30
   weighting, in words, so prose and code agree.
3. The score is 0–100 and comparable across questions — still a ranking
   heuristic, never a rating or a financial projection.
4. Which tool reports which load factor, and over what window.
5. The capacity-endogeneity caveat.
6. The floor is adjustable — raise it when the user clearly means large
   airports.

### `frontend/src/charts/registry.jsx`

One entry: `find_candidates` → the existing `CandidateChart`, which reads only
`data.ranked[].{airport, score, verdict}` and `data.not_found`. All preserved,
so no new component.

`CandidateChart`'s caption needs rewriting: it hardcodes the old formula and
claims "the score has no unit", both now false.

### Bundled fixes

- `tools.py:187` — `mix()` returns `None` when an airport has zero passengers,
  and `get_traffic_mix` dereferences it immediately.
- `selftest.py:111` — reads `s["function"]["parameters"]`, but `schema()`
  returns a flat `{name, description, input_schema}`. The whole tool-schema
  check has been dying on a `KeyError`.

## Testing

Invariants against live BTS, never fixed values — the table gains a month at a
time and hardcoded numbers rot. Added to `selftest.py`.

**Scoring**
- `WEIGHTS` sums to 1.0
- `percentile` returns 0–100 and is monotonic in its argument
- every score is within 0–100
- **dominance** — an airport at a higher percentile on all three components
  scores at least as high as one below it on all three
- **the GUM/HVN regression, as arithmetic** — a sub-25th-percentile load factor
  caps the score at 70 (`0.4·25 + 0.3·100 + 0.3·100`), so such an airport can
  never top a ranking. Provable from the weights rather than asserted against
  today's data, so it cannot rot.

**Discovery**
- `find_candidates` returns ≤ `limit`, sorted descending, every result at or
  above the floor
- raising the floor never grows the population
- a named below-floor airport is scored and flagged, never dropped
- both tools return the same score for an airport present in both

**Docs**
`TESTS.md:68` ("BOS first, scores 74–90") is stale once scores become
percentile-based, and the file needs a `find_candidates` routing row.

## Out of scope

`origin_airport_name` and `origin_city_name` give a real code↔name mapping,
which is the raw material for making IATA resolution a data lookup rather than
a model guess. Worth doing — it is the one remaining place where training
knowledge enters the data path — but it is a separate change.
