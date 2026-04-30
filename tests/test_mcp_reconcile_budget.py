"""
Unit tests for mcp_reconcile_budget.py

Functions under test:
  - get_current_budget_status(): GET /usage → dict or sys.exit(1)
  - record_reconciliation(current_budget, manual_adjustment, reason): POST /budget/reconcile → dict or sys.exit(1)
  - update_budget_directly(remaining, total, period_end): POST /usage/update_budget → dict or sys.exit(1)
  - get_reconciliation_status(): GET /budget/reconciliation/status → dict or None
  - main(): CLI entry point

Strategy: mock `requests.get` / `requests.post` at the mcp_reconcile_budget module level.
"""
import sys
import json
import pytest
from unittest.mock import MagicMock, patch, call
import mcp_reconcile_budget as mrb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(json_data, status_code=200, raise_for_status=None):
    """Return a MagicMock that looks like a requests.Response."""
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data
    if raise_for_status:
        r.raise_for_status.side_effect = raise_for_status
    else:
        r.raise_for_status.return_value = None
    return r


_BUDGET_STATUS = {
    "remaining_budget": 15.00,
    "total_budget": 25.00,
    "used_budget": 10.00,
    "days_remaining": 20,
    "budget_health": "OK",
}

_RECON_RESULT = {"success": True, "message": "recorded"}
_RECON_STATUS = {
    "success": True,
    "budget_tracking_health": "GOOD",
    "period_summary": {
        "reconciliation_count": 3,
        "total_adjustments": 1.50,
    },
}


# ---------------------------------------------------------------------------
# get_current_budget_status
# ---------------------------------------------------------------------------

