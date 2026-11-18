"""#393: the budget follows the Helix monthly grant and rolls over by itself.

The period is the wallet's own (subscription_current_period_start..end), so it
never goes stale. "Used" is what the balance dropped since the period started,
inflows excluded. An optional balance target (e.g. $500 by 2026-12-31, later
$0 by a set date) gives the daily pace needed to get there.
"""
from datetime import datetime, timezone

import pytest

import usage_tracker
from scripts.helix_balance_scraper import sum_burn

UTC = timezone.utc
START = datetime(2026, 11, 17, 22, 21, 23, tzinfo=UTC)
END = datetime(2026, 12, 17, 22, 21, 23, tzinfo=UTC)
NOW = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)


def evaluate(**kw):
    args = dict(grant=100.0, period_start=START, period_end=END, burned=12.5, balance=619.43, now=NOW)
    args.update(kw)
    return usage_tracker.evaluate_helix_grant(**args)


class TestSumBurn:
    def test_drops_add_up(self):
        assert sum_burn([631.93, 630.0, 627.5]) == pytest.approx(4.43)

    def test_inflows_are_not_burn(self):
        assert sum_burn([531.93, 631.93, 630.93]) == pytest.approx(1.0)

    def test_too_few_readings_burn_nothing(self):
        assert sum_burn([]) == 0
        assert sum_burn([500.0]) == 0


class TestEvaluateHelixGrant:
    def test_the_period_is_the_wallets(self):
        out = evaluate()
        assert out["source_type"] == "helix_grant"
        assert out["period_start"] == "2026-11-17"
        assert out["period_end"] == "2026-12-17"
        assert out["period_expired"] is False

    def test_used_and_remaining_come_from_the_burn(self):
        out = evaluate(burned=12.5)
        assert out["total_budget"] == 100.0
        assert out["used_budget"] == 12.5
        assert out["remaining_budget"] == 87.5

    def test_spending_more_than_the_grant_is_fine(self):
        out = evaluate(burned=130.0)
        assert out["remaining_budget"] == 0
        assert out["used_budget"] == 130.0
        assert out["budget_health"] == "GOOD"
        assert out["alerts"] == []

    def test_days_remaining_counts_to_the_next_grant(self):
        assert evaluate()["days_remaining"] == 28  # 11-20 15:00 to 12-17 22:21 UTC, rounded up

    def test_no_spend_pressure_alerts(self):
        out = evaluate(burned=0.0)
        assert out["alerts"] == [] and out["budget_health"] == "GOOD"

    def test_balance_is_reported(self):
        assert evaluate()["helix_balance"] == 619.43

    def test_no_target_means_no_pace(self):
        out = evaluate()
        assert out["target"] is None and out["target_pace_per_day"] is None

    def test_target_pace_counts_the_grants_still_to_land(self):
        # $619.43 now; grants on 12-17 land before 12-31; reach $500 by 12-31.
        out = evaluate(target_balance=500.0, target_date=datetime(2026, 12, 31, tzinfo=UTC).date())
        assert out["target"] == {"balance": 500.0, "date": "2026-12-31", "grants_before": 1}
        # (619.43 + 100 - 500) / 41 days (11-20 to 12-31)
        assert out["target_pace_per_day"] == pytest.approx(5.35, abs=0.005)

    def test_zero_target_six_months_out(self):
        out = evaluate(target_balance=0.0, target_date=datetime(2027, 6, 16, tzinfo=UTC).date())
        # grants on 12-17, 1-17 ... 5-17: 6 of them before 6-16
        assert out["target"]["grants_before"] == 6
        assert out["target_pace_per_day"] == pytest.approx((619.43 + 600) / 208, abs=0.01)

    def test_a_target_already_met_needs_no_pace(self):
        out = evaluate(balance=450.0, target_balance=500.0, target_date=datetime(2026, 11, 30, tzinfo=UTC).date())
        assert out["target_pace_per_day"] == 0

    def test_a_past_target_date_is_ignored(self):
        out = evaluate(target_balance=500.0, target_date=datetime(2026, 11, 1, tzinfo=UTC).date())
        assert out["target"] is None and out["target_pace_per_day"] is None

    def test_unknown_balance_or_burn_says_so(self):
        out = evaluate(balance=None, burned=None)
        assert out["helix_balance"] is None
        assert out["used_budget"] is None and out["remaining_budget"] is None
        assert out["budget_health"] == "UNKNOWN"


def test_helix_grant_is_a_source_type():
    assert "helix_grant" in usage_tracker.SOURCE_TYPES


# --- migration v11 ---------------------------------------------------------------

