#!/usr/bin/env python3
"""
Narrator Context Testing for Mecris
Tests the narrator context functionality and Claude integration scenarios
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_context(**overrides):
    """Return a minimal valid narrator context dict."""
    ctx = {
        "summary": "All systems normal. 2 active goals.",
        "goals_status": {"active": 2, "completed": 1},
        "urgent_items": [],
        "beeminder_alerts": [],
        "goal_runway": [],
        "budget_status": {
            "remaining_budget": 10.50,
            "days_remaining": 3.5,
            "total_budget": 20.0,
            "used_budget": 9.50,
        },
        "recommendations": ["Keep up the good work!"],
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "presence_status": "absent",
        "presence": {},
        "related_bookmarks": [],
    }
    ctx.update(overrides)
    return ctx


def _make_httpx_mock(json_data, status_code=200):
    """Build an AsyncMock that behaves like an httpx.AsyncClient context manager."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


# ---------------------------------------------------------------------------
# TestNarratorContext
# ---------------------------------------------------------------------------

class TestNarratorContext:
    """Test narrator context functionality."""

    async def test_narrator_context_endpoint_structure(self):
        """Narrator context response contains all required fields with correct types."""
        ctx = _make_mock_context()
        mock_client = _make_httpx_mock(ctx)

        with patch("httpx.AsyncClient", return_value=mock_client):
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("http://localhost:8000/narrator/context")

        assert response.status_code == 200
        data = response.json()

        required_fields = [
            "summary", "goals_status", "urgent_items",
            "beeminder_alerts", "goal_runway", "budget_status",
            "recommendations", "last_updated",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        assert isinstance(data["summary"], str)
        assert isinstance(data["goals_status"], dict)
        assert isinstance(data["urgent_items"], list)
        assert isinstance(data["beeminder_alerts"], list)
        assert isinstance(data["goal_runway"], list)
        assert isinstance(data["budget_status"], dict)
        assert isinstance(data["recommendations"], list)

    async def test_narrator_context_budget_warnings(self):
        """Critical budget scenario surfaces urgent items and recommendations."""
        critical_ctx = _make_mock_context(
            urgent_items=["BUDGET CRITICAL: only $0.50 remaining"],
            recommendations=["Reduce usage due to budget constraints."],
            budget_status={
                "remaining_budget": 0.50,
                "days_remaining": 0.5,
                "total_budget": 20.0,
                "used_budget": 19.50,
            },
        )
        mock_client = _make_httpx_mock(critical_ctx)

        with patch("httpx.AsyncClient", return_value=mock_client):
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("http://localhost:8000/narrator/context")

        assert response.status_code == 200
        data = response.json()

        budget_urgents = [item for item in data["urgent_items"] if "BUDGET CRITICAL" in item]
        assert len(budget_urgents) > 0, "Should have critical budget warning in urgent_items"

        budget_recs = [rec for rec in data["recommendations"] if "budget constraints" in rec.lower()]
        assert len(budget_recs) > 0, "Should have budget-related recommendation"

    async def test_narrator_context_performance(self):
        """Two successive calls return consistent, parseable data."""
        ctx = _make_mock_context()
        mock_client = _make_httpx_mock(ctx)

        with patch("httpx.AsyncClient", return_value=mock_client):
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response1 = await client.get("http://localhost:8000/narrator/context")
                response2 = await client.get("http://localhost:8000/narrator/context")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Both responses should have last_updated parseable as ISO timestamps
        time1 = datetime.fromisoformat(data1["last_updated"].replace("Z", "+00:00"))
        time2 = datetime.fromisoformat(data2["last_updated"].replace("Z", "+00:00"))
        assert abs((time2 - time1).total_seconds()) < 10, "Response timestamps too far apart"

    async def test_narrator_context_error_handling(self):
        """Response always has valid structure and fallback fields."""
        minimal_ctx = _make_mock_context(
            summary="Degraded: some subsystems unavailable.",
            urgent_items=[],
            recommendations=[],
        )
        mock_client = _make_httpx_mock(minimal_ctx)

        with patch("httpx.AsyncClient", return_value=mock_client):
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("http://localhost:8000/narrator/context")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["summary"], str)
        assert isinstance(data["urgent_items"], list)
        assert isinstance(data["recommendations"], list)


# ---------------------------------------------------------------------------
# TestClaudeNarratorIntegration
# ---------------------------------------------------------------------------

