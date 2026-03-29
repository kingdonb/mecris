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
