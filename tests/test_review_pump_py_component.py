"""
Tests for poc/wasm/review-pump-py/app.py (kingdonb/mecris#157 POC)

Validates the pure-logic functions (calculate_target, get_status,
_parse_request, _json_ok, _error_json) directly.  Tests run against the
Python source without the WASM runtime — componentize-py wraps this same
logic.

The IncomingHandler class requires spin_sdk (only available inside the
compiled WASM component) and is NOT tested here.  HTTP end-to-end
validation requires `spin test` in the deployment environment.

Coverage mirrors the Rust unit tests in mecris-go-spin/review-pump/src/lib.rs
so both implementations can be verified against the same logic contract.
"""

import importlib.util
import json
import os

import pytest

# Load app.py by absolute path to avoid sys.modules collision with other
# WASM component test files that also do `import app`.
_COMPONENT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "poc", "wasm", "review-pump-py")
)
_spec = importlib.util.spec_from_file_location(
    "review_pump_py_app", os.path.join(_COMPONENT_DIR, "app.py")
)
app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app)


# ---------------------------------------------------------------------------
# calculate_target — core arithmetic
# ---------------------------------------------------------------------------


class TestCalculateTarget:
    def test_maintenance_returns_liability_only(self):
        # 1.0x Maintenance (multiplier_x10=10) → days=None → target = tomorrow_liability
        assert app.calculate_target(1000, 50, 10) == 50

    def test_steady_clears_debt_over_14_days(self):
        # 2.0x Steady: target = 50 + 140 // 14 = 60
        assert app.calculate_target(140, 50, 20) == 60

    def test_brisk_clears_debt_over_10_days(self):
        assert app.calculate_target(100, 50, 30) == 60

    def test_aggressive_clears_debt_over_7_days(self):
        assert app.calculate_target(70, 50, 40) == 60

    def test_high_pressure_clears_debt_over_5_days(self):
        assert app.calculate_target(50, 50, 50) == 60

    def test_very_high_clears_debt_over_3_days(self):
        assert app.calculate_target(30, 50, 60) == 60

    def test_the_blitz_clears_debt_over_2_days(self):
        assert app.calculate_target(20, 50, 70) == 60

    def test_system_overdrive_clears_debt_over_1_day(self):
        assert app.calculate_target(10, 50, 100) == 60

    def test_unknown_multiplier_falls_back_to_maintenance(self):
        # 999 is not a valid key → falls back to Maintenance (days=None)
        assert app.calculate_target(1000, 50, 999) == 50

    def test_zero_debt_all_multipliers(self):
        # No backlog → target = tomorrow_liability regardless of lever
        for multiplier_x10 in [10, 20, 30, 40, 50, 60, 70, 100]:
            result = app.calculate_target(0, 100, multiplier_x10)
            assert result == 100, f"failed for multiplier_x10={multiplier_x10}"

    def test_integer_division_rounds_down(self):
        # debt=15, days=14 → 15 // 14 = 1 (not 1.07)
        assert app.calculate_target(15, 50, 20) == 51


# ---------------------------------------------------------------------------
# get_status — flow state classification
# ---------------------------------------------------------------------------