def test_migration_v11_widens_the_check_and_touches_no_rows():
    from unittest.mock import MagicMock
    from scripts import migrate_v11_helix_grant_budget as m
    conn = MagicMock()
    cur = conn.cursor.return_value
    m.migrate(conn)
    sql = " ".join(c.args[0] for c in cur.execute.call_args_list)
    assert "DROP CONSTRAINT IF EXISTS budget_tracking_source_type_check" in sql
    for v in ("api_credit", "subscription", "retired", "helix_grant"):
        assert f"'{v}'" in sql
    for forbidden in ("UPDATE ", "DELETE ", "TRUNCATE ", "DROP TABLE", "DROP COLUMN"):
        assert forbidden not in sql.upper()
    conn.commit.assert_called_once()


def test_migration_v11_rolls_back_on_failure():
    from unittest.mock import MagicMock
    from scripts import migrate_v11_helix_grant_budget as m
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = [None, RuntimeError("boom")]
    with pytest.raises(RuntimeError):
        m.migrate(conn)
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


# --- get_budget_status dispatch --------------------------------------------------

def _tracker(row):
    from unittest.mock import MagicMock
    tracker = usage_tracker.UsageTracker.__new__(usage_tracker.UsageTracker)
    tracker.neon_url = "postgres://fake"
    tracker.user_id = "test-user"
    tracker._use_neon = True
    tracker._db_initialized = True
    tracker.resolve_user_id = lambda user_id=None: user_id or "test-user"
    cur = MagicMock()
    cur.fetchone.side_effect = [row, {"sum": 0}, {"sum": 0}]
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur
    return tracker, conn


HELIX_ROW = {"total_budget": 100.0, "remaining_budget": 20.72, "budget_period_start": "2025-11-22",
             "budget_period_end": "2026-10-07", "source_type": "helix_grant", "plan": None,
             "monthly_price_usd": None}


def test_get_budget_status_reads_the_wallet_period_for_a_helix_grant(monkeypatch):
    from unittest.mock import patch
    from scripts import helix_billing, helix_balance_scraper
    monkeypatch.setattr(helix_billing, "get_wallet", lambda force=False: {
        "balance": 619.43, "period_start": START.timestamp(), "period_end": END.timestamp()})
    seen = {}
    def burned(user_id, start):
        seen["args"] = (user_id, start)
        return 12.5
    monkeypatch.setattr(helix_balance_scraper, "burned_since", burned)
    monkeypatch.setenv("HELIX_TARGET_BALANCE", "500")
    monkeypatch.setenv("HELIX_TARGET_DATE", "2099-12-31")
    tracker, conn = _tracker(dict(HELIX_ROW))
    with patch("psycopg2.connect", return_value=conn):
        status = tracker.get_budget_status("test-user")
    assert status["source_type"] == "helix_grant"
    assert status["period_start"] == "2026-11-17" and status["period_end"] == "2026-12-17"
    assert status["used_budget"] == 12.5 and status["remaining_budget"] == 87.5
    assert status["period_expired"] is False  # the stored 2026-10-07 end is not used
    assert seen["args"] == ("test-user", START)
    assert status["target"]["balance"] == 500.0


def test_helix_grant_without_a_wallet_is_unknown_not_stale(monkeypatch):
    from unittest.mock import patch
    from scripts import helix_billing
    monkeypatch.setattr(helix_billing, "get_wallet", lambda force=False: None)
    tracker, conn = _tracker(dict(HELIX_ROW))
    with patch("psycopg2.connect", return_value=conn):
        status = tracker.get_budget_status("test-user")
    assert status["source_type"] == "helix_grant"
    assert status["budget_health"] == "UNKNOWN"
    assert status["period_expired"] is False
    assert status["alerts"] == []


# --- narrator text ----------------------------------------------------------------

def _status(**kw):
    s = evaluate(**kw)
    return s


def test_phrase_without_a_target():
    import importlib, sys
    from unittest.mock import patch
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"}), patch("psycopg2.connect"):
        import mcp_server
        phrase, rec = mcp_server._helix_budget_text(_status())
    sys.modules.pop("mcp_server", None)
    assert phrase == "Budget: Helix $12.50 of $100 used this period, 28 days to the next grant (balance $619.43)"
    assert rec is None


def test_phrase_with_a_target_recommends_the_pace_and_flags_the_cap(monkeypatch):
    import sys
    from unittest.mock import patch
    monkeypatch.setenv("HELIX_BURN_CAP", "5")
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"}), patch("psycopg2.connect"):
        import mcp_server
        _, rec = mcp_server._helix_budget_text(
            _status(target_balance=500.0, target_date=datetime(2026, 12, 31, tzinfo=UTC).date()))
    sys.modules.pop("mcp_server", None)
    assert rec == ("💸 Helix: about $5.35/day reaches $500 by 2026-12-31 "
                   "(above the $5.00/day burn cap; raise HELIX_BURN_CAP to allow it)")


def test_unknown_helix_budget_phrase():
    import sys
    from unittest.mock import patch
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"}), patch("psycopg2.connect"):
        import mcp_server
        phrase, rec = mcp_server._helix_budget_text(_status(balance=None, burned=None))
    sys.modules.pop("mcp_server", None)
    assert phrase == "Budget: Helix grant (wallet unavailable)"
    assert rec is None