class TestGetCurrentBudgetStatus:
    def test_happy_path_returns_dict(self):
        with patch("mcp_reconcile_budget.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_BUDGET_STATUS)
            result = mrb.get_current_budget_status()
        assert result["remaining_budget"] == 15.00
        assert result["budget_health"] == "OK"
        mock_get.assert_called_once_with("http://localhost:8000/usage")

    def test_http_error_calls_sys_exit(self):
        with patch("mcp_reconcile_budget.requests.get") as mock_get:
            mock_get.return_value = _mock_response({}, raise_for_status=Exception("500"))
            with pytest.raises(SystemExit) as exc_info:
                mrb.get_current_budget_status()
        assert exc_info.value.code == 1

    def test_connection_error_calls_sys_exit(self):
        with patch("mcp_reconcile_budget.requests.get", side_effect=ConnectionError("refused")):
            with pytest.raises(SystemExit) as exc_info:
                mrb.get_current_budget_status()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# record_reconciliation
# ---------------------------------------------------------------------------

class TestRecordReconciliation:
    def test_happy_path_posts_correct_data(self):
        with patch("mcp_reconcile_budget.requests.post") as mock_post:
            mock_post.return_value = _mock_response(_RECON_RESULT)
            result = mrb.record_reconciliation(19.54, 4.54, "manual-sync")
        assert result["success"] is True
        called_kwargs = mock_post.call_args
        assert called_kwargs[0][0] == "http://localhost:8000/budget/reconcile"
        payload = called_kwargs[1]["json"]
        assert payload["current_budget"] == 19.54
        assert payload["manual_adjustment"] == 4.54
        assert payload["adjustment_reason"] == "manual-sync"

    def test_http_error_calls_sys_exit(self):
        with patch("mcp_reconcile_budget.requests.post") as mock_post:
            mock_post.return_value = _mock_response({}, raise_for_status=Exception("400"))
            with pytest.raises(SystemExit) as exc_info:
                mrb.record_reconciliation(10.0, 1.0, "test")
        assert exc_info.value.code == 1

    def test_network_error_calls_sys_exit(self):
        with patch("mcp_reconcile_budget.requests.post", side_effect=OSError("timeout")):
            with pytest.raises(SystemExit) as exc_info:
                mrb.record_reconciliation(10.0, 1.0, "test")
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# update_budget_directly
# ---------------------------------------------------------------------------

class TestUpdateBudgetDirectly:
    def test_without_total_omits_total_budget_param(self):
        with patch("mcp_reconcile_budget.requests.post") as mock_post:
            mock_post.return_value = _mock_response({"ok": True})
            mrb.update_budget_directly(19.54)
        params = mock_post.call_args[1]["params"]
        assert "total_budget" not in params
        assert params["remaining_budget"] == 19.54

    def test_with_total_includes_total_budget_param(self):
        with patch("mcp_reconcile_budget.requests.post") as mock_post:
            mock_post.return_value = _mock_response({"ok": True})
            mrb.update_budget_directly(19.54, total=24.96)
        params = mock_post.call_args[1]["params"]
        assert params["total_budget"] == 24.96
        assert params["remaining_budget"] == 19.54

    def test_uses_custom_period_end(self):
        with patch("mcp_reconcile_budget.requests.post") as mock_post:
            mock_post.return_value = _mock_response({"ok": True})
            mrb.update_budget_directly(5.0, period_end="2026-03-31")
        params = mock_post.call_args[1]["params"]
        assert params["period_end"] == "2026-03-31"

    def test_http_error_calls_sys_exit(self):
        with patch("mcp_reconcile_budget.requests.post") as mock_post:
            mock_post.return_value = _mock_response({}, raise_for_status=Exception("503"))
            with pytest.raises(SystemExit) as exc_info:
                mrb.update_budget_directly(10.0)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# get_reconciliation_status
# ---------------------------------------------------------------------------

class TestGetReconciliationStatus:
    def test_happy_path_returns_dict(self):
        with patch("mcp_reconcile_budget.requests.get") as mock_get:
            mock_get.return_value = _mock_response(_RECON_STATUS)
            result = mrb.get_reconciliation_status()
        assert result["success"] is True
        assert result["budget_tracking_health"] == "GOOD"

    def test_error_returns_none_not_sys_exit(self):
        with patch("mcp_reconcile_budget.requests.get", side_effect=Exception("network")):
            result = mrb.get_reconciliation_status()
        assert result is None


# ---------------------------------------------------------------------------
# main() integration paths
# ---------------------------------------------------------------------------

class TestMain:
    """Test main() via argv patching. All HTTP calls are mocked."""

    def _run_main(self, argv, status_side_effect=None):
        """Run main() with given argv list, patching budget status and reconciliation."""
        with patch.object(sys, "argv", argv), \
             patch("mcp_reconcile_budget.get_current_budget_status",
                   side_effect=status_side_effect or [_BUDGET_STATUS, _BUDGET_STATUS]), \
             patch("mcp_reconcile_budget.record_reconciliation",
                   return_value=_RECON_RESULT) as mock_recon, \
             patch("mcp_reconcile_budget.get_reconciliation_status",
                   return_value=_RECON_STATUS):
            return mock_recon

    def test_already_in_sync_exits_zero(self):
        """When remaining == tracked_remaining, exit 0 without posting."""
        argv = ["prog", "15.00"]  # matches _BUDGET_STATUS remaining_budget=15.00
        with patch.object(sys, "argv", argv), \
             patch("mcp_reconcile_budget.get_current_budget_status",
                   return_value=_BUDGET_STATUS), \
             patch("mcp_reconcile_budget.record_reconciliation") as mock_recon:
            with pytest.raises(SystemExit) as exc_info:
                mrb.main()
        assert exc_info.value.code == 0
        mock_recon.assert_not_called()

    def test_dry_run_exits_zero_without_posting(self):
        """--dry-run exits 0 and never calls record_reconciliation."""
        argv = ["prog", "20.00", "--dry-run"]
        with patch.object(sys, "argv", argv), \
             patch("mcp_reconcile_budget.get_current_budget_status",
                   return_value=_BUDGET_STATUS), \
             patch("mcp_reconcile_budget.record_reconciliation") as mock_recon:
            with pytest.raises(SystemExit) as exc_info:
                mrb.main()
        assert exc_info.value.code == 0
        mock_recon.assert_not_called()

    def test_small_positive_adjustment_records_reconciliation(self):
        """A small positive delta calls record_reconciliation with correct args."""
        argv = ["prog", "16.00"]  # tracked=15.00 → delta=+1.00
        with patch.object(sys, "argv", argv), \
             patch("mcp_reconcile_budget.get_current_budget_status",
                   side_effect=[_BUDGET_STATUS, _BUDGET_STATUS]), \
             patch("mcp_reconcile_budget.record_reconciliation",
                   return_value=_RECON_RESULT) as mock_recon, \
             patch("mcp_reconcile_budget.get_reconciliation_status",
                   return_value=_RECON_STATUS):
            mrb.main()
        mock_recon.assert_called_once()
        call_args = mock_recon.call_args[1]
        assert call_args["current_budget"] == pytest.approx(16.00)
        assert call_args["manual_adjustment"] == pytest.approx(1.00)

    def test_small_negative_adjustment_records_reconciliation(self):
        """A small negative delta calls record_reconciliation."""
        argv = ["prog", "14.00"]  # tracked=15.00 → delta=-1.00
        with patch.object(sys, "argv", argv), \
             patch("mcp_reconcile_budget.get_current_budget_status",
                   side_effect=[_BUDGET_STATUS, _BUDGET_STATUS]), \
             patch("mcp_reconcile_budget.record_reconciliation",
                   return_value=_RECON_RESULT) as mock_recon, \
             patch("mcp_reconcile_budget.get_reconciliation_status",
                   return_value=_RECON_STATUS):
            mrb.main()
        mock_recon.assert_called_once()
        call_args = mock_recon.call_args[1]
        assert call_args["manual_adjustment"] == pytest.approx(-1.00)

    def test_custom_reason_passed_through(self):
        """--reason flag is forwarded to record_reconciliation."""
        argv = ["prog", "16.00", "--reason", "manual-fix"]
        with patch.object(sys, "argv", argv), \
             patch("mcp_reconcile_budget.get_current_budget_status",
                   side_effect=[_BUDGET_STATUS, _BUDGET_STATUS]), \
             patch("mcp_reconcile_budget.record_reconciliation",
                   return_value=_RECON_RESULT) as mock_recon, \
             patch("mcp_reconcile_budget.get_reconciliation_status",
                   return_value=_RECON_STATUS):
            mrb.main()
        call_args = mock_recon.call_args[1]
        assert call_args["reason"] == "manual-fix"

    def test_reconciliation_failure_exits_nonzero(self):
        """If record_reconciliation returns success=False, main exits 1."""
        argv = ["prog", "16.00"]
        fail_result = {"success": False, "message": "db error"}
        with patch.object(sys, "argv", argv), \
             patch("mcp_reconcile_budget.get_current_budget_status",
                   return_value=_BUDGET_STATUS), \
             patch("mcp_reconcile_budget.record_reconciliation",
                   return_value=fail_result):
            with pytest.raises(SystemExit) as exc_info:
                mrb.main()
        assert exc_info.value.code == 1