class TestGetStatus:
    def test_cavitation_when_below_liability(self):
        s = app.get_status(0, 100, 50, 10, "points")
        assert s["status"] == "cavitation"

    def test_turbulent_when_at_or_above_target(self):
        # 2.0x Steady: target = 50 + 140 // 14 = 60; completions=60 → turbulent
        s = app.get_status(140, 50, 60, 20, "points")
        assert s["status"] == "turbulent"
        assert s["target_flow_rate"] == 0  # at target → nothing remaining

    def test_laminar_between_liability_and_target(self):
        # target = 60, completions = 55 → laminar
        s = app.get_status(140, 50, 55, 20, "points")
        assert s["status"] == "laminar"

    def test_laminar_at_liability(self):
        # completions == tomorrow_liability (not < it) → not cavitation
        # target > completions → not turbulent
        s = app.get_status(140, 50, 50, 20, "points")
        assert s["status"] == "laminar"

    def test_laminar_when_both_zero(self):
        # debt=0, liability=0 → special-case laminar
        s = app.get_status(0, 0, 0, 10, "points")
        assert s["status"] == "laminar"
        assert s["goal_met"] is True

    def test_turbulent_not_triggered_when_target_is_zero(self):
        # target=0: only turbulent if target > 0 (guard prevents false positive)
        s = app.get_status(0, 0, 0, 10, "points")
        assert s["status"] != "turbulent"

    def test_lever_name_returned(self):
        s = app.get_status(0, 100, 100, 40, "cards")
        assert s["lever_name"] == "Aggressive"

    def test_unit_returned(self):
        s = app.get_status(0, 100, 100, 40, "cards")
        assert s["unit"] == "cards"

    def test_multiplier_x10_returned(self):
        s = app.get_status(0, 100, 100, 40, "cards")
        assert s["multiplier_x10"] == 40

    def test_debt_remaining_returned(self):
        s = app.get_status(500, 50, 50, 20, "points")
        assert s["debt_remaining"] == 500

    def test_goal_met_when_completions_at_target(self):
        s = app.get_status(140, 50, 60, 20, "points")
        assert s["goal_met"] is True

    def test_goal_not_met_when_below_target(self):
        s = app.get_status(140, 50, 55, 20, "points")
        assert s["goal_met"] is False

    def test_maintenance_goal_met_when_liability_completed(self):
        # Maintenance (10): target = tomorrow_liability (no debt clearing).
        # goal_met = daily_completions >= target, regardless of residual debt.
        # Debt is not cleared in Maintenance mode — it is simply not targeted.
        assert app.get_status(0, 50, 50, 10)["goal_met"] is True
        assert app.get_status(100, 50, 50, 10)["goal_met"] is True  # debt present but not targeted
        assert app.get_status(100, 50, 49, 10)["goal_met"] is False  # below liability


# ---------------------------------------------------------------------------
# _parse_request — request body deserialization
# ---------------------------------------------------------------------------


class TestParseRequest:
    def test_full_valid_body(self):
        body = json.dumps(
            {
                "debt": 100,
                "tomorrow_liability": 50,
                "daily_completions": 30,
                "multiplier_x10": 20,
                "unit": "cards",
            }
        ).encode()
        result = app._parse_request(body)
        assert result == {
            "debt": 100,
            "tomorrow_liability": 50,
            "daily_completions": 30,
            "multiplier_x10": 20,
            "unit": "cards",
        }

    def test_empty_body_uses_defaults(self):
        result = app._parse_request(b"{}")
        assert result["debt"] == 0
        assert result["tomorrow_liability"] == 0
        assert result["daily_completions"] == 0
        assert result["multiplier_x10"] == 10
        assert result["unit"] == "points"

    def test_none_body_uses_defaults(self):
        result = app._parse_request(None)
        assert result["multiplier_x10"] == 10

    def test_malformed_json_uses_defaults(self):
        result = app._parse_request(b"not valid json")
        assert result["debt"] == 0

    def test_partial_body_fills_in_defaults(self):
        body = json.dumps({"debt": 200}).encode()
        result = app._parse_request(body)
        assert result["debt"] == 200
        assert result["tomorrow_liability"] == 0


# ---------------------------------------------------------------------------
# _json_ok / _error_json — serialization helpers
# ---------------------------------------------------------------------------


class TestSerializationHelpers:
    def test_json_ok_is_bytes(self):
        result = app._json_ok({"status": "laminar"})
        assert isinstance(result, bytes)

    def test_json_ok_round_trips(self):
        data = {"multiplier_x10": 20, "status": "laminar"}
        assert json.loads(app._json_ok(data)) == data

    def test_error_json_structure(self):
        result = json.loads(app._error_json("something broke"))
        assert result == {"error": "something broke"}

    def test_error_json_is_bytes(self):
        assert isinstance(app._error_json("oops"), bytes)


# ---------------------------------------------------------------------------
# ARABIC_POINTS_PER_CARD constant — must match Rust + Python source
# ---------------------------------------------------------------------------


def test_arabic_points_per_card_constant():
    assert app.ARABIC_POINTS_PER_CARD == 16
