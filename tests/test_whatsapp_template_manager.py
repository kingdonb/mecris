"""Unit tests for WhatsAppTemplateManager in whatsapp_template_manager.py.

Covers:
- fetch_all_statuses(): list-style approval, dict-style approval,
  empty/None approval, and Twilio exception path
- get_approved_pool(): filters only approved SIDs
- sync_approved_templates(): writes correct JSON; returns approved count

Bootstrap pattern: mock twilio + dotenv in sys.modules before import,
then patch WhatsAppTemplateManager.client per-test via constructor arg.

Closes yebyen/mecris#333.
"""
import json
import os
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ── bootstrap heavy dependencies before importing the module ──────────────────
_mock_twilio = ModuleType("twilio")
_mock_twilio_rest = ModuleType("twilio.rest")
_mock_twilio_rest.Client = MagicMock()
_mock_twilio.rest = _mock_twilio_rest
sys.modules.setdefault("twilio", _mock_twilio)
sys.modules.setdefault("twilio.rest", _mock_twilio_rest)
sys.modules.setdefault("dotenv", MagicMock(load_dotenv=MagicMock()))

from whatsapp_template_manager import WhatsAppTemplateManager  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_manager(mock_client=None):
    """Return a WhatsAppTemplateManager bypassing __init__ credential check."""
    m = WhatsAppTemplateManager.__new__(WhatsAppTemplateManager)
    m.account_sid = "AC_test"
    m.auth_token = "token_test"
    m.client = mock_client or MagicMock()
    m.data_path = "data/approved_templates.json"
    return m


def _make_record(sid, status, category, approval_style="dict"):
    """Return a mock Twilio content record."""
    record = MagicMock()
    record.sid = sid
    record.friendly_name = f"Template {sid}"
    approval = {"status": status, "category": category}
    if approval_style == "list":
        record.approval_requests = [approval]
    elif approval_style == "empty":
        record.approval_requests = None
    else:
        record.approval_requests = approval
    return record


# ── TestFetchAllStatuses ──────────────────────────────────────────────────────

class TestFetchAllStatuses:
    def test_dict_approval_returned(self):
        """approval_requests is already a dict → status/category extracted directly."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.return_value = [
            _make_record("HX001", "approved", "UTILITY", "dict")
        ]
        m = _make_manager(mock_client)
        results = m.fetch_all_statuses()
        assert len(results) == 1
        assert results[0]["sid"] == "HX001"
        assert results[0]["status"] == "approved"
        assert results[0]["category"] == "UTILITY"

    def test_list_approval_uses_first_element(self):
        """approval_requests is a list → first element used as approval dict."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.return_value = [
            _make_record("HX002", "pending", "MARKETING", "list")
        ]
        m = _make_manager(mock_client)
        results = m.fetch_all_statuses()
        assert results[0]["status"] == "pending"
        assert results[0]["category"] == "MARKETING"

    def test_empty_approval_falls_back_to_unknown(self):
        """approval_requests is None/empty → status and category are 'unknown'."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.return_value = [
            _make_record("HX003", "", "", "empty")
        ]
        m = _make_manager(mock_client)
        results = m.fetch_all_statuses()
        assert results[0]["status"] == "unknown"
        assert results[0]["category"] == "unknown"

    def test_twilio_exception_returns_empty_list(self):
        """If Twilio raises any exception, fetch_all_statuses returns []."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.side_effect = RuntimeError(
            "API unavailable"
        )
        m = _make_manager(mock_client)
        results = m.fetch_all_statuses()
        assert results == []

    def test_multiple_records_returned(self):
        """All records are returned when multiple templates exist."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.return_value = [
            _make_record("HX_A", "approved", "UTILITY", "dict"),
            _make_record("HX_B", "rejected", "MARKETING", "dict"),
            _make_record("HX_C", "pending", "UTILITY", "list"),
        ]
        m = _make_manager(mock_client)
        results = m.fetch_all_statuses()
        assert len(results) == 3
        sids = [r["sid"] for r in results]
        assert "HX_A" in sids and "HX_B" in sids and "HX_C" in sids


# ── TestGetApprovedPool ───────────────────────────────────────────────────────

class TestGetApprovedPool:
    def test_only_approved_sids_returned(self):
        """get_approved_pool returns SIDs only for approved templates."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.return_value = [
            _make_record("HX_OK", "approved", "UTILITY"),
            _make_record("HX_NO", "pending", "UTILITY"),
        ]
        m = _make_manager(mock_client)
        pool = m.get_approved_pool()
        assert pool == ["HX_OK"]

    def test_empty_list_when_none_approved(self):
        """get_approved_pool returns [] when no templates are approved."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.return_value = [
            _make_record("HX_X", "rejected", "MARKETING"),
        ]
        m = _make_manager(mock_client)
        assert m.get_approved_pool() == []

    def test_empty_list_on_twilio_error(self):
        """get_approved_pool returns [] if fetch raises (via fetch_all_statuses)."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.side_effect = Exception(
            "boom"
        )
        m = _make_manager(mock_client)
        assert m.get_approved_pool() == []


# ── TestSyncApprovedTemplates ─────────────────────────────────────────────────

class TestSyncApprovedTemplates:
    def test_writes_approved_templates_to_disk(self, tmp_path):
        """sync_approved_templates writes correct JSON structure to data_path."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.return_value = [
            _make_record("HX_OK1", "approved", "UTILITY"),
            _make_record("HX_OK2", "approved", "MARKETING"),
            _make_record("HX_SKIP", "pending", "UTILITY"),
        ]
        m = _make_manager(mock_client)
        out_file = tmp_path / "approved_templates.json"
        m.data_path = str(out_file)

        count = m.sync_approved_templates()

        assert count == 2
        written = json.loads(out_file.read_text())
        assert "approved_templates" in written
        assert "HX_OK1" in written["approved_templates"]
        assert "HX_OK2" in written["approved_templates"]
        assert "HX_SKIP" not in written["approved_templates"]

    def test_returns_zero_when_no_approved(self, tmp_path):
        """sync_approved_templates returns 0 and writes empty approved dict."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.return_value = [
            _make_record("HX_X", "rejected", "MARKETING"),
        ]
        m = _make_manager(mock_client)
        m.data_path = str(tmp_path / "approved_templates.json")

        count = m.sync_approved_templates()

        assert count == 0

    def test_last_updated_field_present(self, tmp_path):
        """sync_approved_templates includes last_updated in written JSON."""
        mock_client = MagicMock()
        mock_client.content.v1.content_and_approvals.stream.return_value = []
        m = _make_manager(mock_client)
        m.data_path = str(tmp_path / "approved_templates.json")

        with patch.dict(os.environ, {"CURRENT_DATE": "2026-05-10"}):
            m.sync_approved_templates()

        written = json.loads((tmp_path / "approved_templates.json").read_text())
        assert written["last_updated"] == "2026-05-10"
