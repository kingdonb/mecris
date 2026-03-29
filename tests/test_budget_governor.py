"""Tests for BudgetGovernor — TDG red phase. Plan: yebyen/mecris#26"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from services.budget_governor import BudgetGovernor, BucketType


# ---------------------------------------------------------------------------
# check_envelope
# ---------------------------------------------------------------------------

def test_check_envelope_allows_when_no_recent_spend():
    """Fresh governor with no spend events: small estimate is always allowed."""
    gov = BudgetGovernor()
    result = gov.check_envelope("anthropic_api", 0.10)
    assert result == "allow"


def test_check_envelope_defers_when_window_full():
    """If 5% of the period quota was already spent in the last 39 minutes, defer."""
    gov = BudgetGovernor()
    bucket_limit = gov.buckets["anthropic_api"]["limit"]
    window_cap = 0.05 * bucket_limit  # 5% of period quota

    # Fill the window to the cap by injecting a spend event 10 minutes ago
    ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
    gov._spend_log.append({
        "bucket": "anthropic_api",
        "cost": window_cap,
        "ts": ten_min_ago,
    })

    result = gov.check_envelope("anthropic_api", 0.01)
    assert result == "defer"


def test_check_envelope_denies_when_total_budget_exhausted():
    """If total spend equals or exceeds the bucket limit, deny immediately."""
    gov = BudgetGovernor()
    bucket_limit = gov.buckets["anthropic_api"]["limit"]

    # Force total spend to equal the limit by injecting an old event (outside window)
    old_ts = datetime.utcnow() - timedelta(hours=2)
    gov._spend_log.append({
        "bucket": "anthropic_api",
        "cost": bucket_limit,
        "ts": old_ts,
    })

    result = gov.check_envelope("anthropic_api", 0.01)
    assert result == "deny"


def test_check_envelope_allows_spend_bucket_helix():
    """SPEND buckets (Helix) should be allowed when within the envelope."""
    gov = BudgetGovernor()
    result = gov.check_envelope("helix", 1.00)
    assert result == "allow"


def test_check_envelope_unknown_bucket_raises():
    """Unknown bucket name should raise ValueError."""
    gov = BudgetGovernor()
    with pytest.raises(ValueError):
        gov.check_envelope("nonexistent_bucket", 0.01)


# ---------------------------------------------------------------------------
# recommend_bucket
# ---------------------------------------------------------------------------

def test_recommend_bucket_prefers_spend_when_available():
    """Governor should recommend a SPEND bucket (Helix/Gemini) over a GUARD bucket."""
    gov = BudgetGovernor()
    recommendation = gov.recommend_bucket()
    recommended_type = gov.buckets[recommendation]["type"]
    assert recommended_type == BucketType.SPEND


def test_recommend_bucket_falls_back_to_guard_when_spend_exhausted():
    """When all SPEND buckets are exhausted, fall back to a GUARD bucket."""
    gov = BudgetGovernor()
    # Exhaust all SPEND buckets
    for name, cfg in gov.buckets.items():
        if cfg["type"] == BucketType.SPEND:
            old_ts = datetime.utcnow() - timedelta(hours=2)
            gov._spend_log.append({
                "bucket": name,
                "cost": cfg["limit"],
                "ts": old_ts,
            })

    recommendation = gov.recommend_bucket()
    recommended_type = gov.buckets[recommendation]["type"]
    assert recommended_type == BucketType.GUARD


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

def test_get_status_returns_expected_keys():
    """get_status() must return the keys required by the MCP tool."""
    gov = BudgetGovernor()
    status = gov.get_status()
    assert "buckets" in status
    assert "recommendation" in status
    assert "envelope_status" in status


def test_get_status_bucket_structure():
    """Each bucket entry in get_status() has type, limit, spent, and envelope."""
    gov = BudgetGovernor()
    status = gov.get_status()
    for name, data in status["buckets"].items():
        assert "type" in data
        assert "limit" in data
        assert "spent_total" in data
        assert "envelope" in data


# ---------------------------------------------------------------------------
# Helix balance discovery (mocked)
# ---------------------------------------------------------------------------

def test_get_helix_balance_returns_float_on_success():
    """When the Helix API responds with a balance, return a float."""
    gov = BudgetGovernor()
    with patch("os.getenv") as mock_env:
        # Mock env vars needed for Helix discovery
        mock_env.side_effect = lambda k, d=None: {
            "ANTHROPIC_BASE_URL": "https://helix.example.com",
            "ANTHROPIC_API_KEY": "sk-helix-123"
        }.get(k, d)

        with patch("services.budget_governor.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"balance": 97.83}
            mock_get.return_value = mock_resp

            balance = gov.get_helix_balance()
            assert isinstance(balance, float)
            assert balance == pytest.approx(97.83)


def test_get_helix_balance_returns_none_on_failure():
    """When the Helix API is unreachable or returns unexpected data, return None."""
    gov = BudgetGovernor()
    with patch("services.budget_governor.requests.get") as mock_get:
        mock_get.side_effect = Exception("Connection refused")
        balance = gov.get_helix_balance()
        assert balance is None


# ---------------------------------------------------------------------------
# get_narrator_summary — slim dict for narrator context embedding
# ---------------------------------------------------------------------------

def test_get_narrator_summary_returns_required_keys():
    """get_narrator_summary() must return routing_recommendation and envelope_status."""
    gov = BudgetGovernor()
    summary = gov.get_narrator_summary()
    assert "routing_recommendation" in summary
    assert "envelope_status" in summary


def test_get_narrator_summary_routing_recommendation_is_valid_bucket():
    """routing_recommendation must be one of the configured bucket names."""
    gov = BudgetGovernor()
    summary = gov.get_narrator_summary()
    assert summary["routing_recommendation"] in gov.buckets


def test_get_narrator_summary_envelope_status_is_ok_when_fresh():
    """envelope_status should be 'OK' when no spend has occurred."""
    gov = BudgetGovernor()
    summary = gov.get_narrator_summary()
    assert summary["envelope_status"] == "OK"


def test_get_narrator_summary_envelope_status_halted_when_all_denied():
    """envelope_status should be 'HALTED' when all buckets are exhausted."""
    gov = BudgetGovernor()
    from datetime import datetime, timedelta
    old_ts = datetime.utcnow() - timedelta(hours=2)
    for name, cfg in gov.buckets.items():
        gov._spend_log.append({"bucket": name, "cost": cfg["limit"], "ts": old_ts})
    summary = gov.get_narrator_summary()
    assert summary["envelope_status"] == "HALTED"


# ---------------------------------------------------------------------------
# _spend_log persistence — JSON file durability (plan: yebyen/mecris#29)
# ---------------------------------------------------------------------------

def test_spend_log_persists_across_restarts(tmp_path):
    """Spend events recorded via record_spend() must survive process restart."""
    log_path = str(tmp_path / "spend_log.json")

    # First instance: record a spend event
    gov1 = BudgetGovernor(spend_log_path=log_path)
    gov1.record_spend("anthropic_api", 0.42)

    # Second instance from the same path: should see the prior event
    gov2 = BudgetGovernor(spend_log_path=log_path)
    assert gov2._total_spent("anthropic_api") == pytest.approx(0.42)


def test_spend_log_accumulates_across_restarts(tmp_path):
    """Multiple spend events across restarts all accumulate correctly."""
    log_path = str(tmp_path / "spend_log.json")

    gov1 = BudgetGovernor(spend_log_path=log_path)
    gov1.record_spend("groq", 0.10)
    gov1.record_spend("groq", 0.20)

    gov2 = BudgetGovernor(spend_log_path=log_path)
    gov2.record_spend("groq", 0.05)

    gov3 = BudgetGovernor(spend_log_path=log_path)
    assert gov3._total_spent("groq") == pytest.approx(0.35)


def test_spend_log_no_path_works_as_before():
    """BudgetGovernor() with no path argument behaves exactly as before — in-memory."""
    gov = BudgetGovernor()
    gov.record_spend("helix", 1.00)
    assert gov._total_spent("helix") == pytest.approx(1.00)
    # No file created; no error raised.


def test_spend_log_corrupt_file_recovers_gracefully(tmp_path):
    """If the spend log JSON file is corrupt, start fresh rather than crash."""
    log_path = str(tmp_path / "spend_log.json")
    with open(log_path, "w") as f:
        f.write("this is not valid json {{{{")

    gov = BudgetGovernor(spend_log_path=log_path)  # should not raise
    assert gov._total_spent("anthropic_api") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# budget_gate — enforcement guard for MCP handlers (plan: yebyen/mecris#31)
# ---------------------------------------------------------------------------

def test_budget_gate_returns_none_when_allowed():
    """budget_gate() returns None when the bucket is within limits."""
    gov = BudgetGovernor()
    result = gov.budget_gate("anthropic_api")
    assert result is None


def test_budget_gate_returns_warning_dict_when_deferred():
    """budget_gate() returns a warning dict (non-blocking) when the window is full."""
    gov = BudgetGovernor()
    bucket_limit = gov.buckets["anthropic_api"]["limit"]
    window_cap = 0.05 * bucket_limit

    ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
    gov._spend_log.append({
        "bucket": "anthropic_api",
        "cost": window_cap,
        "ts": ten_min_ago,
    })

    result = gov.budget_gate("anthropic_api")
    assert result is not None
    assert "warning" in result
    assert result.get("budget_halted") is not True
    assert result["bucket"] == "anthropic_api"
    assert result["envelope"] == "defer"


def test_budget_gate_returns_error_dict_when_denied():
    """budget_gate() returns a structured error dict when the bucket is exhausted."""
    gov = BudgetGovernor()
    bucket_limit = gov.buckets["anthropic_api"]["limit"]
    old_ts = datetime.utcnow() - timedelta(hours=2)
    gov._spend_log.append({
        "bucket": "anthropic_api",
        "cost": bucket_limit,
        "ts": old_ts,
    })

    result = gov.budget_gate("anthropic_api")
    assert result is not None
    assert result["budget_halted"] is True
    assert result["bucket"] == "anthropic_api"
    assert result["envelope"] == "deny"
    assert "routing_recommendation" in result
    assert result["routing_recommendation"] in gov.buckets
    assert "message" in result
