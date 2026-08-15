"""backend/kpis.py — the candidate score, as pure functions.

The score decides which airports the product recommends, so it is the one piece
of arithmetic worth testing away from the network. Everything here runs on
synthetic rows shaped like national_table()'s output: no key, no BTS, no clock.

The two invariants that matter most are `test_dominance` and
`test_weak_load_factor_cannot_top_a_ranking`. Both are provable from the
weights rather than asserted against today's data, so neither rots when BTS
publishes another month.
"""
import server.agent_bridge  # noqa: F401  — puts backend/ on sys.path

import pytest  # noqa: E402

from kpis import (WEIGHTS, percentile, reference, score,  # noqa: E402
                  screen_metrics, verdict)

YEAR, BASE = 2025, 2022


def rows(*specs):
    """(code, year, pax, seats) tuples -> rows shaped like national_table()."""
    return [{"origin_airport_code": c, "year": str(y),
             "pax": str(p), "seats": str(s)} for c, y, p, s in specs]


def airport(code, lf, growth, seat_growth, pax_2025=1_000_000):
    """One airport with an exact load factor and exact 3-year growth rates.

    Working backwards from the numbers we want keeps the assertions readable:
    a test says "83% full, growing 10%" instead of restating the arithmetic.
    """
    seats = pax_2025 / (lf / 100)
    base_pax = pax_2025 / (1 + growth / 100) ** 3
    base_seats = seats / (1 + seat_growth / 100) ** 3
    return [(code, YEAR, pax_2025, seats), (code, BASE, base_pax, base_seats)]


def population(*airports):
    """Several airport() results -> (metrics, reference), the usual setup."""
    flat = [spec for a in airports for spec in a]
    metrics = screen_metrics(rows(*flat), YEAR, BASE)
    return metrics, reference(metrics, min_pax=0)[0]


# ---------------------------------------------------------------- percentile
def test_percentile_is_bounded_and_monotonic():
    values = sorted([1.0, 2.0, 3.0, 4.0, 5.0])
    got = [percentile(values, v) for v in values]
    assert all(0 <= p <= 100 for p in got)
    assert got == sorted(got)
    assert percentile(values, 5.0) == 100
    assert percentile(values, 0.0) == 0


def test_percentile_places_a_value_above_the_fraction_it_beats():
    values = sorted([10.0, 20.0, 30.0, 40.0])
    assert percentile(values, 20.0) == 50      # beats 2 of 4


# ---------------------------------------------------------------- metrics
def test_screen_metrics_computes_the_four_signals():
    m = screen_metrics(rows(
        ("AAA", 2025, 1331, 1600),
        ("AAA", 2022, 1000, 1600),
        ("AAA", 2019, 1000, 1600)), YEAR, BASE)["AAA"]

    assert m["lf"] == pytest.approx(83.1875)
    assert m["cagr"] == pytest.approx(10.0)         # 1331/1000 over 3 years
    assert m["seat_cagr"] == pytest.approx(0.0)
    assert m["gap"] == pytest.approx(10.0)
    assert m["vs19"] == pytest.approx(33.1)


def test_screen_metrics_skips_airports_with_no_current_year():
    m = screen_metrics(rows(("OLD", 2022, 1000, 1600)), YEAR, BASE)
    assert "OLD" not in m


def test_screen_metrics_reports_missing_history_rather_than_guessing():
    """No baseline year means no growth. It must be None, never 0 — a zero
    would read as a flat airport and be scored as one."""
    m = screen_metrics(rows(("NEW", 2025, 1000, 1600)), YEAR, BASE)["NEW"]
    assert m["cagr"] is None and m["gap"] is None
    assert m["lf"] == pytest.approx(62.5)


# ---------------------------------------------------------------- the score
def test_weights_sum_to_one():
    """Scores are only comparable to 100 if the weights are a partition."""
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_score_is_a_percentage():
    metrics, ref = population(
        airport("AAA", lf=70, growth=1, seat_growth=1),
        airport("BBB", lf=80, growth=5, seat_growth=2),
        airport("CCC", lf=90, growth=9, seat_growth=3))
    assert all(0 <= score(m, ref) <= 100 for m in metrics.values())


def test_score_is_none_without_the_history_to_compute_it():
    metrics, ref = population(
        airport("AAA", lf=70, growth=1, seat_growth=1),
        airport("BBB", lf=80, growth=5, seat_growth=2))
    thin = screen_metrics(rows(("NEW", 2025, 1000, 1600)), YEAR, BASE)["NEW"]
    assert score(thin, ref) is None


