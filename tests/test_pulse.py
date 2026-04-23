"""
tests/test_pulse.py — Unit tests for cli/pulse.py

Tests render_pulse with mocked context data so no MCP calls are made.
"""
import io
import pytest
from datetime import datetime

from cli.pulse import (
    _risk_color,
    _budget_color,
    _walk_status_text,
    build_mock_context,
    render_pulse,
)


# ── Helper colour logic ───────────────────────────────────────────────────────

def test_risk_color_critical():
    assert _risk_color("CRITICAL") == "bold red"


def test_risk_color_safe():
    assert _risk_color("SAFE") == "green"


def test_risk_color_unknown():
    assert _risk_color("BLORP") == "white"


def test_risk_color_case_insensitive():
    assert _risk_color("critical") == "bold red"
    assert _risk_color("Warning") == "bold yellow"


def test_budget_color_critical():
    assert _budget_color(0.95) == "bold red"


def test_budget_color_warning():
    assert _budget_color(0.80) == "bold yellow"


def test_budget_color_safe():
    assert _budget_color(0.50) == "green"


def test_walk_status_complete():
    label, color = _walk_status_text({"status": "complete"})
    assert label == "Complete"
    assert color == "green"


def test_walk_status_needed():
    label, color = _walk_status_text({"status": "needed"})
    assert label == "NEEDED"
    assert color == "bold red"


def test_walk_status_unknown():
    label, color = _walk_status_text({})
    assert label == "Unknown"


# ── Mock context ──────────────────────────────────────────────────────────────

def test_build_mock_context_structure():
    ctx = build_mock_context()
    required = [
        "summary", "goal_runway", "budget_status",
        "daily_walk_status", "system_pulse",
        "daily_aggregate_status", "recommendations",
        "urgent_items", "last_updated",
    ]
    for key in required:
        assert key in ctx, f"Missing key: {key}"


def test_mock_context_has_goals():
    ctx = build_mock_context()
    assert len(ctx["goal_runway"]) >= 1
    goal = ctx["goal_runway"][0]
    assert "slug" in goal
    assert "safebuf" in goal
    assert "derail_risk" in goal


# ── render_pulse smoke test ───────────────────────────────────────────────────

def test_render_pulse_does_not_raise():
    """render_pulse must complete without raising on valid mock data."""
    ctx = build_mock_context()
    render_pulse(ctx)  # Would raise if any key access or rich API call fails


def test_render_pulse_with_urgent_items():
    ctx = build_mock_context()
    ctx["urgent_items"] = ["DERAILING: weight", "WALK NEEDED: Activity Log"]
    render_pulse(ctx)  # Must not raise


def test_render_pulse_with_empty_goal_runway():
    ctx = build_mock_context()
    ctx["goal_runway"] = []
    render_pulse(ctx)  # Must not raise (table is skipped gracefully)


def test_render_pulse_with_vacation_mode():
    ctx = build_mock_context()
    ctx["vacation_mode"] = True
    render_pulse(ctx)


def test_render_pulse_with_all_clear():
    ctx = build_mock_context()
    ctx["daily_aggregate_status"] = {"all_clear": True, "score": "3/3"}
    render_pulse(ctx)


def test_render_pulse_scheduler_down():
    ctx = build_mock_context()
    ctx["system_pulse"] = {"running": False, "is_leader": False, "process_id": "dead"}
    render_pulse(ctx)
