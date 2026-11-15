"""Spin trigger-reminders gates (#368, #349, #166).

The gate logic itself is unit-tested in Rust over contracts/nag_damping_cases.json
(mecris-go-spin/sync-service/src/gates.rs). These tests check the wiring around it:
the cron-key-only endpoint, the SQL that feeds the gates (BIGINT ages, New York days,
the channel and status predicates), and a dry run that sends and writes nothing.

The live tests need the CI Spin service and its Postgres (see spin_e2e.py); the
static ones read repo files only.
"""
import re

import pytest

from spin_e2e import ROOT, cleanup_user, connect, http, http_json, internal_key, make_user, requires_spin

SYNC = ROOT / "mecris-go-spin" / "sync-service"
ALL_DAY = {"time_window_start": 0, "time_window_end": 23, "max_messages_per_day": 3}


# --- static ------------------------------------------------------------------------------

def test_ci_spin_gets_a_per_run_internal_key():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "openssl rand -hex 32" in ci, "CI must generate the internal key per run"
    m = re.search(r'--variable internal_api_key="([^"]*)"', ci)
    assert m, "spin up must receive internal_api_key"
    assert m.group(1).startswith("$"), "the key is a per-run variable, never a literal"
    assert "SPIN_INTERNAL_API_KEY" in ci and "SPIN_E2E_DB_URL" in ci, "the tests need the key and the local DB URL"
    assert "test-internal-key" not in ci


def test_spin_manifest_declares_the_standdown_variable():
    toml = (SYNC / "spin.toml").read_text()
    assert 'reminder_standdown_minutes = { required = false, default = "240" }' in toml
    assert 'reminder_standdown_minutes = "{{ reminder_standdown_minutes }}"' in toml


def test_dead_cron_component_and_hardcoded_subject_are_gone():
    lib = (SYNC / "src" / "lib.rs").read_text()
    assert "cron_component" not in lib and "handle_cron" not in lib
    assert "c0a81a4b-115a-4eb6-bc2c-40908c58bf64" not in lib, "no OIDC subject in the service code"
    assert "spin-cron-sdk" not in (SYNC / "Cargo.toml").read_text()
    assert "spin-cron-sdk" not in (SYNC / "Cargo.lock").read_text()


def test_users_timezone_is_not_read():
    # New York is hard-coded per the operator ruling; users.timezone is 'UTC' live.
    lib = (SYNC / "src" / "lib.rs").read_text()
    assert "COALESCE(timezone" not in lib
    assert "local_hour_from_timezone" not in lib


def test_deployment_doc_says_cron_key_only():
    doc = (ROOT / "mecris-go-spin" / "DEPLOYMENT.md").read_text()
    assert "signed-in user's bearer token (the Android app) or the internal key" not in doc
    assert "accept only the internal cron key" in doc
    assert "reminder_standdown_minutes" in doc


# --- live (CI Spin) ----------------------------------------------------------------------

def _dry_run_users(body):
    """Dry-run entries keyed by the subject make_user derived each familiar_id from."""
    return {u["familiar_id"].removeprefix("fam-"): u for u in body["users"] if u.get("familiar_id")}


@requires_spin
def test_signed_in_bearer_cannot_trigger_reminders():
    # CI runs with auth_bypass, so this bearer is a signed-in user.
    status, _ = http("GET", "/internal/trigger-reminders?dry_run=1", headers={"Authorization": "Bearer TestUser e2e-gates-bearer"})
    assert status == 401
    status, _ = http("POST", "/internal/failover-sync", headers={"Authorization": "Bearer TestUser e2e-gates-bearer"})
    assert status == 401