def test_dominance():
    """Higher on every component must never score lower.

    This is the property the old raw-unit score violated: it summed values on
    different scales, so a large enough outlier on one component outranked an
    airport that was better on all three.
    """
    metrics, ref = population(
        airport("LOW", lf=70, growth=1, seat_growth=3),
        airport("MID", lf=78, growth=5, seat_growth=4),
        airport("TOP", lf=86, growth=9, seat_growth=1))
    assert score(metrics["TOP"], ref) >= score(metrics["MID"], ref)
    assert score(metrics["MID"], ref) >= score(metrics["LOW"], ref)


def test_weak_load_factor_cannot_top_a_ranking():
    """The GUM regression, as arithmetic.

    GUM once ranked 2nd on a 69.6% load factor — below the 10th percentile —
    because an unbounded growth outlier outweighed it. With percentile weights,
    a sub-25th-percentile load factor caps the score at 0.4*25 + 0.3*100 +
    0.3*100 = 70, so such an airport can never lead. Derived from WEIGHTS, so
    it stays true if the weights are retuned.
    """
    cap = WEIGHTS["lf"] * 25 + WEIGHTS["cagr"] * 100 + WEIGHTS["gap"] * 100

    # One airport that is nearly empty but growing explosively, against a field
    # of fuller, calmer ones — the exact shape that broke the old score.
    metrics, ref = population(
        airport("EMPTY", lf=60, growth=40, seat_growth=1),
        *[airport(f"F{i}", lf=78 + i, growth=4, seat_growth=3) for i in range(6)])

    assert score(metrics["EMPTY"], ref) <= cap
    best = max(metrics, key=lambda c: score(metrics[c], ref))
    assert best != "EMPTY"


# ---------------------------------------------------------------- population
def test_reference_excludes_airports_below_the_floor():
    metrics = screen_metrics(rows(
        *airport("BIG", lf=80, growth=5, seat_growth=3, pax_2025=5_000_000),
        *airport("TINY", lf=95, growth=30, seat_growth=1, pax_2025=10_000)),
        YEAR, BASE)
    ref, n = reference(metrics, min_pax=1_000_000)
    assert n == 1
    assert ref["lf"] == [pytest.approx(80.0)]


def test_raising_the_floor_never_grows_the_population():
    metrics = screen_metrics(rows(*[
        spec for i in range(8)
        for spec in airport(f"A{i}", lf=75 + i, growth=3, seat_growth=2,
                            pax_2025=(i + 1) * 500_000)]), YEAR, BASE)
    sizes = [reference(metrics, min_pax=f)[1]
             for f in (0, 500_000, 1_000_000, 2_000_000, 4_000_000)]
    assert sizes == sorted(sizes, reverse=True)


def test_a_below_floor_airport_can_still_be_scored():
    """The floor decides what we SUGGEST, not what we can measure. Scoring a
    small airport the user named is fine; dropping it silently is the bug."""
    metrics = screen_metrics(rows(
        *airport("BIG", lf=80, growth=5, seat_growth=3, pax_2025=5_000_000),
        *airport("TINY", lf=95, growth=30, seat_growth=1, pax_2025=10_000)),
        YEAR, BASE)
    ref, _ = reference(metrics, min_pax=1_000_000)
    assert score(metrics["TINY"], ref) is not None


# ---------------------------------------------------------------- verdict
def test_verdict_bands_follow_the_score():
    metrics, ref = population(
        *[airport(f"A{i}", lf=70 + i * 2, growth=i, seat_growth=1)
          for i in range(9)])
    ranked = sorted(metrics, key=lambda c: score(metrics[c], ref), reverse=True)
    assert verdict(metrics[ranked[0]], ref).startswith("STRONG")
    assert verdict(metrics[ranked[-1]], ref).startswith("weak")


def test_verdict_flags_an_airport_still_below_2019():
    m = screen_metrics(rows(
        ("AAA", 2025, 900, 1000),
        ("AAA", 2022, 800, 1000),
        ("AAA", 2019, 1000, 1000)), YEAR, BASE)
    ref, _ = reference(m, min_pax=0)
    assert "still recovering" in verdict(m["AAA"], ref)


def test_verdict_says_so_when_it_cannot_score():
    metrics, ref = population(
        airport("AAA", lf=70, growth=1, seat_growth=1),
        airport("BBB", lf=80, growth=5, seat_growth=2))
    thin = screen_metrics(rows(("NEW", 2025, 1000, 1600)), YEAR, BASE)["NEW"]
    assert "not enough" in verdict(thin, ref).lower()
