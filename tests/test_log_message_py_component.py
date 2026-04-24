"""
Tests for poc/wasm/log-message-py/app.py (yebyen/mecris#267)

Validates the pure-logic functions directly against the Python source without
the WASM runtime — componentize-py wraps the same logic for deployment.

The IncomingHandler class requires spin_sdk (only available inside the compiled
WASM component) and is NOT tested here. HTTP end-to-end validation requires
`spin test` in the deployment environment.

Covers: validate_entry, make_log_entry, append_entry, _parse_request,
        _load_log_from_json, _dump_log_to_json, _json_ok, _error_json.
"""

import importlib.util
import json
import os
from datetime import datetime

import pytest

# Load app.py by absolute path to avoid sys.modules collision
_COMPONENT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "poc", "wasm", "log-message-py")
)
_spec = importlib.util.spec_from_file_location(
    "log_message_py_app", os.path.join(_COMPONENT_DIR, "app.py")
)
app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app)


# ---------------------------------------------------------------------------
# validate_entry — field-presence checks
# ---------------------------------------------------------------------------


class TestValidateEntry:
    def test_valid_entry_returns_none(self):
        entry = {"type": "walk_reminder", "channel": "android_native"}
        assert app.validate_entry(entry) is None

    def test_missing_type_returns_error(self):
        entry = {"channel": "android_native"}
        error = app.validate_entry(entry)
        assert error is not None
        assert "type" in error

    def test_missing_channel_returns_error(self):
        entry = {"type": "walk_reminder"}
        error = app.validate_entry(entry)
        assert error is not None
        assert "channel" in error

    def test_empty_type_returns_error(self):
        entry = {"type": "", "channel": "android_native"}
        assert app.validate_entry(entry) is not None

    def test_empty_channel_returns_error(self):
        entry = {"type": "walk_reminder", "channel": ""}
        assert app.validate_entry(entry) is not None

    def test_unknown_type_accepted(self):
        # Open schema — unknown types are allowed
        entry = {"type": "new_future_type", "channel": "android_native"}
        assert app.validate_entry(entry) is None

    def test_unknown_channel_accepted(self):
        entry = {"type": "walk_reminder", "channel": "future_channel"}
        assert app.validate_entry(entry) is None


# ---------------------------------------------------------------------------
# make_log_entry — entry construction
# ---------------------------------------------------------------------------


class TestMakeLogEntry:
    def test_required_fields_present(self):
        entry = app.make_log_entry("walk_reminder", "android_native")
        assert set(entry.keys()) == {"type", "channel", "sent_at", "logged_at"}

    def test_type_and_channel_stored(self):
        entry = app.make_log_entry("arabic_pressure", "sms")
        assert entry["type"] == "arabic_pressure"
        assert entry["channel"] == "sms"

    def test_sent_at_defaults_to_logged_at_when_omitted(self):
        entry = app.make_log_entry("walk_reminder", "android_native")
        assert entry["sent_at"] == entry["logged_at"]

    def test_explicit_sent_at_preserved(self):
        sent = "2026-04-24T08:00:00"
        entry = app.make_log_entry("walk_reminder", "android_native", sent_at=sent)
        assert entry["sent_at"] == sent

    def test_logged_at_is_recent_iso_string(self):
        entry = app.make_log_entry("walk_reminder", "android_native")
        dt = datetime.fromisoformat(entry["logged_at"])
        assert abs((datetime.utcnow() - dt).total_seconds()) < 5


# ---------------------------------------------------------------------------
# append_entry — rolling log management
# ---------------------------------------------------------------------------


class TestAppendEntry:
    def _make_entry(self, entry_type="walk_reminder"):
        return app.make_log_entry(entry_type, "android_native")

    def test_entry_appended_to_empty_log(self):
        entry = self._make_entry()
        result = app.append_entry([], entry)
        assert len(result) == 1
        assert result[0]["type"] == "walk_reminder"

    def test_entry_appended_to_existing_log(self):
        existing = [self._make_entry("arabic_pressure")]
        new_entry = self._make_entry("walk_reminder")
        result = app.append_entry(existing, new_entry)
        assert len(result) == 2
        assert result[-1]["type"] == "walk_reminder"

    def test_original_log_not_mutated(self):
        original = [self._make_entry()]
        original_len = len(original)
        app.append_entry(original, self._make_entry())
        assert len(original) == original_len

    def test_rolling_cap_enforced(self):
        log = [self._make_entry() for _ in range(10)]
        new_entry = self._make_entry("greek_nag")
        result = app.append_entry(log, new_entry, max_entries=5)
        assert len(result) == 5
        assert result[-1]["type"] == "greek_nag"  # newest is kept

    def test_oldest_entries_pruned_first(self):
        log = [app.make_log_entry(f"type_{i}", "android_native") for i in range(10)]
        new_entry = app.make_log_entry("newest", "android_native")
        result = app.append_entry(log, new_entry, max_entries=5)
        types = [e["type"] for e in result]
        assert "newest" in types
        assert "type_0" not in types  # oldest pruned

    def test_cap_of_one_keeps_only_newest(self):
        log = [self._make_entry("old")]
        new_entry = self._make_entry("new")
        result = app.append_entry(log, new_entry, max_entries=1)
        assert len(result) == 1
        assert result[0]["type"] == "new"


# ---------------------------------------------------------------------------
# _parse_request — request body deserialization
# ---------------------------------------------------------------------------