@requires_spin
def test_dry_run_explains_every_gate_and_writes_nothing():
    users = {
        "e2e-gates-eligible": dict(prefs=ALL_DAY),
        "e2e-gates-unverified": dict(prefs=ALL_DAY, phone_verified=False),
        "e2e-gates-vacation": dict(prefs=ALL_DAY, vacation_sql="now() + interval '2 days'"),
        "e2e-gates-vacation-past": dict(prefs=ALL_DAY, vacation_sql="now() - interval '2 days'"),
        "e2e-gates-type-off": dict(prefs={**ALL_DAY, "message_types": ["arabic_pressure"]}),
        "e2e-gates-phone": dict(prefs=ALL_DAY),
        "e2e-gates-phone-zero": dict(prefs=ALL_DAY),
        "e2e-gates-damped": dict(prefs=ALL_DAY),
        "e2e-gates-local-nag": dict(prefs=ALL_DAY),
        "e2e-gates-future-row": dict(prefs=ALL_DAY),
        "e2e-gates-not-nags": dict(prefs=ALL_DAY),
        "e2e-gates-old-nag": dict(prefs=ALL_DAY),
        "e2e-gates-walked": dict(prefs=ALL_DAY),
        "e2e-gates-cap-zero": dict(prefs={**ALL_DAY, "max_messages_per_day": 0}),
    }
    conn = connect()
    cur = conn.cursor()
    try:
        for uid, kw in users.items():
            make_user(cur, uid, **kw)
        log = "INSERT INTO message_log (user_id, type, sent_at, status, channel) VALUES (%s, %s, now() + %s::INTERVAL, %s, %s)"
        cur.execute("INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) VALUES ('e2e-gates-phone', 'android_client', 'e2e', now() - interval '35 minutes')")
        cur.execute(log, ("e2e-gates-damped", "walk_reminder", "-30 minutes", "failed", "whatsapp"))
        cur.execute(log, ("e2e-gates-local-nag", "arabic_pressure", "-10 minutes", "shown", "android_native"))
        cur.execute(log, ("e2e-gates-future-row", "walk_reminder", "+5 minutes", "sent", "whatsapp"))
        cur.execute(log, ("e2e-gates-not-nags", "phone_verification", "-5 minutes", "sent", "whatsapp"))
        cur.execute(log, ("e2e-gates-not-nags", "walk_ack", "-5 minutes", "received", "whatsapp"))
        cur.execute(log, ("e2e-gates-not-nags", "walk_reminder", "-5 minutes", "not_sent", "console"))
        cur.execute(log, ("e2e-gates-old-nag", "walk_reminder", "-241 minutes", "sent", "whatsapp"))
        cur.execute("""INSERT INTO walk_inferences (user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score)
                       VALUES ('e2e-gates-walked', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                               to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), '2500', '1800', 'estimated', '0.9')""")
        cur.execute("SELECT COUNT(*) FROM message_log WHERE user_id LIKE 'e2e-gates-%'")
        rows_before = cur.fetchone()[0]

        status, body, text = http_json("GET", f"/internal/trigger-reminders?dry_run=1&key={internal_key()}")
        assert status == 200, text
        assert isinstance(body, dict) and body["dry_run"] is True
        assert body["sent"] == 0 and body["failed"] == 0
        assert "e2e-gates-" not in text.replace("fam-e2e-gates-", ""), "the dry run names users by familiar_id, never by subject"
        got = _dry_run_users(body)
        want = {
            "e2e-gates-eligible": ("send", "eligible"),
            "e2e-gates-unverified": ("skip", "phone_unverified"),
            "e2e-gates-vacation": ("skip", "vacation"),
            "e2e-gates-vacation-past": ("send", "eligible"),
            "e2e-gates-type-off": ("skip", "type_disabled"),
            "e2e-gates-phone": ("stand_down", "phone_active"),
            "e2e-gates-phone-zero": ("send", "eligible"),
            "e2e-gates-damped": ("skip", "damped"),
            "e2e-gates-local-nag": ("skip", "damped"),
            "e2e-gates-future-row": ("skip", "damped"),
            "e2e-gates-not-nags": ("send", "eligible"),
            "e2e-gates-old-nag": ("send", "eligible"),
            "e2e-gates-walked": ("skip", "walked_today"),
            "e2e-gates-cap-zero": ("skip", "daily_cap"),
        }
        for uid, (verdict, reason) in want.items():
            assert uid in got, f"{uid} missing from the dry run"
            assert (got[uid]["verdict"], got[uid]["reason"]) == (verdict, reason), (uid, got[uid])
        phone = got["e2e-gates-phone"]
        assert phone["phone_heartbeat_minutes"] == 35
        assert got["e2e-gates-damped"]["minutes_since_last_nag"] == 30
        assert got["e2e-gates-old-nag"]["minutes_since_last_nag"] == 241
        assert got["e2e-gates-future-row"]["minutes_since_last_nag"] < 0
        assert got["e2e-gates-walked"]["steps"] == 2500
        assert got["e2e-gates-old-nag"]["nags_today"] in (0, 1)
        for u in got.values():
            assert re.search(r" E[SD]T$", u["ny_time"]), u["ny_time"]
            assert set(u["variables"]) == {"1", "2", "3", "4", "5"}
            assert re.fullmatch(r"\d\d:\d\d [AP]M", u["variables"]["5"])
        assert "phone_number" not in text and "pocket_id_sub" not in text

        cur.execute("SELECT COUNT(*) FROM message_log WHERE user_id LIKE 'e2e-gates-%'")
        assert cur.fetchone()[0] == rows_before, "a dry run writes no message_log row"
        cur.execute("SELECT COUNT(*) FROM scheduler_election WHERE user_id LIKE 'e2e-gates-%' AND role <> 'android_client'")
        assert cur.fetchone()[0] == 0, "a dry run records no outcome"
    finally:
        for uid in users:
            cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_daily_cap_counts_new_york_days_by_sent_at():
    conn = connect()
    cur = conn.cursor()
    cur.execute("""SELECT FLOOR(EXTRACT(EPOCH FROM now() - ((date_trunc('day', now() AT TIME ZONE 'America/New_York')) AT TIME ZONE 'America/New_York')) / 60)::BIGINT""")
    minutes_into_ny_day = cur.fetchone()[0]
    if minutes_into_ny_day < 245:
        conn.close()
        pytest.skip("needs 4 h of New York day behind it so the cap rows do not also damp")
    users = ["e2e-gates-cap-today", "e2e-gates-cap-yesterday", "e2e-gates-cap-local"]
    try:
        for uid in users:
            make_user(cur, uid, prefs=ALL_DAY)
        midnight = "(date_trunc('day', now() AT TIME ZONE 'America/New_York')) AT TIME ZONE 'America/New_York'"
        for i in range(3):
            cur.execute(f"INSERT INTO message_log (user_id, type, sent_at, status, channel, date) VALUES ('e2e-gates-cap-today', 'walk_reminder', {midnight} + interval '{i + 1} minutes', 'sent', 'whatsapp', CURRENT_DATE - 1)")
            cur.execute(f"INSERT INTO message_log (user_id, type, sent_at, status, channel, date) VALUES ('e2e-gates-cap-yesterday', 'walk_reminder', {midnight} - interval '{i + 1} minutes', 'sent', 'whatsapp', CURRENT_DATE)")
            cur.execute(f"INSERT INTO message_log (user_id, type, sent_at, status, channel) VALUES ('e2e-gates-cap-local', 'walk_reminder', {midnight} + interval '{i + 1} minutes', 'shown', 'android_native')")
        status, body, text = http_json("GET", f"/internal/trigger-reminders?dry_run=1&key={internal_key()}")
        assert status == 200, text
        got = _dry_run_users(body)
        assert (got["e2e-gates-cap-today"]["reason"], got["e2e-gates-cap-today"]["nags_today"]) == ("daily_cap", 3)
        assert (got["e2e-gates-cap-yesterday"]["reason"], got["e2e-gates-cap-yesterday"]["nags_today"]) == ("eligible", 0)
        assert (got["e2e-gates-cap-local"]["reason"], got["e2e-gates-cap-local"]["nags_today"]) == ("eligible", 0)
    finally:
        for uid in users:
            cleanup_user(cur, uid)
        conn.close()
