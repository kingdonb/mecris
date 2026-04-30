"""
Unit tests for billing_reconciliation.py

Covers:
  - ReconciliationResult: dataclass creation and field defaults
  - BillingReconciliation.__init__: raises EnvironmentError when NEON_DB_URL absent
  - BillingReconciliation._calculate_drift_percentage: pure logic, 7 cases
  - BillingReconciliation._update_usage_records_with_actual_costs: early-return paths
  - BillingReconciliation.reconcile_anthropic: empty-records, no-actual, exception, success
  - BillingReconciliation.reconcile_groq: empty-records, no-actual, exception, success
  - BillingReconciliation.reconcile_all_providers: returns two results
  - BillingReconciliation.daily_reconciliation: date targeting logic
  - BillingReconciliation._get_groq_actual_costs: mocked fetch_groq_usage
  - BillingReconciliation._get_estimated_costs: psycopg2 mock
  - BillingReconciliation._log_reconciliation_job: psycopg2 mock
  - BillingReconciliation._update_usage_records_with_actual_costs: psycopg2 mock
  - BillingReconciliation.get_reconciliation_summary: psycopg2 RealDictCursor mock

No live DB, no live API calls. All external I/O is mocked.

Refs: yebyen/mecris#307
"""

import sys
import types
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, call
import pytest

from billing_reconciliation import BillingReconciliation, ReconciliationResult


# ---------------------------------------------------------------------------
# Helper: build a BillingReconciliation bypassing __init__
# ---------------------------------------------------------------------------

def _make_reconciler(neon_url="postgresql://fake/db", user_id="test_user"):
    """Build a BillingReconciliation via __new__, bypassing __init__."""
    r = BillingReconciliation.__new__(BillingReconciliation)
    r.budget_manager = MagicMock()
    r.neon_url = neon_url
    r.user_id = user_id
    return r


# ---------------------------------------------------------------------------
# ReconciliationResult dataclass
# ---------------------------------------------------------------------------

class TestReconciliationResult:
    def test_creation_all_fields(self):
        rr = ReconciliationResult(
            provider="anthropic",
            date="2026-04-28",
            estimated_total=1.23,
            actual_total=1.10,
            drift_percentage=11.8,
            records_reconciled=5,
            success=True,
        )
        assert rr.provider == "anthropic"
        assert rr.date == "2026-04-28"
        assert rr.estimated_total == 1.23
        assert rr.actual_total == 1.10
        assert rr.drift_percentage == 11.8
        assert rr.records_reconciled == 5
        assert rr.success is True
        assert rr.error is None  # default

    def test_error_field_is_optional(self):
        rr = ReconciliationResult(
            provider="groq", date="2026-04-28",
            estimated_total=0.0, actual_total=0.0,
            drift_percentage=0.0, records_reconciled=0,
            success=False, error="Something went wrong",
        )
        assert rr.error == "Something went wrong"

    def test_success_false_default_error_none(self):
        rr = ReconciliationResult(
            provider="groq", date="2026-04-28",
            estimated_total=0.0, actual_total=0.0,
            drift_percentage=0.0, records_reconciled=0,
            success=False,
        )
        assert rr.error is None


# ---------------------------------------------------------------------------
# __init__: EnvironmentError when NEON_DB_URL absent
# ---------------------------------------------------------------------------

class TestInit:
    def test_raises_when_no_neon_url(self):
        with patch("billing_reconciliation.os.getenv", return_value=None), \
             patch("billing_reconciliation.VirtualBudgetManager"):
            with pytest.raises(EnvironmentError, match="NEON_DB_URL must be set"):
                BillingReconciliation()

    def test_succeeds_with_neon_url(self):
        with patch("billing_reconciliation.os.getenv", side_effect=lambda k, *a: "postgresql://fake/db" if k == "NEON_DB_URL" else "user1"), \
             patch("billing_reconciliation.VirtualBudgetManager"):
            r = BillingReconciliation()
            assert r.neon_url == "postgresql://fake/db"


