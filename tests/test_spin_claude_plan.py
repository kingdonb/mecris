"""aggregate-status?full=true carries the Claude plan card, review pace and the pulse
registry (#344, #349, #346), and GET /claude-plan returns the same plan object.

- A seeded claude_plan_usage_readings row gives the summary Python's
  claude_plan_usage.summarize gives for it.
- Without the table, aggregate-status still answers 200 with claude_plan null.
- Pace lists ARABIC and GREEK; modalities carry last_status and follow pulse_roles.json.
- GET /health no longer writes a stray 'unknown' pulse row.

Live: needs the CI Spin service (see spin_e2e.py). Never reads .env.
"""
import json
from datetime import datetime, timedelta, timezone

import claude_plan_usage as cpu
from spin_e2e import ROOT, cleanup_user, connect, http_json, make_user, requires_spin

PULSE = json.loads((ROOT / "contracts" / "pulse_roles.json").read_text())


def _bearer(uid):
    return {"Authorization": f"Bearer TestUser {uid}"}


def _seed_reading(cur, uid, observed_at, windows):
    cur.execute(
        """INSERT INTO claude_plan_usage_readings (user_id, plan, verified, windows, source, observed_at, notes)
           VALUES (%s, 'ultra', false, %s::JSONB, 'manual', %s, 'private note')""",
        (uid, json.dumps(windows), observed_at),
    )


@requires_spin
def test_seeded_reading_is_available_and_matches_python():
    uid = "e2e-claude-plan"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, autonomous=False)
        now = datetime.now(timezone.utc)
        observed = (now - timedelta(minutes=30)).replace(microsecond=0)
        windows = [
            {"kind": "weekly_all", "pct_used": 62.4, "resets_at": (now + timedelta(days=2)).replace(microsecond=0).isoformat()},
            {"kind": "session", "pct_used": 20.0, "resets_at": (now + timedelta(hours=3)).replace(microsecond=0).isoformat()},
        ]
        _seed_reading(cur, uid, observed, windows)

        status, body, text = http_json("GET", "/aggregate-status?full=true", headers=_bearer(uid))
        assert status == 200, text
        plan = body["claude_plan"]
        assert plan["state"] == "available", plan
        want = cpu.summarize({"plan": "ultra", "verified": False, "source": "manual",
                              "observed_at": observed.isoformat(), "windows": windows}, now)
        for key in ("state", "reason", "stale", "summary_line", "plan", "verified", "source", "observed_at"):
            assert plan[key] == want[key], key
        assert 29 <= plan["age_minutes"] <= 31
        assert [w["kind"] for w in plan["windows"]] == ["weekly_all", "session"]
        assert all(w["fresh"] for w in plan["windows"])
        assert "private note" not in text, "the notes column is never read"

        status, same, text = http_json("GET", "/claude-plan", headers=_bearer(uid))
        assert status == 200, text
        assert same["summary_line"] == plan["summary_line"]
    finally:
        cleanup_user(cur, uid)
        cur.execute("DELETE FROM claude_plan_usage_readings WHERE user_id = %s", (uid,))
        conn.close()


