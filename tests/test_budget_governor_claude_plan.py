"""#396: the Claude plan as a free-while-available Budget Governor bucket.

The plan is paid for whether it is used or not, and its weekly window resets,
so while it has headroom it is the first choice. Its availability comes from
the same plan status the narrator shows; an unknown or stale reading never
counts as free.
"""
from unittest.mock import patch

import pytest

from services.budget_governor import NeonBudgetGovernor


def _gov(state, spend_log=(), raises=False):
    def status():
        if raises:
            raise RuntimeError("store down")
        if state is None:
            return None
        return {"state": state, "reason": f"plan {state}", "summary_line": f"Claude: {state}"}
    gov = NeonBudgetGovernor(neon_url=None, claude_plan_status=status)
    gov._load_spend_log = lambda: list(spend_log)
    gov.get_helix_balance = lambda: None
    return gov


def test_available_plan_is_recommended_first():
    assert _gov("available").recommend_bucket() == "claude_plan"


def test_constrained_plan_comes_after_spend_buckets():
    assert _gov("constrained").recommend_bucket() == "helix"


def test_constrained_plan_beats_guard_buckets_when_spend_buckets_are_used_up():
    spent = [{"bucket": "helix", "cost": 1000.0, "ts": "2026-11-17T00:00:00+00:00"},
             {"bucket": "gemini", "cost": 1000.0, "ts": "2026-11-17T00:00:00+00:00"}]
    gov = _gov("constrained", spend_log=spent)
    gov._total_spent = lambda name, log=None: sum(e["cost"] for e in (log or []) if e["bucket"] == name)
    assert gov.recommend_bucket() == "claude_plan"


@pytest.mark.parametrize("state", ["exhausted", "unknown", None])
def test_exhausted_or_unknown_plan_is_never_recommended(state):
    assert _gov(state).recommend_bucket() == "helix"


def test_a_failing_status_reader_fails_closed():
    assert _gov("available", raises=True).recommend_bucket() == "helix"


def test_without_a_status_reader_the_governor_is_unchanged():
    gov = NeonBudgetGovernor(neon_url=None)
    gov._load_spend_log = lambda: []
    gov.get_helix_balance = lambda: None
    assert gov.recommend_bucket() == "helix"
    assert "claude_plan" not in gov.get_status()["buckets"]


def test_status_reports_the_plan_bucket():
    status = _gov("available").get_status()
    plan = status["buckets"]["claude_plan"]
    assert plan["type"] == "plan"
    assert plan["state"] == "available"
    assert plan["envelope"] == "allow"
    assert plan["summary_line"] == "Claude: available"
    assert status["recommendation"] == "claude_plan"


@pytest.mark.parametrize("state,envelope", [("constrained", "defer"), ("exhausted", "deny"),
                                            ("unknown", "deny"), (None, "deny")])
def test_plan_envelope_follows_the_plan_state(state, envelope):
    gov = _gov(state)
    assert gov.check_envelope("claude_plan", 0.01) == envelope
    assert gov.get_status()["buckets"]["claude_plan"]["envelope"] == envelope


def test_spend_is_never_recorded_against_the_plan():
    gov = _gov("available")
    with patch.object(gov, "_persist_spend") as persist:
        gov.record_spend("claude_plan", 1.0)
    persist.assert_not_called()


def test_the_server_governor_reads_the_local_plan_status():
    import sys
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}), \
         patch("psycopg2.connect"):
        import mcp_server
        gov = mcp_server._neon_budget_governor
        with patch.object(mcp_server, "resolve_target_user", return_value="test-user"), \
             patch.object(mcp_server, "_get_claude_plan_status_sync",
                          return_value={"state": "available", "summary_line": "Claude: available"}) as status, \
             patch.object(gov, "_load_spend_log", return_value=[]), \
             patch.object(gov, "get_helix_balance", return_value=None):
            assert gov.recommend_bucket() == "claude_plan"
            status.assert_called_with("test-user")
        with patch.object(mcp_server, "resolve_target_user", return_value=None), \
             patch.object(gov, "_load_spend_log", return_value=[]):
            assert gov.check_envelope("claude_plan", 0.01) == "deny"
    sys.modules.pop("mcp_server", None)
