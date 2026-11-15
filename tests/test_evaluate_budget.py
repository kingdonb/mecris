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


# ---------------------------------------------------------------------------
# Claude Ultra subscription (kingdonb/mecris#345)
# ---------------------------------------------------------------------------

GRANT_END = date(2027, 5, 13)


def _sub(today, end=GRANT_END, **kw):
    return evaluate_budget(20.72, 20.72, end, today, source_type="subscription", plan="ultra", **kw)


def test_subscription_is_good_while_the_grant_runs():
    r = _sub(TODAY)
    assert r["budget_health"] == "GOOD"
    assert r["alerts"] == []
    assert r["period_expired"] is False
    assert r["source_type"] == "subscription"
    assert r["plan"] == "ultra"
    assert r["grant_end"] == "2027-05-13"
    assert r["days_to_grant_end"] == (GRANT_END - TODAY).days
    assert r["days_remaining"] == r["days_to_grant_end"]


def test_subscription_ignores_spend_pressure():
    r = _sub(TODAY, today_spend=50.0, week_spend=500.0)
    assert r["budget_health"] == "GOOD"
    assert r["alerts"] == []


def test_subscription_is_ending_within_14_days():
    r = _sub(date(2027, 4, 29))
    assert r["days_to_grant_end"] == 14
    assert r["budget_health"] == "ENDING"
    assert r["alerts"] == ["GRANT_ENDING"]


def test_subscription_15_days_out_is_still_good():
    assert _sub(date(2027, 4, 28))["budget_health"] == "GOOD"


def test_subscription_last_day_is_ending_not_ended():
    r = _sub(GRANT_END)
    assert r["budget_health"] == "ENDING"
    assert r["days_to_grant_end"] == 0


def test_subscription_after_grant_end_is_ended_never_negative():
    r = _sub(date(2027, 5, 20))
    assert r["budget_health"] == "ENDED"
    assert r["alerts"] == ["GRANT_ENDED"]
    assert r["days_to_grant_end"] == 0
    assert r["days_remaining"] == 0
    assert r["days_since_grant_end"] == 7
    assert r["period_expired"] is False


def test_subscription_keeps_numeric_dollar_fields():
    r = _sub(TODAY)
    assert isinstance(r["remaining_budget"], float)
    assert isinstance(r["total_budget"], float)


def test_retired_budget_reports_retired_without_alerts():
    r = evaluate_budget(20.72, 20.72, date(2026, 10, 7), TODAY, source_type="retired")
    assert r["budget_health"] == "RETIRED"
    assert r["alerts"] == []
    assert r["period_expired"] is False
    assert r["days_remaining"] == 0
    assert isinstance(r["remaining_budget"], float)


def test_api_credit_is_the_default_source():
    r = evaluate_budget(20.0, 15.0, date(2026, 12, 13), TODAY)
    assert r["source_type"] == "api_credit"