# ---------------------------------------------------------------------------
# _calculate_drift_percentage: pure logic
# ---------------------------------------------------------------------------

class TestCalculateDriftPercentage:
    def setup_method(self):
        self.r = _make_reconciler()

    def test_both_zero(self):
        assert self.r._calculate_drift_percentage(0.0, 0.0) == 0.0

    def test_nonzero_estimated_zero_actual(self):
        assert self.r._calculate_drift_percentage(5.0, 0.0) == 100.0

    def test_equal_values(self):
        assert self.r._calculate_drift_percentage(1.0, 1.0) == 0.0

    def test_overestimate(self):
        # estimated > actual → positive drift
        result = self.r._calculate_drift_percentage(1.1, 1.0)
        assert abs(result - 10.0) < 0.001

    def test_underestimate(self):
        # estimated < actual → negative drift
        result = self.r._calculate_drift_percentage(0.9, 1.0)
        assert abs(result - (-10.0)) < 0.001

    def test_large_overestimate(self):
        result = self.r._calculate_drift_percentage(2.0, 1.0)
        assert abs(result - 100.0) < 0.001

    def test_small_values(self):
        result = self.r._calculate_drift_percentage(0.001, 0.001)
        assert result == 0.0


# ---------------------------------------------------------------------------
# _update_usage_records_with_actual_costs: early-return edge cases
# ---------------------------------------------------------------------------

class TestUpdateUsageRecordsEarlyReturns:
    def setup_method(self):
        from virtual_budget_manager import Provider
        self.r = _make_reconciler()
        self.provider = Provider.ANTHROPIC
        self.target_date = date(2026, 4, 28)

    def test_empty_records_returns_zero(self):
        result = self.r._update_usage_records_with_actual_costs(
            self.provider, self.target_date, [], 1.0, "user1"
        )
        assert result == 0

    def test_zero_actual_returns_zero(self):
        records = [{"id": 1, "estimated_cost": 0.5}]
        result = self.r._update_usage_records_with_actual_costs(
            self.provider, self.target_date, records, 0.0, "user1"
        )
        assert result == 0

    def test_negative_actual_returns_zero(self):
        records = [{"id": 1, "estimated_cost": 0.5}]
        result = self.r._update_usage_records_with_actual_costs(
            self.provider, self.target_date, records, -1.0, "user1"
        )
        assert result == 0

    def test_zero_estimated_sum_returns_zero(self):
        records = [{"id": 1, "estimated_cost": 0.0}]
        result = self.r._update_usage_records_with_actual_costs(
            self.provider, self.target_date, records, 1.0, "user1"
        )
        assert result == 0


# ---------------------------------------------------------------------------
# reconcile_anthropic: various paths
# ---------------------------------------------------------------------------

class TestReconcileAnthropic:
    def setup_method(self):
        self.r = _make_reconciler()
        self.target_date = date(2026, 4, 28)

    def test_empty_usage_records_returns_zero_success(self):
        with patch.object(self.r, "_get_estimated_costs", return_value=(0.0, [])):
            result = self.r.reconcile_anthropic(self.target_date)
        assert result.success is True
        assert result.records_reconciled == 0
        assert result.provider == "anthropic"
        assert result.error is None

    def test_actual_costs_unavailable_returns_failure(self):
        records = [{"id": 1, "estimated_cost": 0.5}]
        with patch.object(self.r, "_get_estimated_costs", return_value=(0.5, records)), \
             patch.object(self.r, "_get_anthropic_actual_costs", return_value=None):
            result = self.r.reconcile_anthropic(self.target_date)
        assert result.success is False
        assert "actual Anthropic costs" in result.error

    def test_exception_returns_failure(self):
        with patch.object(self.r, "_get_estimated_costs", side_effect=RuntimeError("DB down")):
            result = self.r.reconcile_anthropic(self.target_date)
        assert result.success is False
        assert "DB down" in result.error

    def test_success_path(self):
        records = [{"id": 1, "estimated_cost": 1.0}]
        with patch.object(self.r, "_get_estimated_costs", return_value=(1.0, records)), \
             patch.object(self.r, "_get_anthropic_actual_costs", return_value=0.9), \
             patch.object(self.r, "_update_usage_records_with_actual_costs", return_value=1), \
             patch.object(self.r, "_log_reconciliation_job"):
            result = self.r.reconcile_anthropic(self.target_date)
        assert result.success is True
        assert result.records_reconciled == 1
        assert result.provider == "anthropic"
        assert abs(result.drift_percentage - 11.11) < 0.1

    def test_user_id_override(self):
        with patch.object(self.r, "_get_estimated_costs", return_value=(0.0, [])) as mock_get:
            self.r.reconcile_anthropic(self.target_date, user_id="override_user")
            mock_get.assert_called_once()
            # first positional arg after provider and date is user_id
            assert mock_get.call_args[0][2] == "override_user"


