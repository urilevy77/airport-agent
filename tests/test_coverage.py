"""backend/prompts.py — the data-coverage block.

BTS publishes T-100 months behind, so "recent months" is not the recent months
the reader pictures. These tests pin the arithmetic that tells the model which
months it is actually holding. Every fact is injected, so nothing here needs a
clock or a network.
"""
import datetime

import server.agent_bridge  # noqa: F401  — puts backend/ on sys.path

import pytest  # noqa: E402

from prompts import (SYSTEM, coverage_block, month_offset,  # noqa: E402
                     months_between, system_prompt)

TODAY = datetime.date(2026, 8, 15)
NEWEST = "2026-04"


def block(today=TODAY, newest=NEWEST, year=2025, window=6):
    return coverage_block(today, newest, year, window)


# ---------------------------------------------------------------- arithmetic
@pytest.mark.parametrize("ym, shift, expected", [
    ("2026-04", -5, "2025-11"),      # the real 6-month window, across a year end
    ("2026-04", 0, "2026-04"),
    ("2026-01", -1, "2025-12"),
    ("2025-12", 1, "2026-01"),
    ("2026-04", -12, "2025-04"),
])
def test_month_offset(ym, shift, expected):
    assert month_offset(ym, shift) == expected


@pytest.mark.parametrize("ym, today, expected", [
    ("2026-04", datetime.date(2026, 8, 15), 4),
    ("2026-08", datetime.date(2026, 8, 1), 0),
    ("2025-12", datetime.date(2026, 3, 9), 3),
    ("2026-09", datetime.date(2026, 8, 1), 0),     # never negative
])
def test_months_between(ym, today, expected):
    assert months_between(ym, today) == expected


# ---------------------------------------------------------------- the block
def test_block_states_the_measured_lag_not_a_hardcoded_one():
    """The lag must follow the inputs. A hardcoded '4 months' would be right
    today and quietly wrong every month after."""
    assert "last 4 months" in block()
    assert "last 7 months" in block(today=datetime.date(2026, 11, 2))
    assert "last 1 month" in block(newest="2026-07")


def test_block_names_the_window_the_tools_actually_return():
    """This is the whole point: get_congestion averages 2025-11..2026-04 while
    an August reader pictures March-August."""
    text = block()
    assert "2025-11 through 2026-04" in text


def test_block_window_follows_the_configured_month_count():
    assert "2026-02 through 2026-04" in block(window=3)


def test_block_carries_todays_date_and_the_complete_year():
    text = block()
    assert "2026-08-15" in text
    assert "2025" in text


def test_block_handles_current_data_without_claiming_missing_months():
    text = block(newest="2026-08")
    assert "current to this month" in text
    assert "NO data for the last" not in text


def test_block_is_pure():
    """Same inputs, same text — no clock, no network, no module state."""
    assert block() == block()


# ---------------------------------------------------------------- assembly
def test_system_prompt_appends_coverage_after_the_static_rules():
    """Static prefix first, volatile part last, so the long rules stay
    byte-identical between requests and remain cacheable."""
    text = system_prompt(today=TODAY, newest=NEWEST, complete_year=2025)
    assert text.startswith(SYSTEM)
    assert text.endswith(block())


def test_system_prompt_does_not_mutate_the_static_rules():
    before = SYSTEM
    system_prompt(today=TODAY, newest=NEWEST, complete_year=2025)
    assert SYSTEM == before
    assert "DATA COVERAGE" not in SYSTEM
