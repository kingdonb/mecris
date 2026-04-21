"""
tests/test_smart_nag.py — Unit tests for services/smart_nag.py

Covers: success_probability, evaluate_nag, find_peak_success_window.
Uses synthetic walk data with a fixed 'now' so tests are deterministic.
"""
import pytest
from datetime import datetime, timedelta

from services.smart_nag import (
    HISTORY_DAYS,
    SUPPRESS_THRESHOLD,
    WINDOW_HOURS,
    evaluate_nag,
    find_peak_success_window,
    success_probability,
)

# Fixed reference point — all synthetic walks are relative to this.
FIXED_NOW = datetime(2026, 4, 21, 15, 0)  # 3 PM on 21 Apr 2026


def make_walks_at_hour(hour: int, count: int) -> list:
    """Return `count` walk datetimes all at `hour`, one per day, ending today.

    Walk at index 0 is today (hour < FIXED_NOW hour so it's in the past),
    index 29 is 29 days ago — all within the 30-day history window.
    """
    return [
        FIXED_NOW.replace(hour=hour, minute=0, second=0, microsecond=0)
        - timedelta(days=i)
        for i in range(count)
    ]


# ── success_probability ─────────────────────────────────────────────────────


def test_probability_empty_history():
    assert success_probability([], 14, now=FIXED_NOW) == 0.0


def test_probability_perfect_window():
    """30 walks at hour 14 → 30/30 = 100%."""
    walks = make_walks_at_hour(14, 30)
    assert success_probability(walks, 14, now=FIXED_NOW) == pytest.approx(1.0)


def test_probability_partial_window():
    """21/30 walks at hour 14 → 70% probability (right at threshold)."""
    walks = make_walks_at_hour(14, 21)
    assert success_probability(walks, 14, now=FIXED_NOW) == pytest.approx(21 / 30)


def test_probability_wrong_hour():
    """Walks at hour 14 give 0% probability at hour 20 (no window overlap)."""
    walks = make_walks_at_hour(14, 25)
    assert success_probability(walks, 20, now=FIXED_NOW) == 0.0


def test_probability_adjacent_hour_included():
    """Hour 13 is within ±1h of walks at hour 14 — probability should be > 0."""
    walks = make_walks_at_hour(14, 25)
    p = success_probability(walks, 13, now=FIXED_NOW)
    assert p > 0.0


def test_probability_stale_walks_excluded():
    """Walks older than HISTORY_DAYS are not counted."""
    old_walks = [FIXED_NOW - timedelta(days=HISTORY_DAYS + 5)]
    assert success_probability(old_walks, old_walks[0].hour, now=FIXED_NOW) == 0.0


def test_probability_midnight_wrap():
    """Walks at hour 23 count for target_hour=0 (window wraps midnight)."""
    walks = make_walks_at_hour(23, 25)
    p = success_probability(walks, 0, now=FIXED_NOW)
    assert p > 0.0


# ── evaluate_nag ────────────────────────────────────────────────────────────


def test_suppress_during_high_success_window():
    """Hour 14 has >70% walk rate → suppress the nag, no catch-up."""
    walks = make_walks_at_hour(14, 25)  # 25/30 ≈ 83 %
    result = evaluate_nag(walks, current_hour=14, has_walked_today=False, now=FIXED_NOW)

    assert result["should_suppress"] is True
    assert result["catch_up_nag"] is False
    assert result["probability"] > SUPPRESS_THRESHOLD


def test_no_suppress_low_probability():
    """Hour 14 has only 5/30 ≈ 17 % → neither suppress nor catch-up."""
    walks = make_walks_at_hour(14, 5)
    result = evaluate_nag(walks, current_hour=14, has_walked_today=False, now=FIXED_NOW)

    assert result["should_suppress"] is False
    assert result["catch_up_nag"] is False


def test_catch_up_nag_after_success_window_passes():
    """Success window at hour 14 (>70 %), now hour 17 — catch-up nag fires."""
    walks = make_walks_at_hour(14, 25)  # high-prob at hours 13–15
    result = evaluate_nag(walks, current_hour=17, has_walked_today=False, now=FIXED_NOW)

    assert result["should_suppress"] is False
    assert result["catch_up_nag"] is True
    assert "catch-up" in result["reason"].lower()


def test_no_nag_if_already_walked():
    """User already walked → suppress regardless of the hour or history."""
    walks = make_walks_at_hour(14, 25)
    result = evaluate_nag(walks, current_hour=17, has_walked_today=True, now=FIXED_NOW)

    assert result["should_suppress"] is True
    assert result["catch_up_nag"] is False
    assert "already walked" in result["reason"]


def test_no_catch_up_when_no_high_prob_window():
    """No high-probability window in history → never fire catch-up."""
    walks = make_walks_at_hour(14, 5)  # only 17 % — below threshold
    result = evaluate_nag(walks, current_hour=20, has_walked_today=False, now=FIXED_NOW)

    assert result["catch_up_nag"] is False


def test_no_suppress_empty_history():
    """No walk history → nag should not be suppressed."""
    result = evaluate_nag([], current_hour=14, has_walked_today=False, now=FIXED_NOW)

    assert result["should_suppress"] is False
    assert result["catch_up_nag"] is False
    assert result["probability"] == 0.0


def test_suppress_exactly_at_adjacent_hour():
    """Hour 15 is still within the ±1h window of walks at 14 → suppress."""
    walks = make_walks_at_hour(14, 25)
    result = evaluate_nag(walks, current_hour=15, has_walked_today=False, now=FIXED_NOW)

    assert result["should_suppress"] is True
    assert result["catch_up_nag"] is False


def test_no_suppress_two_hours_past_window():
    """Hour 16 is just past the ±1h window of walks at 14 → catch-up fires."""
    walks = make_walks_at_hour(14, 25)
    result = evaluate_nag(walks, current_hour=16, has_walked_today=False, now=FIXED_NOW)

    # hour 16 probability = 0 (walks at 14, window 15-17 → 14 not in [15,17])
    # peak at hour 13 (first with 83 %), 16 > 13+1=14 → catch-up
    assert result["catch_up_nag"] is True


# ── find_peak_success_window ─────────────────────────────────────────────────


def test_peak_hour_within_walk_concentration():
    """Peak hour should be inside the walk window (hours 13–15 for walks at 14)."""
    walks = make_walks_at_hour(14, 25)
    peak_hour, peak_prob = find_peak_success_window(walks, now=FIXED_NOW)

    assert peak_prob > SUPPRESS_THRESHOLD
    assert 13 <= peak_hour <= 15


def test_peak_returns_sentinel_for_empty_history():
    """No history → peak_hour == -1, peak_prob == 0.0."""
    peak_hour, peak_prob = find_peak_success_window([], now=FIXED_NOW)

    assert peak_hour == -1
    assert peak_prob == 0.0
