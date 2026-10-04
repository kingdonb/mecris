"""
Tests for services/beeminder_road.py — due-today math from a Beeminder goal JSON.

Python is the executable spec for task 000617; the Rust twin
(mecris-go-spin/sync-service/src/lib.rs road_value_today/beeminder_due_today)
must agree with every case here.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from services.beeminder_road import (
    GOAL_TIMEZONE,
    beeminder_due_today,
    combine_pump_and_due,
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
    # No explicit daystamp: the default must be an evaluation at goal_daystamp()
    # (America/New_York). The expected value is recomputed from the fixture with
    # real-date math (FULLROAD is linear: -2/day from 2026-09-28 through
    # 2026-10-02, extrapolated after), so this stays green on any calendar day —
    # the original hardcoded (92.0, 94.0) tuple rotted as soon as real time
    # passed 2026-10-03.
    value = road_value_today(FULLROAD)
    today = goal_daystamp()
    today_date = date(today // 10000, (today // 100) % 100, today % 100)
    if today_date >= date(2026, 9, 28):
        expected = 92.0 - 2.0 * (today_date - date(2026, 10, 2)).days
    else:
        expected = 100.0
    assert value == expected


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


def test_safebuf_ge_one_enforces_zero_due():
    # When safebuf >= 1, the user is safe today regardless of curval vs road_today.
    assert beeminder_due_today(-1, 246.0, 86.04, safebuf=1) == 0
    assert beeminder_due_today(1, 50.0, 100.0, safebuf=2) == 0


def test_incident_fixture_reviewstack_due_is_160():
    # 2026-10-01 reviewstack incident: curval=246, safebump=86.04, safebuf=0, yaw=-1 -> due=160
    assert beeminder_due_today(-1, 246.0, 86.04, safebuf=0) == 160


def test_road_epoch_timestamps_and_interpolation():
    # Epoch timestamp row fixtures matching Beeminder fullroad:
    # 1789747200 is 2026-09-18 12:00 EDT (val=397, rate=0)
    # 1791129600 is 2026-10-04 12:00 EDT (val=0, rate=-23.92)
    epoch_road = [
        [1789747200, 397.0, 0.0],
        [1791129600, 0.0, -23.92],
    ]
    # On 2026-10-01 (daystamp 20261001), 3 days before 2026-10-04:
    # Interpolated backwards: 0.0 - (-23.92 * 3) = 71.76
    val = road_value_today(epoch_road, 20261001)
    assert val is not None
    assert round(val, 2) == 71.76


# --- combine_pump_and_due (constructive interference) ------------------------

def test_combine_incident_fixture_due_dominates_and_goal_not_met():
    # 2026-10-01: pump quota 18 (met? no), Beeminder due 171 -> show 171, not met.
    assert combine_pump_and_due(18, False, 171) == (171, False)


def test_combine_pump_met_but_due_standing_means_not_met():
    # Pump quota satisfied (done >= 18) but Beeminder still demands 171.
    assert combine_pump_and_due(0, True, 171) == (171, False)


def test_combine_due_cleared_keeps_pump_verdict():
    assert combine_pump_and_due(0, True, 0) == (0, True)
    assert combine_pump_and_due(40, True, 0) == (40, True)
    assert combine_pump_and_due(5, False, 0) == (5, False)


def test_combine_pump_quota_dominates_when_larger_than_due():
    # Maintenance-style quota 40 > Beeminder due 5 -> max(), not replacement.
    assert combine_pump_and_due(40, False, 5) == (40, False)


def test_combine_tolerates_none_and_negative_inputs():
    assert combine_pump_and_due(None, True, None) == (0, True)
    assert combine_pump_and_due(-3, False, -7) == (0, False)