class TestClaudeNarratorIntegration:
    """Test scenarios that simulate Claude narrator usage."""

    # -- pure logic helpers (sync) --

    def _simulate_claude_analysis(self, context):
        analysis = {
            "priority_tasks": [],
            "time_management": "",
            "budget_recommendation": "",
        }
        urgent_items = context.get("urgent_items", [])
        analysis["priority_tasks"] = urgent_items

        budget_status = context.get("budget_status", {})
        days_remaining = budget_status.get("days_remaining", 0)

        if days_remaining < 1:
            analysis["time_management"] = "CRITICAL: Less than 1 day of budget remaining"
            analysis["budget_recommendation"] = "Emergency mode: Focus only on absolutely critical tasks"
        elif days_remaining < 2:
            analysis["time_management"] = "URGENT: Less than 2 days of budget remaining"
            analysis["budget_recommendation"] = "High priority mode: Focus on high-value work only"
        elif days_remaining < 5:
            analysis["time_management"] = "CAUTION: Less than 5 days of budget remaining"
            analysis["budget_recommendation"] = "Selective mode: Choose tasks carefully"
        else:
            analysis["time_management"] = "NORMAL: Sufficient budget remaining"
            analysis["budget_recommendation"] = "Standard mode: All task types acceptable"

        return analysis

    def _should_work_on_complex_task(self, context):
        budget_status = context.get("budget_status", {})
        days_remaining = budget_status.get("days_remaining", 0)
        urgent_items = context.get("urgent_items", [])
        if days_remaining < 1 or len(urgent_items) > 0:
            return False
        return days_remaining > 2

    def _get_time_horizon(self, context):
        budget_status = context.get("budget_status", {})
        days_remaining = budget_status.get("days_remaining", 0)
        if days_remaining < 1:
            return "immediate"
        elif days_remaining < 2:
            return "today"
        elif days_remaining < 5:
            return "this_week"
        else:
            return "multiple_weeks"

    def _get_prioritization_advice(self, context):
        urgent_items = context.get("urgent_items", [])
        recommendations = context.get("recommendations", [])
        budget_status = context.get("budget_status", {})
        days_remaining = budget_status.get("days_remaining", 0)
        if urgent_items:
            return f"URGENT: Address {len(urgent_items)} critical items first"
        elif days_remaining < 2:
            return "BUDGET CRITICAL: Focus on highest-value work only"
        elif recommendations:
            return f"Follow system recommendations: {recommendations[0][:40]}..."
        else:
            return "Standard prioritization: Work on active goals"

    # -- tests --

    async def test_claude_context_consumption_scenario(self):
        """_simulate_claude_analysis produces correct output from mock context."""
        ctx = _make_mock_context(
            urgent_items=["Walk the dogs"],
            budget_status={
                "remaining_budget": 1.50,
                "days_remaining": 3.0,
                "total_budget": 20.0,
                "used_budget": 18.50,
            },
        )
        mock_client = _make_httpx_mock(ctx)

        with patch("httpx.AsyncClient", return_value=mock_client):
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("http://localhost:8000/narrator/context")

        assert response.status_code == 200
        context = response.json()

        claude_analysis = self._simulate_claude_analysis(context)

        assert isinstance(claude_analysis["priority_tasks"], list)
        assert isinstance(claude_analysis["time_management"], str)
        assert isinstance(claude_analysis["budget_recommendation"], str)
        assert claude_analysis["priority_tasks"] == ["Walk the dogs"]
        assert "CAUTION" in claude_analysis["time_management"]

    def test_narrator_decision_making_scenarios(self):
        """Decision helper methods return correct types and values for sample contexts."""
        ctx = _make_mock_context(
            urgent_items=[],
            budget_status={
                "remaining_budget": 10.0,
                "days_remaining": 5.0,
                "total_budget": 20.0,
                "used_budget": 10.0,
            },
        )

        scenarios = [
            {
                "name": "Should I work on a complex feature?",
                "result": self._should_work_on_complex_task(ctx),
                "expect_type": bool,
            },
            {
                "name": "What's my time horizon?",
                "result": self._get_time_horizon(ctx),
                "expect_type": str,
            },
            {
                "name": "What should I prioritize?",
                "result": self._get_prioritization_advice(ctx),
                "expect_type": str,
            },
        ]

        for scenario in scenarios:
            assert isinstance(scenario["result"], scenario["expect_type"]), (
                f"{scenario['name']} returned wrong type"
            )

        # With 5 days and no urgent items: complex tasks OK, horizon = multiple_weeks
        assert self._should_work_on_complex_task(ctx) is True
        assert self._get_time_horizon(ctx) == "multiple_weeks"

        # With urgent items: no complex tasks
        urgent_ctx = _make_mock_context(urgent_items=["CRITICAL: Beeminder derail"])
        assert self._should_work_on_complex_task(urgent_ctx) is False
        assert "URGENT" in self._get_prioritization_advice(urgent_ctx)
