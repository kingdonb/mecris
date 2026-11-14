"""Tests for usage_tracker.evaluate_budget (kingdonb/mecris#345)."""

from datetime import date

from usage_tracker import evaluate_budget

TODAY = date(2026, 11, 13)


def test_expired_period_is_stale_not_critical():
    r = evaluate_budget(20.72, 20.72, date(2026, 10, 7), TODAY)
    assert r["period_expired"] is True
    assert r["days_since_period_end"] == 37
    assert r["days_remaining"] == 0
    assert r["budget_health"] == "STALE"
    assert r["alerts"] == ["PERIOD_EXPIRED"]


def test_expired_period_suppresses_spend_alerts():
    r = evaluate_budget(20.0, 1.0, date(2026, 10, 7), TODAY, today_spend=5.0, week_spend=70.0)
    assert r["alerts"] == ["PERIOD_EXPIRED"]


def test_period_ending_today_is_not_expired():
    r = evaluate_budget(20.0, 15.0, TODAY, TODAY)
    assert r["period_expired"] is False
    assert r["days_remaining"] == 0
    assert "PERIOD_ENDING" in r["alerts"]


def test_healthy_period():
    r = evaluate_budget(20.0, 15.0, date(2026, 12, 13), TODAY, week_spend=3.5)
    assert r["budget_health"] == "GOOD"
    assert r["days_remaining"] == 30
    assert r["daily_burn_rate"] == 0.5
    assert r["projected_spend"] == 15.0
    assert r["used_budget"] == 5.0


def test_live_alert_thresholds_unchanged():
    r = evaluate_budget(20.0, 4.0, date(2026, 11, 14), TODAY, today_spend=3.0, week_spend=70.0)
    assert set(r["alerts"]) == {"LOW_BUDGET", "BURN_RATE_HIGH", "PERIOD_ENDING", "DAILY_LIMIT_EXCEEDED"}
    assert r["budget_health"] == "CRITICAL"
