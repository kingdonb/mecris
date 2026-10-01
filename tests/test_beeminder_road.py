"""
Tests for services/beeminder_road.py — due-today math from a Beeminder goal JSON.

Python is the executable spec for task 000617; the Rust twin
(mecris-go-spin/sync-service/src/lib.rs road_value_today/beeminder_due_today)
must agree with every case here.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from services.beeminder_road import (
    GOAL_TIMEZONE,
    beeminder_due_today,
    goal_daystamp,
    road_value_today,
)


# --- goal_daystamp -----------------------------------------------------------

def test_goal_daystamp_uses_new_york_not_utc():
    # 2026-10-02 02:00 UTC is still 2026-10-01 evening in New York (EDT, UTC-4).
    utc_moment = datetime(2026, 10, 2, 2, 0, tzinfo=ZoneInfo("UTC"))
    assert goal_daystamp(utc_moment) == 20261001


def test_goal_daystamp_rolls_with_new_york_midnight():
    # 2026-10-02 06:00 UTC = 2026-10-02 02:00 EDT -> new goal day.
    utc_moment = datetime(2026, 10, 2, 6, 0, tzinfo=ZoneInfo("UTC"))
    assert goal_daystamp(utc_moment) == 20261002


def test_goal_timezone_is_new_york():
    assert str(GOAL_TIMEZONE) == "America/New_York"


# --- road_value_today --------------------------------------------------------

FULLROAD = [
    [20260928, 100.0, -2.0],
    [20260929, 98.0, -2.0],
    [20260930, 96.0, -2.0],
    [20261001, 94.0, -2.0],
    [20261002, 92.0, -2.0],
]


def test_road_exact_day_match():
    assert road_value_today(FULLROAD, 20261001) == 94.0


def test_road_missing_day_falls_back_to_last_row_rate():
    # Road spans only through Sep 30; Oct 1 extrapolates 96 - 2*1 = 94.
    partial = [row for row in FULLROAD if row[0] <= 20260930]
    assert road_value_today(partial, 20261001) == 94.0


def test_road_before_first_row_returns_first_value():
    assert road_value_today(FULLROAD, 20260901) == 100.0


def test_road_without_last_row_rate_extends_flat():
    flat = [[20260928, 100.0, -2.0], [20260929, 98.0, None]]
    assert road_value_today(flat, 20261001) == 98.0


def test_road_missing_or_malformed_returns_none():
    assert road_value_today(None) is None
    assert road_value_today([]) is None
    assert road_value_today([[20261001]]) is None  # no value column
    assert road_value_today([["garbage", "x"]]) is None


def test_road_accepts_string_and_dashed_daystamps():
    dashed = [["2026-10-01", 86.0, -4.0]]
    assert road_value_today(dashed, 20261001) == 86.0
    stringy = [["20261001", 86.0, -4.0]]
    assert road_value_today(stringy, 20261001) == 86.0


def test_road_defaults_to_today_in_goal_timezone():
    # No explicit daystamp: uses goal_daystamp() — just verify it doesn't crash
    # and returns a plausible road value from the fixture.
    value = road_value_today(FULLROAD)
    assert value in (92.0, 94.0)  # today (2026-10-01 in NY) or extrapolation


# --- beeminder_due_today -----------------------------------------------------

def test_incident_fixture_do_less_due_is_cards_above_road():
    # The 2026-10-01 reviewstack state: cur=257, road limit today=86, yaw=-1.
    assert beeminder_due_today(-1, 257.0, 86.0) == 171


def test_do_less_already_below_road_owes_zero():
    assert beeminder_due_today(-1, 80.0, 86.0) == 0
    assert beeminder_due_today(-1, 86.0, 86.0) == 0


def test_do_more_sign_convention():
    assert beeminder_due_today(1, 50.0, 60.0) == 10   # below road -> owe 10
    assert beeminder_due_today(1, 65.0, 60.0) == 0    # above road -> safe


def test_fractional_demand_ceils_upward():
    # Road at 86.37: dropping to exactly 86 (171 cards from 257) is required —
    # flooring would leave the datapoint above a do-less road (derail).
    assert beeminder_due_today(-1, 257.0, 86.37) == 171


def test_missing_yaw_or_road_fabricates_nothing():
    assert beeminder_due_today(None, 257.0, 86.0) == 0
    assert beeminder_due_today(-1, 257.0, None) == 0
    assert beeminder_due_today(None, 257.0, None) == 0


def test_unparseable_curval_owes_zero():
    assert beeminder_due_today(-1, "nan-ish", 86.0) == 0


# --- safebuf invariant canary ------------------------------------------------

def test_safebuf_ge_one_implies_zero_due_for_realistic_road():
    # Invariant: when the user can coast >= 1 day, today's due must be 0.
    # (Live-data canary — the client logs a warning if violated.)
    road = road_value_today(FULLROAD, 20261001)
    # curval already at/below the road -> due 0
    assert beeminder_due_today(-1, 94.0, road) == 0
    assert beeminder_due_today(-1, 90.0, road) == 0
