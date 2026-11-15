"""Plumbing for tests that drive the CI Spin service and its local Postgres.

The live tests run only when CI provides SPIN_INTERNAL_API_KEY (a per-run key) and
SPIN_E2E_DB_URL pointing at localhost. They never read .env and never reach a
database or service off this machine. Users they create are named e2e-* and removed
afterwards. Requests use urllib so conftest's mocked `requests` does not apply.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("SPIN_BASE_URL", "http://127.0.0.1:3000")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def e2e_config():
    key = os.environ.get("SPIN_INTERNAL_API_KEY", "")
    db_url = os.environ.get("SPIN_E2E_DB_URL", "")
    if not key or not db_url:
        return None
    if urlparse(db_url).hostname not in LOCAL_HOSTS or urlparse(BASE).hostname not in LOCAL_HOSTS:
        return None
    return key, db_url


requires_spin = pytest.mark.skipif(
    e2e_config() is None,
    reason="needs the CI Spin service: SPIN_INTERNAL_API_KEY and a localhost SPIN_E2E_DB_URL",
)


def internal_key():
    return e2e_config()[0]


def http(method, path, headers=None, body=None, timeout=90):
    """(status, text) for a request to the Spin service; HTTP errors are returned, not raised."""
    data = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def http_json(method, path, **kw):
    status, text = http(method, path, **kw)
    try:
        return status, json.loads(text), text
    except ValueError:
        return status, None, text


def connect():
    import psycopg2
    conn = psycopg2.connect(e2e_config()[1])
    conn.autocommit = True
    return conn


def familiar(uid):
    """The familiar_id make_user gives a user: never equal to its subject, so a test can
    tell which one a response printed."""
    return "fam-" + uid


def make_user(cur, uid, *, phone_verified=True, prefs=None, autonomous=True, phone_enc="00" * 28, vacation_sql="NULL"):
    """A user eligible for the cron loop unless told otherwise. phone_enc is never decrypted by a dry run."""
    cleanup_user(cur, uid)
    cur.execute(
        f"""INSERT INTO users (pocket_id_sub, familiar_id, beeminder_goal, phone_number_encrypted, phone_verified,
                               notification_prefs, autonomous_sync_enabled, vacation_mode_until)
            VALUES (%s, %s, 'bike', %s, %s, %s::JSONB, %s, {vacation_sql})""",
        (uid, familiar(uid), phone_enc, phone_verified, json.dumps(prefs if prefs is not None else {}), autonomous),
    )


def cleanup_user(cur, uid):
    for table in ("message_log", "scheduler_election", "language_stats", "walk_inferences", "phone_verifications"):
        cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (uid,))
    cur.execute("DELETE FROM users WHERE pocket_id_sub = %s", (uid,))


def refusal_count(cur, endpoint, reason):
    cur.execute(
        """SELECT COALESCE(SUM(count), 0) FROM internal_refusals
           WHERE day = (now() AT TIME ZONE 'America/New_York')::DATE AND endpoint = %s AND reason = %s""",
        (endpoint, reason),
    )
    return int(cur.fetchone()[0])