class TestParseRequest:
    def test_parses_all_fields(self):
        body = json.dumps({
            "type": "walk_reminder",
            "channel": "android_native",
            "sent_at": "2026-04-24T08:00:00",
        }).encode()
        result = app._parse_request(body)
        assert result["type"] == "walk_reminder"
        assert result["channel"] == "android_native"
        assert result["sent_at"] == "2026-04-24T08:00:00"

    def test_missing_sent_at_returns_none(self):
        body = json.dumps({"type": "walk_reminder", "channel": "android_native"}).encode()
        result = app._parse_request(body)
        assert result["sent_at"] is None

    def test_empty_sent_at_returns_none(self):
        body = json.dumps({"type": "walk_reminder", "channel": "android_native", "sent_at": ""}).encode()
        result = app._parse_request(body)
        assert result["sent_at"] is None

    def test_missing_fields_default_to_empty_string(self):
        result = app._parse_request(b"{}")
        assert result["type"] == ""
        assert result["channel"] == ""

    def test_none_body_uses_defaults(self):
        result = app._parse_request(None)
        assert result["type"] == ""

    def test_malformed_json_uses_defaults(self):
        result = app._parse_request(b"not valid json {{")
        assert result["type"] == ""


# ---------------------------------------------------------------------------
# _json_ok / _error_json — serialization helpers
# ---------------------------------------------------------------------------


class TestSerializationHelpers:
    def test_json_ok_is_bytes(self):
        assert isinstance(app._json_ok({"ok": True}), bytes)

    def test_json_ok_round_trips(self):
        data = {"logged": True, "entry_count": 5}
        assert json.loads(app._json_ok(data)) == data

    def test_error_json_structure(self):
        result = json.loads(app._error_json("something broke"))
        assert result == {"error": "something broke"}

    def test_error_json_is_bytes(self):
        assert isinstance(app._error_json("oops"), bytes)


# ---------------------------------------------------------------------------
# _load_log_from_json / _dump_log_to_json — KV persistence round-trip
# ---------------------------------------------------------------------------


class TestLogSerialization:
    def _sample_entry(self, entry_type="walk_reminder"):
        return app.make_log_entry(entry_type, "android_native")

    def test_empty_bytes_returns_empty_list(self):
        assert app._load_log_from_json(b"[]") == []

    def test_none_returns_empty_list(self):
        assert app._load_log_from_json(None) == []

    def test_malformed_json_returns_empty_list(self):
        assert app._load_log_from_json(b"not json") == []

    def test_non_list_json_returns_empty_list(self):
        assert app._load_log_from_json(b'{"key": "value"}') == []

    def test_round_trip_preserves_entry(self):
        entry = self._sample_entry("arabic_pressure")
        log = [entry]
        dumped = app._dump_log_to_json(log)
        loaded = app._load_log_from_json(dumped)
        assert len(loaded) == 1
        assert loaded[0]["type"] == "arabic_pressure"
        assert loaded[0]["channel"] == "android_native"

    def test_round_trip_preserves_sent_at(self):
        entry = app.make_log_entry("walk_reminder", "android_native", "2026-04-24T08:30:00")
        dumped = app._dump_log_to_json([entry])
        loaded = app._load_log_from_json(dumped)
        assert loaded[0]["sent_at"] == "2026-04-24T08:30:00"

    def test_dump_produces_bytes(self):
        assert isinstance(app._dump_log_to_json([]), bytes)

    def test_multiple_entries_round_trip(self):
        log = [self._sample_entry(f"type_{i}") for i in range(5)]
        dumped = app._dump_log_to_json(log)
        loaded = app._load_log_from_json(dumped)
        assert len(loaded) == 5
        types = [e["type"] for e in loaded]
        for i in range(5):
            assert f"type_{i}" in types


# ---------------------------------------------------------------------------
# Integration-style: validate → make → append → dump → load round-trip
# ---------------------------------------------------------------------------


class TestEndToEndLogic:
    def test_full_flow_walk_reminder(self):
        """Simulate the happy-path POST handling without WASM runtime."""
        body = json.dumps({
            "type": "walk_reminder",
            "channel": "android_native",
            "sent_at": "2026-04-24T10:00:00",
        }).encode()

        params = app._parse_request(body)
        error = app.validate_entry(params)
        assert error is None

        entry = app.make_log_entry(params["type"], params["channel"], params["sent_at"])
        log = app.append_entry([], entry)
        raw = app._dump_log_to_json(log)
        reloaded = app._load_log_from_json(raw)

        assert len(reloaded) == 1
        assert reloaded[0]["type"] == "walk_reminder"
        assert reloaded[0]["sent_at"] == "2026-04-24T10:00:00"

    def test_full_flow_arabic_pressure(self):
        body = json.dumps({
            "type": "arabic_pressure",
            "channel": "android_native",
        }).encode()

        params = app._parse_request(body)
        assert app.validate_entry(params) is None

        entry = app.make_log_entry(params["type"], params["channel"], params["sent_at"])
        # sent_at defaults to logged_at
        assert entry["sent_at"] == entry["logged_at"]

    def test_invalid_request_rejected_before_storage(self):
        body = json.dumps({"channel": "android_native"}).encode()  # missing type
        params = app._parse_request(body)
        error = app.validate_entry(params)
        assert error is not None
        # If error is not None, no entry should be created/stored

    def test_rolling_cap_across_many_notifications(self):
        log = []
        for i in range(1005):
            entry = app.make_log_entry("walk_reminder", "android_native")
            log = app.append_entry(log, entry)
        assert len(log) == 1000  # capped at _MAX_LOG_ENTRIES
