"""
Tests for poc/wasm/budget-governor-py/app.py (yebyen/mecris#262)

Validates the pure-logic functions directly against the Python source without
the WASM runtime — componentize-py wraps the same logic for deployment.

The IncomingHandler class requires spin_sdk (only available inside the compiled
WASM component) and is NOT tested here. HTTP end-to-end validation requires
`spin test` in the deployment environment.

Coverage mirrors the envelope logic in services/budget_governor.py so both
implementations can be verified against the same logic contract.
"""

import importlib.util
import json
import os
from datetime import datetime, timedelta

import pytest

# Load app.py by absolute path to avoid sys.modules collision with other
# WASM component test files that also do `import app`.
_COMPONENT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "poc", "wasm", "budget-governor-py")
)
_spec = importlib.util.spec_from_file_location(
    "budget_governor_py_app", os.path.join(_COMPONENT_DIR, "app.py")
)
app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(limits=None):
    """Shorthand for make_bucket_config."""
    return app.make_bucket_config(limits)


def _recent_entry(bucket, cost):
    """Spend entry with a timestamp 1 minute ago (within the 39-min window)."""
    return {
        "bucket": bucket,
        "cost": cost,
        "ts": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
    }


def _old_entry(bucket, cost):
    """Spend entry with a timestamp 2 hours ago (outside the 39-min window)."""
    return {
        "bucket": bucket,
        "cost": cost,
        "ts": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
    }


# ---------------------------------------------------------------------------
# make_bucket_config — static config factory
# ---------------------------------------------------------------------------


class TestMakeBucketConfig:
    def test_returns_all_four_buckets(self):
        cfg = _cfg()
        assert set(cfg.keys()) == {"helix", "gemini", "anthropic_api", "groq"}

    def test_default_limits(self):
        cfg = _cfg()
        assert cfg["helix"]["limit"] == 100.00
        assert cfg["gemini"]["limit"] == 50.00
        assert cfg["anthropic_api"]["limit"] == 20.89
        assert cfg["groq"]["limit"] == 10.00

    def test_limit_override(self):
        cfg = _cfg({"helix": 200.00})
        assert cfg["helix"]["limit"] == 200.00
        assert cfg["gemini"]["limit"] == 50.00  # unchanged

    def test_bucket_types(self):
        cfg = _cfg()
        assert cfg["helix"]["type"] == "spend"
        assert cfg["gemini"]["type"] == "spend"
        assert cfg["anthropic_api"]["type"] == "guard"
        assert cfg["groq"]["type"] == "guard"


# ---------------------------------------------------------------------------
# _calc_total_spent — all-time accumulation
# ---------------------------------------------------------------------------


class TestCalcTotalSpent:
    def test_empty_log_returns_zero(self):
        assert app._calc_total_spent([], "anthropic_api") == 0.0

    def test_sums_matching_bucket(self):
        log = [_recent_entry("anthropic_api", 1.0), _recent_entry("anthropic_api", 0.5)]
        assert app._calc_total_spent(log, "anthropic_api") == 1.5

    def test_ignores_other_buckets(self):
        log = [_recent_entry("groq", 5.0), _recent_entry("anthropic_api", 1.0)]
        assert app._calc_total_spent(log, "groq") == 5.0
        assert app._calc_total_spent(log, "anthropic_api") == 1.0

    def test_old_entries_counted(self):
        # Total spend counts ALL time — old entries count toward the limit
        log = [_old_entry("groq", 3.0)]
        assert app._calc_total_spent(log, "groq") == 3.0


# ---------------------------------------------------------------------------
# _calc_window_spent — rolling 39-minute window
# ---------------------------------------------------------------------------