@requires_spin
def test_claude_plan_is_scoped_to_the_bearer_and_needs_one():
    a, b = "e2e-claude-plan-a", "e2e-claude-plan-b"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, a, autonomous=False)
        make_user(cur, b, autonomous=False)
        now = datetime.now(timezone.utc)
        _seed_reading(cur, a, now - timedelta(minutes=5),
                      [{"kind": "weekly_all", "pct_used": 90.0, "resets_at": (now + timedelta(days=1)).isoformat()}])
        status, body, text = http_json("GET", "/aggregate-status?full=true", headers=_bearer(b))
        assert status == 200, text
        assert body["claude_plan"] is None, "another user's reading is never shown"
        status, body, text = http_json("GET", "/claude-plan", headers=_bearer(b))
        assert status == 200, text
        assert body["state"] == "unknown" and body["reason"] == "no reading recorded"
        status, _, _ = http_json("GET", "/claude-plan")
        assert status == 401
    finally:
        for uid in (a, b):
            cur.execute("DELETE FROM claude_plan_usage_readings WHERE user_id = %s", (uid,))
            cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_without_the_table_aggregate_status_still_answers():
    uid = "e2e-claude-plan-notable"
    conn = connect()
    cur = conn.cursor()
    renamed = False
    try:
        make_user(cur, uid, autonomous=False)
        cur.execute("ALTER TABLE claude_plan_usage_readings RENAME TO claude_plan_usage_readings_e2e_hidden")
        renamed = True
        status, body, text = http_json("GET", "/aggregate-status?full=true", headers=_bearer(uid))
        assert status == 200, text
        assert body["claude_plan"] is None
        assert isinstance(body["pace"], list)
    finally:
        if renamed:
            cur.execute("ALTER TABLE claude_plan_usage_readings_e2e_hidden RENAME TO claude_plan_usage_readings")
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_pace_and_pulse_follow_the_contracts():
    uid = "e2e-claude-plan-pulse"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, autonomous=False)
        cur.execute(
            """INSERT INTO language_stats (user_id, language_name, current_reviews, tomorrow_reviews, pump_multiplier,
                                           daily_completions, beeminder_due_today)
               VALUES (%s, 'ARABIC', 0, 40, 1.0, 0, 0), (%s, 'GREEK', 0, 0, 1.0, 0, 0)""",
            (uid, uid),
        )
        for role, minutes, last_status in [("android_client", 42, None), ("akamai_functions", 10, "sync 19:00Z: fresh 4m"),
                                           ("fermyon_cloud", 1, None), ("unknown", 2000, None)]:
            cur.execute(
                """INSERT INTO scheduler_election (user_id, role, process_id, heartbeat, last_status)
                   VALUES (%s, %s, 'e2e', now() - make_interval(mins => %s), %s)""",
                (uid, role, minutes, last_status),
            )
        status, body, text = http_json("GET", "/aggregate-status?full=true", headers=_bearer(uid))
        assert status == 200, text

        pace = {p["goal"]: p for p in body["pace"]}
        assert list(pace) == ["ARABIC", "GREEK"]
        assert pace["ARABIC"]["remaining"] == 40 and pace["ARABIC"]["per_hour"] > 0
        assert pace["GREEK"]["remaining"] == 0 and pace["GREEK"]["per_hour"] == 0
        assert pace["ARABIC"]["clear_by"].endswith(("-05:00", "-04:00"))

        mods = {m["role"]: m for m in body["modalities"]}
        assert mods["ANDROID CLIENT"]["status"] == "healthy", "android is healthy under 90 minutes"
        assert mods["AKAMAI FUNCTIONS"]["last_status"] == "sync 19:00Z: fresh 4m"
        assert mods["ANDROID CLIENT"]["last_status"] is None
        assert "FERMYON CLOUD" not in mods and "FERMYON" not in mods, "retired roles are hidden"
        assert "UNKNOWN" not in mods, "a day-old unlisted role is hidden"
        assert body["system_pulse"]["modalities"] == body["modalities"]
        displays = [m["role"] for m in body["modalities"]]
        assert len(displays) == len(set(displays)), "each role at most once"
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_health_check_does_not_write_an_unknown_role():
    uid = "e2e-claude-plan-health"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, autonomous=False)
        status, _, text = http_json("GET", "/health", headers=_bearer(uid))
        assert status == 200, text
        cur.execute("SELECT role FROM scheduler_election WHERE user_id = %s", (uid,))
        roles = [r[0] for r in cur.fetchall()]
        # CI runs with cloud_provider=local, which names no known cloud.
        assert "unknown" not in roles, roles
    finally:
        cleanup_user(cur, uid)
        conn.close()
