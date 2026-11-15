"""Offline tests for scripts/fetch_template_bodies.py (#363 step 1).

The fetcher reads approved WhatsApp template bodies from the Twilio Content
API (read-only GETs) and writes data/templates/<name>.json. These tests use a
fake HTTP getter, so they need no .env, no credentials and no network.
"""
import json

import pytest

from scripts.fetch_template_bodies import (
    CONTENT_HOST,
    catalog_problems,
    fetch_all,
    load_approved,
    placeholders,
)

STATUS_SID = "HX" + "a" * 32
BRIEF_SID = "HX" + "b" * 32

CONTENT = {
    STATUS_SID: {
        "sid": STATUS_SID,
        "account_sid": "AC" + "0" * 32,
        "friendly_name": "mecris_status_v2",
        "language": "en",
        "variables": {"1": "Daily Walk", "2": "NOT FOUND", "3": "Boris & Fiona", "4": "EXPECTANT", "5": "04:00 PM"},
        "types": {"twilio/text": {"body": "{{1}} is currently {{2}}. {{3}} is {{4}}. Review {{5}}."}},
    },
    BRIEF_SID: {
        "sid": BRIEF_SID,
        "account_sid": "AC" + "0" * 32,
        "friendly_name": "mecris_daily_briefing_v2",
        "language": "en",
        "variables": {"1": "x"},
        "types": {"twilio/quick-reply": {"body": "Briefing: {{1}}", "actions": [{"title": "OK", "id": "ok"}]}},
    },
}
APPROVALS = {
    STATUS_SID: {"sid": STATUS_SID, "whatsapp": {"category": "UTILITY", "status": "approved", "name": "mecris_status_v2", "rejection_reason": ""}},
    BRIEF_SID: {"sid": BRIEF_SID, "whatsapp": {"category": "UTILITY", "status": "approved", "name": "mecris_daily_briefing_v2", "rejection_reason": ""}},
}


class FakeGet:
    """Stands in for the Twilio HTTP client; records every URL it is asked for."""

    def __init__(self, content=CONTENT, approvals=APPROVALS, fail=None):
        self.content, self.approvals, self.fail = content, approvals, fail or {}
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        for sid, status in self.fail.items():
            if sid in url:
                return status, {"message": "nope"}
        for sid in self.content:
            if url.endswith(f"/Content/{sid}"):
                return 200, self.content[sid]
            if url.endswith(f"/Content/{sid}/ApprovalRequests"):
                return 200, self.approvals[sid]
        return 404, {}


def _approved_file(tmp_path, mapping):
    path = tmp_path / "approved_templates.json"
    path.write_text(json.dumps({"approved_templates": mapping, "last_updated": "unknown"}))
    return path


def test_placeholders_are_unique_and_sorted():
    assert placeholders("{{2}} and {{1}} then {{2}} and {{10}}") == [1, 2, 10]
    assert placeholders("no slots") == []


def test_load_approved_maps_sid_to_name(tmp_path):
    path = _approved_file(tmp_path, {STATUS_SID: "mecris_status_v2"})
    assert load_approved(path) == {STATUS_SID: "mecris_status_v2"}


def test_fetch_all_writes_one_body_file_per_template(tmp_path):
    out = tmp_path / "templates"
    get = FakeGet()
    written, failures = fetch_all({STATUS_SID: "mecris_status_v2", BRIEF_SID: "mecris_daily_briefing_v2"}, get, out)

    assert failures == []
    assert sorted(p.name for p in written) == ["mecris_daily_briefing_v2.json", "mecris_status_v2.json"]
    record = json.loads((out / "mecris_status_v2.json").read_text())
    assert record["sid"] == STATUS_SID
    assert record["name"] == "mecris_status_v2"
    assert record["body"] == "{{1}} is currently {{2}}. {{3}} is {{4}}. Review {{5}}."
    assert record["placeholders"] == [1, 2, 3, 4, 5]
    assert record["category"] == "UTILITY"
    assert record["approval_status"] == "approved"
    assert record["language"] == "en"
    assert record["variables"]["5"] == "04:00 PM"
    assert "account_sid" not in json.dumps(record)


def test_quick_reply_body_is_used_when_there_is_no_text_type(tmp_path):
    out = tmp_path / "templates"
    fetch_all({BRIEF_SID: "mecris_daily_briefing_v2"}, FakeGet(), out)
    record = json.loads((out / "mecris_daily_briefing_v2.json").read_text())
    assert record["body"] == "Briefing: {{1}}"
    assert record["types"]["twilio/quick-reply"]["body"] == "Briefing: {{1}}"


def test_only_reads_from_the_content_api(tmp_path):
    get = FakeGet()
    fetch_all({STATUS_SID: "mecris_status_v2"}, get, tmp_path / "templates")
    assert get.urls, "expected at least one request"
    assert all(u.startswith(f"https://{CONTENT_HOST}/v1/Content/") for u in get.urls)


def test_failures_report_sid_and_status_only_and_write_nothing(tmp_path):
    out = tmp_path / "templates"
    written, failures = fetch_all({STATUS_SID: "mecris_status_v2"}, FakeGet(fail={STATUS_SID: 401}), out)
    assert written == []
    assert failures == [(STATUS_SID, 401)]
    assert not (out / "mecris_status_v2.json").exists()


def test_dry_run_writes_nothing(tmp_path):
    out = tmp_path / "templates"
    written, failures = fetch_all({STATUS_SID: "mecris_status_v2"}, FakeGet(), out, dry_run=True)
    assert failures == []
    assert not out.exists()


def test_unsafe_template_names_are_refused(tmp_path):
    out = tmp_path / "templates"
    written, failures = fetch_all({STATUS_SID: "../escape"}, FakeGet(), out)
    assert written == []
    assert failures == [(STATUS_SID, "bad-name")]
    assert not (tmp_path / "escape.json").exists()


def test_catalog_problems_flags_missing_bodies_and_slot_mismatch(tmp_path):
    approved = _approved_file(tmp_path, {STATUS_SID: "mecris_status_v2", BRIEF_SID: "mecris_daily_briefing_v2"})
    out = tmp_path / "templates"
    out.mkdir()
    (out / "mecris_status_v2.json").write_text(json.dumps({"sid": STATUS_SID, "body": "{{1}} {{2}}", "placeholders": [1, 2]}))

    problems = catalog_problems(approved, out)
    assert any("mecris_daily_briefing_v2" in p and "missing" in p for p in problems)
    assert any("mecris_status_v2" in p and "5" in p for p in problems)


def test_catalog_problems_empty_for_a_complete_catalog(tmp_path):
    approved = _approved_file(tmp_path, {STATUS_SID: "mecris_status_v2", BRIEF_SID: "mecris_daily_briefing_v2"})
    out = tmp_path / "templates"
    fetch_all(load_approved(approved), FakeGet(), out)
    assert catalog_problems(approved, out) == []
