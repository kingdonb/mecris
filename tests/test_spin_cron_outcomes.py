"""Every cron run and every refusal leaves state (#183, #245), and the cloud owns
periodic language sync (#183 failover-sync).

Static checks read the scripts and docs; the verify script runs against a fake curl
and a fake Neon reader, so nothing leaves this machine. Live checks need the CI Spin
service (see spin_e2e.py).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from spin_e2e import ROOT, cleanup_user, connect, http, http_json, internal_key, make_user, refusal_count, requires_spin

ALL_DAY = {"time_window_start": 0, "time_window_end": 23, "max_messages_per_day": 3}
VERIFY = ROOT / "scripts" / "verify_spin_deploy.sh"
MIGRATION = ROOT / "scripts" / "migrate_v9_cloud_observability.py"


# --- cron schedule ---------------------------------------------------------------------

def test_one_failover_job_every_two_hours():
    cron = (ROOT / "scripts" / "setup_spin_cron.sh").read_text()
    creates = re.findall(r'--schedule "([^"]+)"\s*\\\s*\n\s*--name "([^"]+)"', cron)
    assert ("0 */2 * * *", "trigger-reminders") in creates
    assert ("5 */2 * * *", "failover-sync") in creates
    assert not any(name.startswith("failover-sync-") for _, name in creates), "the edt/est jobs are replaced"


# --- schema and migration --------------------------------------------------------------

def test_schema_catches_up_with_live_tables():
    schema = (ROOT / "mecris-go-spin" / "schema.sql").read_text()
    for col in ("last_status", "last_error", "intent"):
        assert re.search(rf"\b{col}\b", schema), col
    assert "CREATE TABLE IF NOT EXISTS internal_refusals" in schema
    assert "PRIMARY KEY (day, endpoint, reason)" in schema
    assert "CREATE TABLE IF NOT EXISTS claude_plan_usage_readings" in schema


class _FakeCursor:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=None):
        self.log.append(" ".join(sql.split()))

    def close(self):
        pass


class _FakeConn:
    def __init__(self):
        self.sql, self.commits = [], 0

    def cursor(self):
        return _FakeCursor(self.sql)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


def _load_migration():
    spec = importlib.util.spec_from_file_location("migrate_v9_cloud_observability", MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_is_additive_and_idempotent():
    mod = _load_migration()
    conn = _FakeConn()
    mod.migrate(conn)
    sql = "\n".join(conn.sql)
    assert conn.commits == 1
    assert "CREATE TABLE IF NOT EXISTS internal_refusals" in sql
    assert "PRIMARY KEY (day, endpoint, reason)" in sql
    for col in ("last_status", "last_error", "intent"):
        assert f"ADD COLUMN IF NOT EXISTS {col}" in sql
    for verb in ("DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT"):
        assert not re.search(rf"\b{verb}\b", sql.upper()), f"the migration must not {verb}"
    for stmt in conn.sql:
        assert "IF NOT EXISTS" in stmt, stmt


def test_migration_reads_only_neon_db_url_and_does_nothing_without_it(monkeypatch):
    mod = _load_migration()
    monkeypatch.delenv("NEON_DB_URL", raising=False)
    called = []
    monkeypatch.setattr(mod, "_connect", lambda url: called.append(url))
    assert mod.main() == 1
    assert called == []


# --- docs --------------------------------------------------------------------------------

def test_deployment_doc_puts_outcomes_in_scheduler_election():
    doc = (ROOT / "mecris-go-spin" / "DEPLOYMENT.md").read_text()
    assert "stand-down rationale directly to Neon Postgres (`message_log` table)" not in doc
    assert "scheduler_election.last_status" in doc
    assert "internal_refusals" in doc


# --- verify_spin_deploy.sh against fakes ---------------------------------------------------

GOOD_KEY = "k" * 64

FAKE_CURL = r'''#!@PYTHON@
import json, os, sys
from urllib.parse import urlparse, parse_qs
args = sys.argv[1:]
url, out, fmt, stdin_cfg, i = None, None, "", None, 0
while i < len(args):
    a = args[i]
    if a in ("-o", "-w", "-m", "-H", "-X", "-d", "-K"):
        v = args[i + 1]
        if a == "-o": out = v
        if a == "-w": fmt = v
        if a == "-K" and v == "-":
            stdin_cfg = sys.stdin.read()
            for line in stdin_cfg.splitlines():
                if line.startswith("url = "): url = json.loads(line[6:])
        i += 2
        continue
    if not a.startswith("-"): url = a
    i += 1
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"argv": args, "url": url, "via_stdin": stdin_cfg is not None}) + "\n")
u = urlparse(url); q = parse_qs(u.query); key = q.get("key", [None])[0]
good = key == os.environ["FAKE_GOOD_KEY"]
if u.path == "/version": code, body = 200, json.dumps({"version": os.environ["FAKE_VERSION"], "cloud_provider": "akamai"})
elif u.path == "/internal/trigger-reminders" and good and q.get("dry_run") == ["1"]:
    code, body = 200, json.dumps({"sent": 0, "failed": 0, "stood_down": 0, "reasons": {"outside_window": 1}, "dry_run": True,
        "users": [{"familiar_id": "someone", "ny_time": "2026-11-14 15:00 EST", "verdict": "skip", "reason": "outside_window"}]})
elif u.path == "/internal/trigger-reminders" and good: code, body = 200, json.dumps({"sent": 0, "failed": 0, "stood_down": 1, "reasons": {}})
elif u.path == "/internal/failover-sync" and good: code, body = 200, json.dumps({"status": "success", "scraped": 0, "failed": 0, "fresh": 1})
elif u.path == "/internal/twilio-webhook": code, body = 403, "Forbidden"
else: code, body = 401, "Unauthorized"
if out != "/dev/null": sys.stdout.write(body)
sys.stdout.write(fmt.replace("%{http_code}", str(code)))
'''

# Stands in for the read-only Neon reader: `$MECRIS_PYTHON - <query> [args]` with SQL on stdin.
# Refusal counts read 0 the first time and 3 after; anything else runs the real python.
FAKE_PY = r'''#!/usr/bin/env bash
if [[ "${1:-}" == "-" ]]; then
  cat >/dev/null
  echo "$*" >> "$FAKE_NEON_LOG"
  case "$2" in
    now) echo 1000 ;;
    refusals) f="$FAKE_STATE/$3-$4"; if [[ -f "$f" ]]; then echo 3; else touch "$f"; echo 0; fi ;;
    cron_rows_since) echo "${FAKE_CRON_ROWS:-1}" ;;
    last_status) echo "reminders 20:00Z: skipped (outside window); sync 20:05Z: fresh 40m" ;;
    *) echo "unknown query $2" >&2; exit 3 ;;
  esac
  exit 0
fi
exec "@PYTHON@" "$@"
'''


def _run_verify(tmp_path, *args, cron_rows="1"):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "curl").write_text(FAKE_CURL.replace("@PYTHON@", sys.executable))
    (bin_dir / "fakepy").write_text(FAKE_PY.replace("@PYTHON@", sys.executable))
    for f in ("curl", "fakepy"):
        (bin_dir / f).chmod(0o755)
    (tmp_path / "state").mkdir(exist_ok=True)
    env_file = tmp_path / "env"
    env_file.write_text(f"INTERNAL_API_KEY={GOOD_KEY}\nNEON_DB_URL=postgresql://fake.invalid/db\n")
    version = re.search(r'^version = "(.*)"', (ROOT / "mecris-go-spin/sync-service/spin.toml").read_text(), re.M).group(1)
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "SPIN_BASE_URL": "https://spin.fake.invalid",
        "MECRIS_ENV_FILE": str(env_file),
        "MECRIS_PYTHON": str(bin_dir / "fakepy"),
        "FAKE_LOG": str(tmp_path / "curl.log"),
        "FAKE_NEON_LOG": str(tmp_path / "neon.log"),
        "FAKE_STATE": str(tmp_path / "state"),
        "FAKE_GOOD_KEY": GOOD_KEY,
        "FAKE_VERSION": version,
        "FAKE_CRON_ROWS": cron_rows,
    }
    proc = subprocess.run(["bash", str(VERIFY), *args], env=env, capture_output=True, text=True, timeout=120)
    calls = [json.loads(line) for line in (tmp_path / "curl.log").read_text().splitlines()] if (tmp_path / "curl.log").exists() else []
    return proc, calls


def _keyed(calls):
    return [c for c in calls if c["url"] and f"key={GOOD_KEY}" in c["url"]]


def test_verify_defaults_to_a_dry_run_and_keeps_the_key_off_the_command_line(tmp_path):
    proc, calls = _run_verify(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "All checks passed" in proc.stdout
    assert GOOD_KEY not in proc.stdout + proc.stderr, "the key is never printed"
    for c in calls:
        assert all(GOOD_KEY not in a for a in c["argv"]), "the key travels on stdin (curl -K -), never in argv"
    keyed = _keyed(calls)
    assert keyed and all(c["via_stdin"] for c in keyed)
    triggers = [c["url"] for c in keyed if "/internal/trigger-reminders" in c["url"]]
    assert triggers and all("dry_run=1" in u for u in triggers), "no real trigger without --live-trigger"
    assert any("/internal/failover-sync" in c["url"] for c in keyed), "a cron-shaped failover-sync request"
    neon = (tmp_path / "neon.log").read_text()
    assert "cron_rows_since" in neon and "last_status" in neon
    assert "refusals trigger-reminders burned_key" in neon
    assert "America/New_York" in proc.stdout or "EST" in proc.stdout


def test_verify_sends_a_real_trigger_only_when_asked(tmp_path):
    proc, calls = _run_verify(tmp_path, "--live-trigger")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    triggers = [c["url"] for c in _keyed(calls) if "/internal/trigger-reminders" in c["url"]]
    assert any("dry_run=1" not in u for u in triggers)


def test_verify_fails_when_the_cron_run_leaves_no_heartbeat(tmp_path):
    proc, _ = _run_verify(tmp_path, cron_rows="0")
    assert proc.returncode == 1
    assert "FAIL" in proc.stdout


def test_verify_script_documents_its_modes():
    text = VERIFY.read_text()
    assert "--live-trigger" in text and "curl" in text and "-K -" in text
    assert 'TRIGGER=1' not in text, "the real trigger is no longer the default"


# --- live (CI Spin) ----------------------------------------------------------------------

@requires_spin
def test_cron_run_records_a_stand_down_in_last_status():
    uid = "e2e-cron-standdown"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, prefs=ALL_DAY)
        cur.execute("INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) VALUES (%s, 'android_client', 'e2e', now() - interval '35 minutes')", (uid,))
        cur.execute("SELECT now()")
        t0 = cur.fetchone()[0]
        status, body, text = http_json("GET", f"/internal/trigger-reminders?key={internal_key()}")
        assert status == 200, text
        assert isinstance(body, dict) and {"sent", "failed", "stood_down", "reasons"} <= set(body)
        assert body["stood_down"] >= 1 and body["reasons"].get("phone_active", 0) >= 1
        cur.execute("SELECT last_status, intent, last_error, heartbeat FROM scheduler_election WHERE user_id = %s AND role <> 'android_client'", (uid,))
        rows = cur.fetchall()
        assert len(rows) == 1, rows
        last_status, intent, last_error, heartbeat = rows[0]
        assert "stood down (android active 35m)" in last_status
        assert last_status.startswith("reminders ")
        assert intent == "cron" and last_error is None and heartbeat >= t0
        cur.execute("SELECT COUNT(*) FROM message_log WHERE user_id = %s", (uid,))
        assert cur.fetchone()[0] == 0, "a stand-down is never a message_log row"
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_refusals_are_counted_per_new_york_day():
    conn = connect()
    cur = conn.cursor()
    try:
        before = {r: refusal_count(cur, "trigger-reminders", r) for r in ("bad_key", "burned_key", "no_key")}
        before_sync = refusal_count(cur, "failover-sync", "no_key")
        assert http("GET", "/internal/trigger-reminders?key=not-the-key")[0] == 401
        assert http("GET", "/internal/trigger-reminders?key=test-internal-key")[0] == 401
        assert http("GET", "/internal/trigger-reminders", headers={"x-internal-api-key": "test-internal-key"})[0] == 401
        assert http("GET", "/internal/trigger-reminders")[0] == 401
        assert http("GET", "/internal/failover-sync")[0] == 401
        assert refusal_count(cur, "trigger-reminders", "bad_key") == before["bad_key"] + 1
        assert refusal_count(cur, "trigger-reminders", "burned_key") == before["burned_key"] + 2
        assert refusal_count(cur, "trigger-reminders", "no_key") == before["no_key"] + 1
        assert refusal_count(cur, "failover-sync", "no_key") == before_sync + 1
        cur.execute("SELECT COUNT(*) FROM internal_refusals WHERE day = (now() AT TIME ZONE 'America/New_York')::DATE AND endpoint = 'trigger-reminders' AND reason = 'burned_key'")
        assert cur.fetchone()[0] == 1, "one row per day, endpoint and reason"
    finally:
        conn.close()


@requires_spin
def test_failover_sync_stands_down_on_fresh_stats_and_keeps_both_segments():
    uid = "e2e-cron-fresh"
    conn = connect()
    cur = conn.cursor()
    try:
        make_user(cur, uid, prefs=ALL_DAY)
        cur.execute("INSERT INTO scheduler_election (user_id, role, process_id, heartbeat) VALUES (%s, 'android_client', 'e2e', now() - interval '35 minutes')", (uid,))
        cur.execute("INSERT INTO language_stats (user_id, language_name, current_reviews, last_updated) VALUES (%s, 'ARABIC', 7, now())", (uid,))
        cur.execute("SELECT last_updated FROM language_stats WHERE user_id = %s", (uid,))
        updated_before = cur.fetchone()[0]
        assert http("GET", f"/internal/trigger-reminders?key={internal_key()}")[0] == 200
        status, body, text = http_json("GET", f"/internal/failover-sync?key={internal_key()}")
        assert status == 200, text
        assert isinstance(body, dict) and body.get("fresh", 0) >= 1
        cur.execute("SELECT last_status FROM scheduler_election WHERE user_id = %s AND role <> 'android_client'", (uid,))
        last_status = cur.fetchone()[0]
        assert re.search(r"^reminders \d\d:\d\dZ: stood down \(android active 35m\); sync \d\d:\d\dZ: fresh 0m$", last_status), last_status
        assert len(last_status) <= 255
        cur.execute("SELECT last_updated FROM language_stats WHERE user_id = %s", (uid,))
        assert cur.fetchone()[0] == updated_before, "fresh stats are not scraped"
        cur.execute("SELECT last_autonomous_sync FROM users WHERE pocket_id_sub = %s", (uid,))
        assert cur.fetchone()[0] is None
    finally:
        cleanup_user(cur, uid)
        conn.close()


@requires_spin
def test_migration_runs_twice_on_the_ci_database(monkeypatch):
    mod = _load_migration()
    monkeypatch.setenv("NEON_DB_URL", os.environ["SPIN_E2E_DB_URL"])
    assert mod.main() == 0
    assert mod.main() == 0
