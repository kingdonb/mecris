"""Unit tests for virtual_budget_manager.py — VirtualBudgetManager class.

Covers:
- calculate_cost: pure math for known models and fallback to default pricing
- can_afford: early return when NEON_DB_URL absent
- get_budget_status: early return when no DB
- get_usage_summary: early return when no DB
- reset_daily_budget: early return when no DB
- record_usage: early returns for no-budget and no-DB paths
- Provider enum values

All tests run without a live database by omitting NEON_DB_URL from the environment.
Closes yebyen/mecris#195
"""
import os
import pytest
from unittest.mock import patch
from virtual_budget_manager import VirtualBudgetManager, Provider

FAKE_USER = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_vbm(user_id=FAKE_USER) -> VirtualBudgetManager:
    """Create VirtualBudgetManager with no DB and a fixed user_id."""
    env = {}
    env.pop("NEON_DB_URL", None)
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("NEON_DB_URL", None)
        with patch(
            "virtual_budget_manager.credentials_manager.resolve_user_id",
            return_value=user_id,
        ):
            vbm = VirtualBudgetManager(user_id=user_id)
    return vbm


# ---------------------------------------------------------------------------
# Provider enum
# ---------------------------------------------------------------------------

class TestProviderEnum:
    def test_anthropic_value(self):
        assert Provider.ANTHROPIC.value == "anthropic"

    def test_groq_value(self):
        assert Provider.GROQ.value == "groq"


# ---------------------------------------------------------------------------
# calculate_cost — pure math, no DB
# ---------------------------------------------------------------------------

class TestCalculateCost:
    def setup_method(self):
        self.vbm = _make_vbm()

    def test_anthropic_sonnet_known_model(self):
        # claude-3-5-sonnet: input $3/1M, output $15/1M
        cost = self.vbm.calculate_cost(
            Provider.ANTHROPIC, "claude-3-5-sonnet-20241022", 1_000_000, 0
        )
        assert cost == pytest.approx(3.0, abs=1e-6)

    def test_anthropic_sonnet_output_tokens(self):
        cost = self.vbm.calculate_cost(
            Provider.ANTHROPIC, "claude-3-5-sonnet-20241022", 0, 1_000_000
        )
        assert cost == pytest.approx(15.0, abs=1e-6)

    def test_groq_llama_70b_known_model(self):
        # llama-3.3-70b-versatile: $0.08/1M input+output
        cost = self.vbm.calculate_cost(
            Provider.GROQ, "llama-3.3-70b-versatile", 1_000_000, 0
        )
        assert cost == pytest.approx(0.08, abs=1e-6)

    def test_anthropic_haiku_known_model(self):
        # claude-3-5-haiku: input $0.25/1M
        cost = self.vbm.calculate_cost(
            Provider.ANTHROPIC, "claude-3-5-haiku-20241022", 1_000_000, 0
        )
        assert cost == pytest.approx(0.25, abs=1e-6)

    def test_unknown_anthropic_model_falls_back_to_sonnet(self):
        # Unknown model → fallback is claude-3-5-sonnet pricing ($3/1M input)
        cost_unknown = self.vbm.calculate_cost(
            Provider.ANTHROPIC, "claude-9-ultramax", 1_000_000, 0
        )
        cost_sonnet = self.vbm.calculate_cost(
            Provider.ANTHROPIC, "claude-3-5-sonnet-20241022", 1_000_000, 0
        )
        assert cost_unknown == pytest.approx(cost_sonnet, abs=1e-6)

    def test_unknown_groq_model_falls_back_to_gpt_oss_120b(self):
        # Unknown model → fallback is openai/gpt-oss-120b pricing ($0.15/1M)
        cost_unknown = self.vbm.calculate_cost(
            Provider.GROQ, "some-new-model", 1_000_000, 0
        )
        cost_fallback = self.vbm.calculate_cost(
            Provider.GROQ, "openai/gpt-oss-120b", 1_000_000, 0
        )
        assert cost_unknown == pytest.approx(cost_fallback, abs=1e-6)

    def test_zero_tokens_returns_zero(self):
        cost = self.vbm.calculate_cost(
            Provider.ANTHROPIC, "claude-3-5-sonnet-20241022", 0, 0
        )
        assert cost == 0.0


# ---------------------------------------------------------------------------
# can_afford — no DB path
# ---------------------------------------------------------------------------

class TestCanAffordNoDb:
    def test_returns_cannot_afford_when_no_db(self):
        vbm = _make_vbm()
        result = vbm.can_afford(0.50)
        assert result["can_afford"] is False
        assert result["reason"] == "No DB"


# ---------------------------------------------------------------------------
# get_budget_status — no DB path
# ---------------------------------------------------------------------------

class TestGetBudgetStatusNoDb:
    def test_returns_error_when_no_db(self):
        vbm = _make_vbm()
        result = vbm.get_budget_status()
        assert "error" in result


# ---------------------------------------------------------------------------
# get_usage_summary — no DB path
# ---------------------------------------------------------------------------

class TestGetUsageSummaryNoDb:
    def test_returns_error_when_no_db(self):
        vbm = _make_vbm()
        result = vbm.get_usage_summary()
        assert "error" in result


# ---------------------------------------------------------------------------
# reset_daily_budget — no DB path
# ---------------------------------------------------------------------------

class TestResetDailyBudgetNoDb:
    def test_returns_error_when_no_db(self):
        vbm = _make_vbm()
        result = vbm.reset_daily_budget()
        assert "error" in result


# ---------------------------------------------------------------------------
# record_usage — no-afford and no-DB paths
# ---------------------------------------------------------------------------

class TestRecordUsageNoDb:
    def test_returns_not_recorded_when_cannot_afford(self):
        """Without DB, can_afford returns False → record_usage short-circuits."""
        vbm = _make_vbm()
        result = vbm.record_usage(
            Provider.ANTHROPIC, "claude-3-5-sonnet-20241022", 1000, 500
        )
        assert result["recorded"] is False
        assert "reason" in result
        assert "cost" in result

    def test_emergency_override_returns_not_recorded_no_db(self):
        """With emergency_override=True but no DB, hits no-DB guard and returns not-recorded."""
        vbm = _make_vbm()
        result = vbm.record_usage(
            Provider.ANTHROPIC,
            "claude-3-5-sonnet-20241022",
            100,
            50,
            emergency_override=True,
        )
        assert result["recorded"] is False
        assert result["reason"] == "No DB configured"
