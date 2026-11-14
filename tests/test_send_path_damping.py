"""Python send path truth and shared damping (#349 Python twin, #358 slice).

- send_reminder_message stores sent_at as the database's NOW() (timezone-aware
  UTC), never a naive local datetime, and sets channel explicitly.
- A console fallback is a 'console' row with status 'not_sent', never a
  WhatsApp 'sent', and it writes nothing to stdout (the MCP stdio channel).
- Before any send, one SQL read feeds the same 4-hour any-channel damping and
  New York daily cap as Spin, over contracts/nag_damping_cases.json.
- set_notification_prefs accepts max_messages_per_day.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Load the real packages before tests/test_twilio_sender.py can stub them in
# sys.modules (it uses setdefault at collection time).
import services.auth_service  # noqa: F401
import services.encryption_service  # noqa: F401
import usage_tracker  # noqa: F401

CASES =json.loads((Path(__file__).resolve().parents[1] / "contracts" / "nag_damping_cases.json").read_text())
_ENV = {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}
BODY = "Walk Boris and Fiona: 0 steps so far"


def ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _case_inputs(case):
    merged = {**CASES["base"], **case["given"]}
    rows = [{**row, "sent_at": ts(row["sent_at"])} for row in merged["message_log"]]
    return rows, ts(merged["now"]), merged["prefs"]


GUARD_CASES = [c for c in CASES["cases"] if {"damping", "daily_cap"} & set(c["tags"])]


@pytest.fixture
def server():
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", _ENV), patch("psycopg2.connect"):
        import mcp_server
        yield mcp_server
    sys.modules.pop("mcp_server", None)


# ---------------------------------------------------------------------------
# The guard rule, over the shared contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", GUARD_CASES, ids=lambda c: c["name"])
def test_guard_matches_contract(server, case):
    rows, now, prefs = _case_inputs(case)
    assert server.nag_damping_verdict(rows, now, prefs) == case["expect"]


def test_guard_covers_every_damping_and_cap_case():
    assert len(GUARD_CASES) >= 20


def test_guard_reads_a_naive_sent_at_as_utc(server):
    # Old Python rows were written with a naive local datetime; a naive value
    # coming back must not crash the guard. It is read as UTC.
    now = ts("2026-11-14T20:00:00Z")
    row = {"type": "walk_reminder", "channel": "whatsapp", "status": "sent",
           "sent_at": datetime(2026, 11, 14, 19, 0, 0)}
    assert server.nag_damping_verdict([row], now, {}) == {"verdict": "skip", "reason": "damped"}


# ---------------------------------------------------------------------------
# send_reminder_message
# ---------------------------------------------------------------------------

def _db(guard_rows=()):
    """psycopg2.connect mock: fetchall serves the guard read; inserts are recorded."""
    cur = MagicMock()
    cur.fetchall.return_value = [(r["type"], r["channel"], r["status"], r["sent_at"]) for r in guard_rows]
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


def _inserts(cur):
    return [c for c in cur.execute.call_args_list if "INSERT INTO message_log" in c.args[0]]


async def _send(server, conn, delivery, prefs=None, message=None):
    message = message or {"type": "walk_reminder", "fallback_message": BODY}
    with patch.dict("os.environ", _ENV), patch("psycopg2.connect", return_value=conn), \
         patch.object(server, "smart_send_message", return_value=delivery) as smart, \
         patch.object(server.neon_checker, "get_notification_prefs", return_value=prefs or {}), \
         patch.object(server.usage_tracker, "resolve_user_id", return_value="test-user"), \
         patch.object(server.usage_tracker.encryption, "try_encrypt", side_effect=lambda v: v):
        result = await server.send_reminder_message(message, "test-user")
    return result, smart


@pytest.mark.asyncio
async def test_sent_at_is_database_now_and_channel_is_explicit(server):
    conn, cur = _db()
    result, _ = await _send(server, conn, {"sent": True, "method": "whatsapp_freeform"})
    assert result["sent"] is True
    (insert,) = _inserts(cur)
    sql, params = insert.args
    assert "NOW()" in sql.upper()
    assert "channel" in sql
    for value in params:
        if isinstance(value, datetime):
            assert value.tzinfo is not None and value.utcoffset().total_seconds() == 0
    assert "whatsapp" in params and "sent" in params


@pytest.mark.asyncio
async def test_failed_whatsapp_is_logged_failed_on_whatsapp(server):
    conn, cur = _db()
    await _send(server, conn, {"sent": False, "method": "whatsapp_template", "template_sid": "HX1"})
    (insert,) = _inserts(cur)
    assert "whatsapp" in insert.args[1] and "failed" in insert.args[1]


@pytest.mark.asyncio
async def test_console_fallback_is_never_a_whatsapp_send(server):
    conn, cur = _db()
    await _send(server, conn, {"sent": False, "method": "console"})
    (insert,) = _inserts(cur)
    params = insert.args[1]
    assert "console" in params and "not_sent" in params
    assert "sent" not in params and "whatsapp" not in params


async def _send_through_real_sender(server, conn, env):
    """send_reminder_message over the real smart_send_message, Twilio failing."""
    tracker = MagicMock()
    tracker.get_user_preferences.return_value = {}
    sender_globals = server.smart_send_message.__globals__
    template = MagicMock(return_value=False)
    freeform = MagicMock(return_value=False)
    with patch.dict("os.environ", {**_ENV, **env}), \
         patch("psycopg2.connect", return_value=conn), \
         patch.dict(sender_globals, {"send_whatsapp_template": template, "send_message": freeform}), \
         patch("usage_tracker.get_tracker", return_value=tracker), \
         patch("os.path.exists", return_value=False), \
         patch.object(server.neon_checker, "get_notification_prefs", return_value={}), \
         patch.object(server.usage_tracker, "resolve_user_id", return_value="test-user"), \
         patch.object(server.usage_tracker.encryption, "try_encrypt", side_effect=lambda v: v):
        result = await server.send_reminder_message(
            {"type": "walk_reminder", "fallback_message": BODY}, "test-user")
    return result, template, freeform


@pytest.mark.asyncio
@pytest.mark.parametrize("env", [
    {"REMINDER_DELIVERY_METHOD": "whatsapp", "TWILIO_WHATSAPP_TEMPLATE_SID": "HX999"},
    {"REMINDER_DELIVERY_METHOD": "whatsapp"},
], ids=["template_and_freeform_fail", "freeform_fails"])
async def test_a_failed_whatsapp_attempt_is_logged_whatsapp_failed(server, env):
    # contracts/nag_damping_cases.json: a failed WhatsApp attempt damps and
    # counts toward the cap, so it must never be logged as console/not_sent.
    conn, cur = _db()
    result, template, freeform = await _send_through_real_sender(server, conn, env)
    assert result["sent"] is False
    freeform.assert_called_once()
    (insert,) = _inserts(cur)
    params = insert.args[1]
    assert "whatsapp" in params and "failed" in params
    assert "console" not in params and "not_sent" not in params


@pytest.mark.asyncio
async def test_console_delivery_method_with_no_attempt_stays_console_not_sent(server):
    conn, cur = _db()
    result, template, freeform = await _send_through_real_sender(
        server, conn, {"REMINDER_DELIVERY_METHOD": "console"})
    assert result["sent"] is False
    template.assert_not_called()
    freeform.assert_not_called()
    (insert,) = _inserts(cur)
    params = insert.args[1]
    assert "console" in params and "not_sent" in params


@pytest.mark.asyncio
async def test_guard_blocks_within_4h_of_a_spin_whatsapp_row(server):
    recent = {"type": "walk_reminder", "channel": "whatsapp", "status": "sent",
              "sent_at": datetime.now(timezone.utc).replace(microsecond=0)}
    conn, cur = _db([recent])
    result, smart = await _send(server, conn, {"sent": True, "method": "whatsapp_freeform"})
    assert result["sent"] is False and result["reason"] == "damped"
    smart.assert_not_called()
    assert _inserts(cur) == []


@pytest.mark.asyncio
async def test_guard_blocks_within_4h_of_a_phone_nag(server):
    recent = {"type": "walk_reminder", "channel": "android_native", "status": "shown",
              "sent_at": datetime.now(timezone.utc)}
    conn, _ = _db([recent])
    result, smart = await _send(server, conn, {"sent": True, "method": "whatsapp_freeform"})
    assert result["reason"] == "damped"
    smart.assert_not_called()


@pytest.mark.asyncio
async def test_guard_blocks_at_the_daily_cap(server):
    now = datetime.now(timezone.utc)
    conn, _ = _db()
    with patch.object(server, "nag_damping_verdict", return_value={"verdict": "skip", "reason": "daily_cap"}) as v:
        result, smart = await _send(server, conn, {"sent": True, "method": "whatsapp_freeform"},
                                    prefs={"max_messages_per_day": 1})
    assert result["reason"] == "daily_cap"
    smart.assert_not_called()
    args = v.call_args.args
    assert args[2] == {"max_messages_per_day": 1}
    assert args[1].tzinfo is not None and abs((args[1] - now).total_seconds()) < 60


@pytest.mark.asyncio
async def test_guard_fails_closed_when_the_read_fails(server):
    conn, cur = _db()
    cur.fetchall.side_effect = Exception("connection reset")
    result, smart = await _send(server, conn, {"sent": True, "method": "whatsapp_freeform"})
    assert result["sent"] is False
    assert result["reason"] == "guard_unavailable"
    smart.assert_not_called()


def test_guard_reads_recent_rows_once(server):
    sql = server.NAG_GUARD_SQL
    assert "FROM message_log" in sql
    assert "user_id = %s" in sql
    assert "sent_at >" in sql  # recent rows, future-dated ones included


# ---------------------------------------------------------------------------
# Console fallback in twilio_sender
# ---------------------------------------------------------------------------

def test_console_fallback_is_not_sent_and_keeps_stdout_clean(capsys, caplog):
    import twilio_sender
    caplog.set_level(logging.DEBUG)
    tracker = MagicMock()
    tracker.get_user_preferences.return_value = {}
    with patch.dict(os.environ, {"REMINDER_DELIVERY_METHOD": "console"}, clear=False), \
         patch("usage_tracker.get_tracker", return_value=tracker), \
         patch("os.path.exists", return_value=False):
        result = twilio_sender.smart_send_message(BODY)
    assert result["sent"] is False
    assert result["method"] == "console"
    out = capsys.readouterr()
    assert out.out == ""
    assert BODY not in caplog.text


# ---------------------------------------------------------------------------
# set_notification_prefs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_notification_prefs_stores_max_messages_per_day(server):
    with patch.object(server.usage_tracker, "resolve_user_id", return_value="test-user"), \
         patch.object(server.neon_checker, "update_notification_prefs", return_value=True) as update:
        result = await server.set_notification_prefs(max_messages_per_day=2)
    assert result["status"] == "success"
    update.assert_called_once_with("test-user", {"max_messages_per_day": 2})


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [-1, 25])
async def test_set_notification_prefs_rejects_a_silly_cap(server, value):
    with patch.object(server.usage_tracker, "resolve_user_id", return_value="test-user"), \
         patch.object(server.neon_checker, "update_notification_prefs", return_value=True) as update:
        result = await server.set_notification_prefs(max_messages_per_day=value)
    assert result["status"] == "error"
    update.assert_not_called()
