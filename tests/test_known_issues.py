"""Failure-driven tests that capture known gaps in Mecris.
Each test deliberately fails until the corresponding issue is fixed.

ARCHITECTURAL DECISION RECORD (ADR-001):
GitHub MCP Operations are OUT OF SCOPE for Mecris

CONTEXT: Mecris config includes both 'mecris' and 'github' MCP servers, leading to 
confusion about whether GitHub operations are part of Mecris functionality.

DECISION: Mecris focuses exclusively on SMS accountability and budget tracking.
GitHub operations are handled by the separate GitHub MCP server.

RATIONALE: 
- Separation of concerns: Mecris = personal accountability, GitHub MCP = repository management
- Clear boundaries prevent feature creep
- Each MCP server has distinct, focused responsibilities

CONSEQUENCES: 
- GitHub issue management tests belong in GitHub MCP server tests, not Mecris
- Goal tracking beyond usage/budget belongs in external systems (Beeminder)
- Mecris tests focus on SMS reminders, budget tracking, and usage monitoring

STATUS: Accepted
"""

import os
import sys
import pytest
import requests

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from usage_tracker import UsageTracker
from virtual_budget_manager import get_virtual_budget_status

# Helper dummy response for request mocking (re‑used in several tests)
class DummyResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data or {}
        self.status_code = status_code
    def json(self):
        return self._json

# ---------------------------------------------------------------------------
# 1. Negative token validation in UsageTracker.calculate_cost
# ---------------------------------------------------------------------------

def test_calculate_cost_negative_tokens():
    tracker = UsageTracker(db_path=":memory:")
    with pytest.raises(ValueError):
        tracker.calculate_cost("claude-3-5-sonnet-20241022", -1, 0)

# ---------------------------------------------------------------------------
# 2. Budget should never be negative & expose budget_exhausted flag
# ---------------------------------------------------------------------------

def test_budget_never_negative(monkeypatch):
    # Force an over-spend scenario via mocking
    def mock_get_virtual_budget_status():
        return {
            "total_budget": 10,
            "remaining_budget": -5,
            "days_remaining": 5,
            "alerts": [],
        }
    monkeypatch.setattr('virtual_budget_manager.get_virtual_budget_status', mock_get_virtual_budget_status)
    status = get_virtual_budget_status()
    assert status["remaining_budget"] >= 0, "remaining_budget must be non‑negative"
    # Optional: check a custom flag if you add one later
    # assert status.get("budget_exhausted") is True

# ---------------------------------------------------------------------------
# 3. Graceful fallback when MCP server is unavailable  
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="MCP integration pattern needs refactoring - see ADR-001")
def test_get_narrator_context_graceful_fallback(monkeypatch):
    """Test that narrator context gracefully handles MCP server failures.
    
    NOTE: This test is currently skipped because the MCP integration pattern
    needs refactoring. The current mcp__mecris__* function pattern may not
    be the final implementation approach.
    """
    # Simulate the MCP call raising an exception
    def broken():
        raise RuntimeError("MCP dead")
    # TODO: Determine final MCP integration pattern before implementing
    # monkeypatch.setattr('mcp_integration.get_narrator_context', broken)
    # ctx = get_narrator_context()
    # assert isinstance(ctx, dict)
    # assert ctx.get("error") == "MCP unavailable"
    pass

# ---------------------------------------------------------------------------
# 4. Live Beeminder test should be skipped when env var set or token missing
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    os.getenv('SKIP_LIVE_TESTS') == 'true' or not os.getenv('BEEMINDER_TOKEN'),
    reason="Live test disabled"
)
def test_beeminder_live_placeholder():
    # This placeholder will be replaced by the real live test when you enable it.
    assert True

# ---------------------------------------------------------------------------
# 5. Delivery fallback chain (SMS -> console fallback)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Test implementation needs refactoring to match current architecture")
def test_fallback_to_console():
    """Test that delivery falls back from SMS to console when SMS fails.
    
    This is a valid test concept for Mecris but needs refactoring to match
    the actual delivery system architecture rather than importing test functions.
    """
    # TODO: Implement proper delivery fallback testing
    # Should test twilio_sender.py fallback logic directly
    pass

# ---------------------------------------------------------------------------
# ❌ OUT OF SCOPE: Goal management tests
# ADR-001: Goal tracking belongs in external systems (Beeminder), not Mecris
# ---------------------------------------------------------------------------
# def test_prevent_duplicate_goals():
#     """This functionality belongs in Beeminder integration, not Mecris core."""
#     tracker = UsageTracker(db_path=":memory:")
#     g1 = tracker.add_goal("Test Goal")
#     with pytest.raises(RuntimeError):
#         tracker.add_goal("Test Goal")
#
# def test_complete_goal_idempotent():
#     """Goal completion is Beeminder's responsibility, not Mecris."""
#     tracker = UsageTracker(db_path=":memory:")
#     g = tracker.add_goal("Idempotent Goal")
#     first = tracker.complete_goal(g["goal_id"])
#     second = tracker.complete_goal(g["goal_id"])
#     assert second["completed"] is True
#     assert first["completed_at"] == second["completed_at"]

# ---------------------------------------------------------------------------
# 7. record_session should validate session_type
# ---------------------------------------------------------------------------
def test_invalid_session_type_raises():
    tracker = UsageTracker(db_path=":memory:")
    with pytest.raises(ValueError):
        tracker.record_session(
            "claude-3-5-sonnet-20241022",
            input_tokens=10,
            output_tokens=5,
            session_type="typo"
        )

# ---------------------------------------------------------------------------
# ❌ OUT OF SCOPE: GitHub MCP server functionality 
# ADR-001: GitHub operations are handled by separate GitHub MCP server, not Mecris
# ---------------------------------------------------------------------------
# def test_github_rate_limit_handling(monkeypatch):
#     """GitHub rate limiting belongs in GitHub MCP server tests, not Mecris."""
#     class Resp:
#         status_code = 403
#         headers = {"X-RateLimit-Remaining": "0"}
#         def json(self):
#             return {"message": "rate limit exceeded"}
#     monkeypatch.setattr('requests.post', lambda *a, **kw: Resp())
#     from mcp__github__create_issue import create_issue
#     with pytest.raises(RuntimeError) as exc:
#         create_issue(owner='kingdonb', repo='mecris', title='test', body='')
#     assert 'rate limit' in str(exc.value).lower()

"""End of failure‑driven test suite.

NOTE: Tests for goal management and GitHub operations have been commented out
as they fall outside Mecris' core scope per ADR-001. These features are handled
by external systems (Beeminder for goals, GitHub MCP server for repository operations).
"""