# ---------------------------------------------------------------------------
# reconcile_groq: various paths
# ---------------------------------------------------------------------------

class TestReconcileGroq:
    def setup_method(self):
        self.r = _make_reconciler()
        self.target_date = date(2026, 4, 28)

    def test_empty_usage_records_returns_zero_success(self):
        with patch.object(self.r, "_get_estimated_costs", return_value=(0.0, [])):
            result = self.r.reconcile_groq(self.target_date)
        assert result.success is True
        assert result.records_reconciled == 0
        assert result.provider == "groq"

    def test_actual_costs_unavailable_returns_failure(self):
        records = [{"id": 1, "estimated_cost": 0.3}]
        with patch.object(self.r, "_get_estimated_costs", return_value=(0.3, records)), \
             patch.object(self.r, "_get_groq_actual_costs", return_value=None):
            result = self.r.reconcile_groq(self.target_date)
        assert result.success is False
        assert "actual Groq costs" in result.error

    def test_exception_returns_failure(self):
        with patch.object(self.r, "_get_estimated_costs", side_effect=ValueError("broken")):
            result = self.r.reconcile_groq(self.target_date)
        assert result.success is False
        assert "broken" in result.error

    def test_success_path(self):
        records = [{"id": 2, "estimated_cost": 0.5}]
        with patch.object(self.r, "_get_estimated_costs", return_value=(0.5, records)), \
             patch.object(self.r, "_get_groq_actual_costs", return_value=0.5), \
             patch.object(self.r, "_update_usage_records_with_actual_costs", return_value=1), \
             patch.object(self.r, "_log_reconciliation_job"):
            result = self.r.reconcile_groq(self.target_date)
        assert result.success is True
        assert result.drift_percentage == 0.0


# ---------------------------------------------------------------------------
# reconcile_all_providers
# ---------------------------------------------------------------------------

class TestReconcileAllProviders:
    def test_returns_two_results(self):
        r = _make_reconciler()
        target_date = date(2026, 4, 28)
        anthro_result = ReconciliationResult("anthropic", "2026-04-28", 0.0, 0.0, 0.0, 0, True)
        groq_result = ReconciliationResult("groq", "2026-04-28", 0.0, 0.0, 0.0, 0, True)
        with patch.object(r, "reconcile_anthropic", return_value=anthro_result), \
             patch.object(r, "reconcile_groq", return_value=groq_result):
            results = r.reconcile_all_providers(target_date)
        assert len(results) == 2
        assert results[0].provider == "anthropic"
        assert results[1].provider == "groq"


# ---------------------------------------------------------------------------
# daily_reconciliation: date targeting
# ---------------------------------------------------------------------------

class TestDailyReconciliation:
    def test_days_back_1_targets_yesterday(self):
        r = _make_reconciler()
        called_dates = []

        def fake_reconcile_all(target_date, user_id=None):
            called_dates.append(target_date)
            return []

        with patch.object(r, "reconcile_all_providers", side_effect=fake_reconcile_all):
            r.daily_reconciliation(days_back=1)

        assert len(called_dates) == 1
        assert called_dates[0] == date.today() - timedelta(days=1)

    def test_days_back_3_targets_three_days(self):
        r = _make_reconciler()
        called_dates = []

        def fake_reconcile_all(target_date, user_id=None):
            called_dates.append(target_date)
            return []

        with patch.object(r, "reconcile_all_providers", side_effect=fake_reconcile_all):
            r.daily_reconciliation(days_back=3)

        assert len(called_dates) == 3
        expected = [date.today() - timedelta(days=i+1) for i in range(3)]
        assert called_dates == expected


