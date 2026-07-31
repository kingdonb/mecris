"""
tests/test_neon_spend_log.py

Verifies Phase 1 completion: Neon-backed spend log for Budget Governor.
Tests both NeonBudgetGovernor and fallback to JSON file when NEON_DB_URL absent.

Plan: yebyen/mecris#26 Phase 1
"""
import os
import json
import pytest
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, Mock

# Test NeonBudgetGovernor (new implementation)
from services.budget_governor import NeonBudgetGovernor

# Test legacy BudgetGovernor fallback
from services.budget_governor import BudgetGovernor


class TestNeonSpendLog:
    """Test Neon-backed spend log with 39-minute window queries."""

    @pytest.fixture
    def mock_neon_url(self):
        """Provide a mock Neon URL for testing."""
        return "postgresql://test:test@localhost/test"

    @pytest.fixture
    def neon_governor(self, mock_neon_url):
        """Create NeonBudgetGovernor with mocked DB."""
        with patch("services.budget_governor.NeonBudgetGovernor._init_db"):
            gov = NeonBudgetGovernor(neon_url=mock_neon_url, user_id="test-user")
        return gov

    def test_check_envelope_allow_when_empty(self, neon_governor):
        """Fresh governor: small estimate is always allowed."""
        with patch.object(neon_governor, '_load_spend_log', return_value=[]):
            result = neon_governor.check_envelope("anthropic_api", 0.10)
        assert result == "allow"

    def test_check_envelope_deny_when_total_exhausted(self, neon_governor):
        """If total spend >= limit, deny immediately."""
        with patch.object(neon_governor, '_load_spend_log', return_value=[
            {"bucket": "anthropic_api", "cost": 20.89, "ts": datetime.now(timezone.utc) - timedelta(hours=1)}
        ]):
            result = neon_governor.check_envelope("anthropic_api", 0.01)
        assert result == "deny"

    def test_check_envelope_defer_when_window_full(self, neon_governor):
        """If 5% of quota spent in last 39 min, defer."""
        with patch.object(neon_governor, '_load_spend_log', return_value=[
            {"bucket": "anthropic_api", "cost": 1.04, "ts": datetime.now(timezone.utc) - timedelta(minutes=10)}
        ]):
            result = neon_governor.check_envelope("anthropic_api", 0.01)
        assert result == "defer"

    def test_check_envelope_allow_when_window_exactly_at_cap(self, neon_governor):
        """At exactly 5% cap, still allow (not > cap)."""
        with patch.object(neon_governor, '_load_spend_log', return_value=[
            {"bucket": "groq", "cost": 0.49, "ts": datetime.now(timezone.utc) - timedelta(minutes=10)}
        ]):
            # groq limit = 10.00, 5% = 0.50. 0.49 + 0.01 = 0.50 (not > 0.50)
            result = neon_governor.check_envelope("groq", 0.01)
        assert result == "allow"

    def test_39min_window_query_excludes_old_entries(self, neon_governor):
        """Window query ignores entries older than 39 minutes."""
        now = datetime.now(timezone.utc)
        with patch.object(neon_governor, '_load_spend_log', return_value=[
            {"bucket": "groq", "cost": 5.00, "ts": now - timedelta(minutes=10)},  # in window
            {"bucket": "groq", "cost": 3.00, "ts": now - timedelta(hours=2)},     # outside window
        ]):
            window_spent = neon_governor._window_spent("groq")
        assert window_spent == pytest.approx(5.00)


class TestLegacyFallback:
    """Test BudgetGovernor falls back to JSON file when NEON_DB_URL absent."""

    def test_json_fallback_when_no_db_url(self, tmp_path):
        """BudgetGovernor works with file path when no NEON_DB_URL."""
        log_path = str(tmp_path / "spend_log.json")
        
        with patch.dict(os.environ, {"NEON_DB_URL": ""}, clear=False):
            gov = BudgetGovernor(spend_log_path=log_path)
        
        # Record a spend
        gov.record_spend("anthropic_api", 0.50)
        
        # Verify it was persisted to file
        with open(log_path, "r") as f:
            data = json.load(f)
        
        assert len(data) == 1
        assert data[0]["bucket"] == "anthropic_api"
        assert data[0]["cost"] == 0.50

    def test_json_fallback_persists_across_restarts(self, tmp_path):
        """Spend events survive process restart via JSON file."""
        log_path = str(tmp_path / "spend_log.json")
        
        with patch.dict(os.environ, {"NEON_DB_URL": ""}, clear=False):
            gov1 = BudgetGovernor(spend_log_path=log_path)
            gov1.record_spend("groq", 1.00)
            gov1.record_spend("groq", 2.00)
        
        # New instance from same file
        with patch.dict(os.environ, {"NEON_DB_URL": ""}, clear=False):
            gov2 = BudgetGovernor(spend_log_path=log_path)
        
        assert gov2._total_spent("groq") == pytest.approx(3.00)

    def test_corrupt_json_recovers_gracefully(self, tmp_path):
        """Corrupt JSON file doesn't crash - starts fresh."""
        log_path = str(tmp_path / "spend_log.json")
        
        with open(log_path, "w") as f:
            f.write("not valid json {{{{")
        
        with patch.dict(os.environ, {"NEON_DB_URL": ""}, clear=False):
            gov = BudgetGovernor(spend_log_path=log_path)
        
        assert gov._total_spent("anthropic_api") == 0.0


class TestEnvelopeDecisionsMatch:
    """Both implementations produce identical envelope decisions for same input."""

    def test_same_input_same_output(self):
        """Legacy and Neon governors agree on envelope decisions."""
        # Create a shared spend log
        spend_log = [
            {"bucket": "groq", "cost": 0.49, "ts": datetime.now(timezone.utc) - timedelta(minutes=10)},
            {"bucket": "groq", "cost": 1.00, "ts": datetime.now(timezone.utc) - timedelta(hours=1)},
        ]
        
        # Legacy governor with file path (won't actually use file in test)
        with patch.dict(os.environ, {"NEON_DB_URL": ""}, clear=False):
            legacy = BudgetGovernor(spend_log_path="/tmp/test.json")
            legacy._spend_log = spend_log
        
        # Neon governor with mocked load
        with patch("services.budget_governor.NeonBudgetGovernor._init_db"):
            neon = NeonBudgetGovernor(neon_url="postgresql://test", user_id="test")
            neon._load_spend_log = Mock(return_value=spend_log)
        
        # Test check_envelope
        assert legacy.check_envelope("groq", 0.02) == neon.check_envelope("groq", 0.02)
        
        # Test recommend_bucket
        assert legacy.recommend_bucket() == neon.recommend_bucket()
        
        # Test get_status structure
        legacy_status = legacy.get_status()
        neon_status = neon.get_status()
        
        for bucket in ["helix", "gemini", "anthropic_api", "groq"]:
            assert legacy_status["buckets"][bucket]["envelope"] == neon_status["buckets"][bucket]["envelope"]
            assert legacy_status["buckets"][bucket]["spent_total"] == pytest.approx(neon_status["buckets"][bucket]["spent_total"])
        
        assert legacy_status["recommendation"] == neon_status["recommendation"]
        assert legacy_status["envelope_status"] == neon_status["envelope_status"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])