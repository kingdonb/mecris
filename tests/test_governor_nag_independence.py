"""Deterministic tools are not gated on the API-era anthropic_api bucket (#351, narrowed).

With every Budget Governor bucket at 'deny':
- check_reminder_needed still produces a walk reminder;
- get_coaching_insight and trigger_language_sync still return their
  deterministic content (no LLM call happens in either).
LLM tools such as get_real_anthropic_usage keep their gate.
"""
import datetime
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.budget_governor import NeonBudgetGovernor

INSIGHT = {"type": "momentum", "message": "Two walks this week. Keep it rolling.", "momentum": "high"}


@pytest.fixture
def server():
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}), \
         patch("psycopg2.connect"):
        import mcp_server
        with patch.object(NeonBudgetGovernor, "check_envelope", return_value="deny"), \
             patch.object(NeonBudgetGovernor, "recommend_bucket", return_value="helix"), \
             patch.object(mcp_server, "resolve_target_user", return_value="test-user"):
            yield mcp_server
    sys.modules.pop("mcp_server", None)


def _fake_coaching_service():
    insight = MagicMock()
    insight.to_dict.return_value = dict(INSIGHT)
    service = MagicMock()
    service.generate_insight = AsyncMock(return_value=insight)
    return MagicMock(return_value=service)


@pytest.mark.asyncio
async def test_coaching_insight_ignores_denied_buckets(server):
    with patch.object(server, "CoachingService", _fake_coaching_service()):
        result = await server.get_coaching_insight("test-user")
    assert "budget_halted" not in result
    assert result == INSIGHT


@pytest.mark.asyncio
async def test_language_sync_ignores_denied_buckets(server):
    synced = {"success": True, "languages": {"arabic": {"pushed": True}}}
    with patch.object(server.language_sync_service, "sync_all", AsyncMock(return_value=synced)) as sync_all:
        result = await server.trigger_language_sync()
    assert "budget_halted" not in result
    assert result == synced
    sync_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_walk_reminder_survives_denied_buckets(server):
    from services.reminder_service import ReminderService

    context = {"daily_walk_status": {"has_activity_today": False}, "beeminder_alerts": [], "goal_runway": []}

    class Afternoon(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 11, 14, 15, 0, 0)

    service = ReminderService(AsyncMock(return_value=context), server.get_coaching_insight)
    with patch.object(server, "CoachingService", _fake_coaching_service()), \
         patch("services.reminder_service.datetime", Afternoon):
        result = await service.check_reminder_needed("test-user")
    assert result["should_send"] is True
    assert result["type"] == "walk_reminder"


@pytest.mark.asyncio
async def test_llm_tool_keeps_its_gate(server):
    result = await server.get_real_anthropic_usage()
    assert result.get("budget_halted") is True
    assert result.get("bucket") == "anthropic_api"


def test_budget_governor_header_is_accurate():
    import services.budget_governor as bg
    doc = bg.__doc__ or ""
    assert "DEPRECATED" not in doc
    assert "DO NOT MODIFY" not in doc
    assert "NeonBudgetGovernor" in doc