# ---------------------------------------------------------------------------
# _get_groq_actual_costs: mocked fetch_groq_usage
# ---------------------------------------------------------------------------

class TestGetGroqActualCosts:
    def setup_method(self):
        self.r = _make_reconciler()
        self.target_date = date(2026, 4, 28)

    def test_returns_none_when_fetch_fails(self):
        with patch("billing_reconciliation.fetch_groq_usage", return_value={"success": False, "error": "timeout"}):
            result = self.r._get_groq_actual_costs(self.target_date)
        assert result is None

    def test_returns_none_when_no_dollar_amounts(self):
        with patch("billing_reconciliation.fetch_groq_usage", return_value={"success": True, "data": {"info": "no cost"}}):
            result = self.r._get_groq_actual_costs(self.target_date)
        assert result is None

    def test_returns_daily_estimate_from_monthly_cost(self):
        data = {"success": True, "data": {"monthly_spend": "$30.00"}}
        with patch("billing_reconciliation.fetch_groq_usage", return_value=data):
            result = self.r._get_groq_actual_costs(self.target_date)
        assert result is not None
        # $30 / days_in_month — April has 30 days
        assert abs(result - 1.0) < 0.01

    def test_returns_none_when_fetch_raises(self):
        with patch("billing_reconciliation.fetch_groq_usage", side_effect=Exception("network error")):
            result = self.r._get_groq_actual_costs(self.target_date)
        assert result is None


# ---------------------------------------------------------------------------
# _get_estimated_costs: psycopg2 mock
# ---------------------------------------------------------------------------

class TestGetEstimatedCostsDB:
    def test_returns_total_and_records(self):
        from virtual_budget_manager import Provider

        r = _make_reconciler()
        target_date = date(2026, 4, 28)

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(1, 0.5), (2, 0.3)]

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch("billing_reconciliation.psycopg2.connect", return_value=mock_conn):
            total, records = r._get_estimated_costs(Provider.ANTHROPIC, target_date, "user1")

        assert abs(total - 0.8) < 0.001
        assert len(records) == 2
        assert records[0] == {"id": 1, "estimated_cost": 0.5}
        assert records[1] == {"id": 2, "estimated_cost": 0.3}

    def test_empty_records_returns_zero(self):
        from virtual_budget_manager import Provider

        r = _make_reconciler()
        target_date = date(2026, 4, 28)

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch("billing_reconciliation.psycopg2.connect", return_value=mock_conn):
            total, records = r._get_estimated_costs(Provider.ANTHROPIC, target_date, "user1")

        assert total == 0.0
        assert records == []


# ---------------------------------------------------------------------------
# _update_usage_records_with_actual_costs: psycopg2 mock (DB path)
# ---------------------------------------------------------------------------

class TestUpdateUsageRecordsDB:
    def test_updates_records_with_scale_factor(self):
        from virtual_budget_manager import Provider

        r = _make_reconciler()
        target_date = date(2026, 4, 28)
        records = [{"id": 1, "estimated_cost": 1.0}, {"id": 2, "estimated_cost": 1.0}]

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch("billing_reconciliation.psycopg2.connect", return_value=mock_conn):
            count = r._update_usage_records_with_actual_costs(
                Provider.ANTHROPIC, target_date, records, 1.5, "user1"
            )

        assert count == 2
        assert mock_cursor.execute.call_count == 2


# ---------------------------------------------------------------------------
# get_reconciliation_summary: psycopg2 RealDictCursor mock
# ---------------------------------------------------------------------------