class TestCalcWindowSpent:
    def test_empty_log_returns_zero(self):
        assert app._calc_window_spent([], "anthropic_api") == 0.0

    def test_recent_entry_counted(self):
        log = [_recent_entry("anthropic_api", 0.50)]
        result = app._calc_window_spent(log, "anthropic_api")
        assert result == pytest.approx(0.50)

    def test_old_entry_not_counted(self):
        log = [_old_entry("anthropic_api", 5.0)]
        result = app._calc_window_spent(log, "anthropic_api")
        assert result == 0.0

    def test_mixed_entries_only_counts_recent(self):
        log = [_recent_entry("groq", 1.0), _old_entry("groq", 9.0)]
        result = app._calc_window_spent(log, "groq")
        assert result == pytest.approx(1.0)

    def test_ignores_other_buckets(self):
        log = [_recent_entry("helix", 10.0)]
        assert app._calc_window_spent(log, "groq") == 0.0

    def test_invalid_ts_string_skipped(self):
        log = [{"bucket": "groq", "cost": 5.0, "ts": "not-a-date"}]
        assert app._calc_window_spent(log, "groq") == 0.0

    def test_accepts_datetime_object_as_ts(self):
        log = [{"bucket": "groq", "cost": 2.0, "ts": datetime.utcnow() - timedelta(minutes=1)}]
        result = app._calc_window_spent(log, "groq")
        assert result == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# check_envelope — allow / defer / deny
# ---------------------------------------------------------------------------


class TestCheckEnvelope:
    def test_allow_when_empty_log(self):
        assert app.check_envelope([], _cfg(), "anthropic_api", 0.01) == "allow"

    def test_deny_when_total_at_limit(self):
        # Exhaust anthropic_api limit (20.89)
        log = [_old_entry("anthropic_api", 20.89)]
        assert app.check_envelope(log, _cfg(), "anthropic_api", 0.01) == "deny"

    def test_deny_when_total_exceeds_limit(self):
        log = [_old_entry("anthropic_api", 25.00)]
        assert app.check_envelope(log, _cfg(), "anthropic_api", 0.01) == "deny"

    def test_defer_when_window_would_exceed_5pct(self):
        # groq limit=10.00, 5% cap = 0.50/window
        # Already spent 0.49 in window, adding 0.02 would push to 0.51 > 0.50
        log = [_recent_entry("groq", 0.49)]
        assert app.check_envelope(log, _cfg(), "groq", 0.02) == "defer"

    def test_allow_when_window_exactly_at_cap(self):
        # groq 5% of 10.00 = 0.50; spent 0.49, cost 0.01 → total 0.50 (not > 0.50)
        log = [_recent_entry("groq", 0.49)]
        assert app.check_envelope(log, _cfg(), "groq", 0.01) == "allow"

    def test_unknown_bucket_raises(self):
        with pytest.raises(ValueError, match="Unknown bucket"):
            app.check_envelope([], _cfg(), "nonexistent", 0.01)

    def test_old_window_spend_does_not_trigger_defer(self):
        # Old entries exhaust window cap on paper but are outside the rolling window
        log = [_old_entry("groq", 5.0)]
        result = app.check_envelope(log, _cfg(), "groq", 0.01)
        # Total < limit (10.00), window spend = 0 → allow
        assert result == "allow"


# ---------------------------------------------------------------------------
# recommend_bucket — routing priority
# ---------------------------------------------------------------------------


class TestRecommendBucket:
    def test_prefers_spend_over_guard(self):
        # Fresh log — helix and gemini are SPEND, should win over guard buckets
        rec = app.recommend_bucket([], _cfg())
        assert rec in ("helix", "gemini")

    def test_prefers_highest_remaining_spend_bucket(self):
        # Exhaust gemini entirely; helix still has full balance
        log = [_old_entry("gemini", 50.00)]
        rec = app.recommend_bucket(log, _cfg())
        assert rec == "helix"

    def test_falls_back_to_guard_when_spend_exhausted(self):
        log = [
            _old_entry("helix", 100.00),
            _old_entry("gemini", 50.00),
        ]
        rec = app.recommend_bucket(log, _cfg())
        assert rec in ("anthropic_api", "groq")

    def test_prefers_least_used_guard(self):
        # Exhaust spend; anthropic_api has spent 10, groq has spent 1 → prefer groq (lower ratio)
        log = [
            _old_entry("helix", 100.00),
            _old_entry("gemini", 50.00),
            _old_entry("anthropic_api", 10.00),
            _old_entry("groq", 1.00),
        ]
        rec = app.recommend_bucket(log, _cfg())
        assert rec == "groq"

    def test_emergency_fallback_when_all_exhausted(self):
        # All buckets at or above limit — return the one with most remaining (least spent ratio)
        log = [
            _old_entry("helix", 100.00),
            _old_entry("gemini", 50.00),
            _old_entry("anthropic_api", 20.89),
            _old_entry("groq", 10.00),
        ]
        rec = app.recommend_bucket(log, _cfg())
        assert isinstance(rec, str)  # Must return something, not crash