def _make_mock_cursor(provider_rows, recent_rows):
    """Build a context-manager cursor with two sequential fetchall() returns."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchall.side_effect = [provider_rows, recent_rows]
    return mock_cursor


def _make_mock_conn(mock_cursor):
    """Build a context-manager connection whose cursor() returns mock_cursor."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestGetReconciliationSummary:
    def test_returns_provider_summary_with_data(self):
        r = _make_reconciler()
        provider_rows = [
            {"provider": "anthropic", "jobs_count": 3, "avg_abs_drift": 5.5,
             "avg_drift": 2.0, "total_estimated": 1.2345, "total_actual": 1.1234},
        ]
        recent_rows = [
            {"provider": "anthropic", "job_date": "2026-04-28",
             "drift_percentage": 5.5, "records_reconciled": 10,
             "reconciled_at": "2026-04-28T12:00:00"},
        ]
        mock_cursor = _make_mock_cursor(provider_rows, recent_rows)
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("billing_reconciliation.psycopg2.connect", return_value=mock_conn):
            result = r.get_reconciliation_summary(days=7)

        assert result["period_days"] == 7
        assert "anthropic" in result["provider_summary"]
        ps = result["provider_summary"]["anthropic"]
        assert ps["jobs_count"] == 3
        assert ps["avg_abs_drift_pct"] == 5.5
        assert ps["avg_drift_pct"] == 2.0
        assert ps["total_estimated"] == 1.2345
        assert ps["total_actual"] == 1.1234
        assert len(result["recent_jobs"]) == 1
        assert result["recent_jobs"][0]["job_date"] == "2026-04-28"
        assert result["overall_accuracy"]["avg_abs_drift"] == 5.5

    def test_empty_results_returns_zero_accuracy(self):
        r = _make_reconciler()
        mock_cursor = _make_mock_cursor([], [])
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("billing_reconciliation.psycopg2.connect", return_value=mock_conn):
            result = r.get_reconciliation_summary(days=3)

        assert result["period_days"] == 3
        assert result["provider_summary"] == {}
        assert result["recent_jobs"] == []
        assert result["overall_accuracy"]["avg_abs_drift"] == 0

    def test_overall_accuracy_averages_multiple_providers(self):
        r = _make_reconciler()
        provider_rows = [
            {"provider": "anthropic", "jobs_count": 2, "avg_abs_drift": 4.0,
             "avg_drift": 1.0, "total_estimated": 1.0, "total_actual": 1.0},
            {"provider": "groq", "jobs_count": 1, "avg_abs_drift": 6.0,
             "avg_drift": -1.0, "total_estimated": 0.5, "total_actual": 0.5},
        ]
        mock_cursor = _make_mock_cursor(provider_rows, [])
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("billing_reconciliation.psycopg2.connect", return_value=mock_conn):
            result = r.get_reconciliation_summary(days=7)

        assert set(result["provider_summary"]) == {"anthropic", "groq"}
        assert result["overall_accuracy"]["avg_abs_drift"] == 5.0  # (4.0 + 6.0) / 2

    def test_raises_when_no_neon_url(self):
        r = _make_reconciler(neon_url=None)
        with pytest.raises(RuntimeError, match="Neon connection not active"):
            r.get_reconciliation_summary()

    def test_reraises_on_db_exception(self):
        r = _make_reconciler()
        with patch("billing_reconciliation.psycopg2.connect", side_effect=Exception("conn refused")):
            with pytest.raises(Exception, match="conn refused"):
                r.get_reconciliation_summary()

    def test_uses_override_user_id(self):
        r = _make_reconciler(user_id="default_user")
        provider_rows = []
        recent_rows = []
        mock_cursor = _make_mock_cursor(provider_rows, recent_rows)
        mock_conn = _make_mock_conn(mock_cursor)

        with patch("billing_reconciliation.psycopg2.connect", return_value=mock_conn):
            r.get_reconciliation_summary(days=7, user_id="override_user")

        # Both execute calls should use the override user_id
        calls = mock_cursor.execute.call_args_list
        assert len(calls) == 2
        assert calls[0][0][1][1] == "override_user"
        assert calls[1][0][1][1] == "override_user"