# ---------------------------------------------------------------------------
# get_status — full status report
# ---------------------------------------------------------------------------


class TestGetStatus:
    def test_empty_log_all_allow(self):
        status = app.get_status([], _cfg())
        for name, info in status["buckets"].items():
            assert info["envelope"] == "allow", f"{name} should be allow on empty log"

    def test_envelope_status_ok_by_default(self):
        assert app.get_status([], _cfg())["envelope_status"] == "OK"

    def test_envelope_status_halted_when_all_denied(self):
        log = [
            _old_entry("helix", 100.00),
            _old_entry("gemini", 50.00),
            _old_entry("anthropic_api", 20.89),
            _old_entry("groq", 10.00),
        ]
        status = app.get_status(log, _cfg())
        assert status["envelope_status"] == "HALTED"

    def test_window_minutes_constant(self):
        assert app.get_status([], _cfg())["window_minutes"] == 39

    def test_envelope_spend_pct_constant(self):
        assert app.get_status([], _cfg())["envelope_spend_pct"] == 5

    def test_recommendation_present(self):
        status = app.get_status([], _cfg())
        assert "recommendation" in status
        assert status["recommendation"] in ("helix", "gemini", "anthropic_api", "groq")

    def test_helix_live_balance_injected(self):
        status = app.get_status([], _cfg(), helix_live_balance=42.50)
        assert status["buckets"]["helix"]["live_balance"] == 42.50

    def test_no_live_balance_field_when_none(self):
        status = app.get_status([], _cfg(), helix_live_balance=None)
        assert "live_balance" not in status["buckets"]["helix"]

    def test_spent_total_reflects_all_time_spend(self):
        log = [_old_entry("groq", 3.00), _recent_entry("groq", 1.00)]
        status = app.get_status(log, _cfg())
        assert status["buckets"]["groq"]["spent_total"] == pytest.approx(4.00)

    def test_remaining_computed_correctly(self):
        log = [_old_entry("groq", 3.00)]
        status = app.get_status(log, _cfg())
        assert status["buckets"]["groq"]["remaining"] == pytest.approx(7.00)

    def test_remaining_clamped_at_zero(self):
        log = [_old_entry("groq", 15.00)]  # over limit
        status = app.get_status(log, _cfg())
        assert status["buckets"]["groq"]["remaining"] == 0.0


# ---------------------------------------------------------------------------
# budget_gate — enforcement guard
# ---------------------------------------------------------------------------


class TestBudgetGate:
    def test_returns_none_when_allowed(self):
        assert app.budget_gate([], _cfg(), "anthropic_api") is None

    def test_returns_deny_dict_when_exhausted(self):
        log = [_old_entry("anthropic_api", 20.89)]
        result = app.budget_gate(log, _cfg(), "anthropic_api")
        assert result is not None
        assert result["budget_halted"] is True
        assert result["envelope"] == "deny"

    def test_deny_includes_routing_recommendation(self):
        log = [_old_entry("anthropic_api", 20.89)]
        result = app.budget_gate(log, _cfg(), "anthropic_api")
        assert "routing_recommendation" in result

    def test_defer_returns_warning_not_halted(self):
        # groq 5% cap = 0.50; spend 0.49 in window, cost 0.10 → defer
        log = [_recent_entry("groq", 0.49)]
        result = app.budget_gate(log, _cfg(), "groq", 0.10)
        assert result is not None
        assert result["budget_halted"] is False
        assert "warning" in result
        assert result["envelope"] == "defer"

    def test_deny_message_contains_bucket_name(self):
        log = [_old_entry("groq", 10.00)]
        result = app.budget_gate(log, _cfg(), "groq")
        assert "groq" in result["message"]


# ---------------------------------------------------------------------------
# _parse_request — request body deserialization
# ---------------------------------------------------------------------------


class TestParseRequest:
    def test_status_action(self):
        body = json.dumps({"action": "status"}).encode()
        assert app._parse_request(body)["action"] == "status"

    def test_check_action_with_bucket_and_cost(self):
        body = json.dumps({"action": "check", "bucket": "groq", "cost": 0.05}).encode()
        result = app._parse_request(body)
        assert result["action"] == "check"
        assert result["bucket"] == "groq"
        assert result["cost"] == pytest.approx(0.05)

    def test_default_action_is_status(self):
        assert app._parse_request(b"{}")["action"] == "status"

    def test_default_cost(self):
        assert app._parse_request(b"{}")["cost"] == pytest.approx(0.01)

    def test_none_body_uses_defaults(self):
        result = app._parse_request(None)
        assert result["action"] == "status"

    def test_malformed_json_uses_defaults(self):
        result = app._parse_request(b"not valid json {{")
        assert result["action"] == "status"


# ---------------------------------------------------------------------------
# _json_ok / _error_json — serialization helpers
# ---------------------------------------------------------------------------


class TestSerializationHelpers:
    def test_json_ok_is_bytes(self):
        assert isinstance(app._json_ok({"ok": True}), bytes)

    def test_json_ok_round_trips(self):
        data = {"envelope": "allow", "bucket": "groq"}
        assert json.loads(app._json_ok(data)) == data

    def test_error_json_structure(self):
        result = json.loads(app._error_json("something broke"))
        assert result == {"error": "something broke"}

    def test_error_json_is_bytes(self):
        assert isinstance(app._error_json("oops"), bytes)


# ---------------------------------------------------------------------------
# Spend log serialization — round-trip KV persistence
# ---------------------------------------------------------------------------


class TestSpendLogSerialization:
    def test_empty_json_returns_empty_list(self):
        assert app._load_spend_log_from_json(b"[]") == []

    def test_none_returns_empty_list(self):
        assert app._load_spend_log_from_json(None) == []

    def test_malformed_json_returns_empty_list(self):
        assert app._load_spend_log_from_json(b"not json") == []

    def test_round_trip_preserves_fields(self):
        original = [{"bucket": "groq", "cost": 1.23, "ts": "2026-04-23T10:00:00"}]
        dumped = app._dump_spend_log_to_json(original)
        loaded = app._load_spend_log_from_json(dumped)
        assert len(loaded) == 1
        assert loaded[0]["bucket"] == "groq"
        assert loaded[0]["cost"] == pytest.approx(1.23)
        assert loaded[0]["ts"] == "2026-04-23T10:00:00"

    def test_dump_converts_datetime_to_iso_string(self):
        dt = datetime(2026, 4, 23, 10, 0, 0)
        log = [{"bucket": "groq", "cost": 0.5, "ts": dt}]
        dumped = app._dump_spend_log_to_json(log)
        parsed = json.loads(dumped)
        assert isinstance(parsed[0]["ts"], str)
        assert "2026-04-23" in parsed[0]["ts"]


# ---------------------------------------------------------------------------
# make_spend_entry — entry creation
# ---------------------------------------------------------------------------


class TestMakeSpendEntry:
    def test_entry_has_required_keys(self):
        entry = app.make_spend_entry("anthropic_api", 0.05)
        assert set(entry.keys()) == {"bucket", "cost", "ts"}

    def test_bucket_and_cost_stored(self):
        entry = app.make_spend_entry("groq", 1.50)
        assert entry["bucket"] == "groq"
        assert entry["cost"] == pytest.approx(1.50)

    def test_ts_is_parseable_iso_string(self):
        entry = app.make_spend_entry("groq", 0.01)
        assert isinstance(entry["ts"], str)
        dt = datetime.fromisoformat(entry["ts"])
        # Should be within the last few seconds
        assert abs((datetime.utcnow() - dt).total_seconds()) < 5
