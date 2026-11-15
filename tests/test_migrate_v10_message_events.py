"""
scripts/migrate_v10_message_events.py and the phase 1 schema (kingdonb/mecris#363).

The shapes are contracts/message_events.json. Unit tests use a fake connection and
read files, so they need no database.

TestAgainstRealPostgres runs only when MECRIS_TEST_PG_URL points at a throwaway
Postgres on localhost (for example a postgres:18 container). It never reads
NEON_DB_URL, and it refuses any other host.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "migrate_v10_message_events.py"
SCHEMA = ROOT / "mecris-go-spin" / "schema.sql"
SYNC = ROOT / "mecris-go-spin" / "sync-service"
CONTRACT = json.loads((ROOT / "contracts" / "message_events.json").read_text())

MESSAGE_LOG_COLUMNS = {
    "client_ref": "TEXT",
    "message_sid": "TEXT",
    "delivery_status": "TEXT",
    "delivery_error": "INTEGER",
    "status_updated_at": "TIMESTAMPTZ",
}
USERS_COLUMNS = {"notifications_enabled": "BOOLEAN", "notifications_checked_at": "TIMESTAMPTZ"}


def _load():
    spec = importlib.util.spec_from_file_location("migrate_v10_message_events", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _norm(sql):
    return " ".join(sql.split())


class _FakeCursor:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=None):
        self.log.append(_norm(sql))

    def close(self):
        pass


class _FakeConn:
    def __init__(self):
        self.sql, self.commits, self.rollbacks = [], 0, 0

    def cursor(self):
        return _FakeCursor(self.sql)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def _ddl_checks(sql):
    """The phase 1 DDL, wherever it lives (the migration or schema.sql)."""
    for col, ty in MESSAGE_LOG_COLUMNS.items():
        assert re.search(rf"ALTER TABLE message_log ADD COLUMN IF NOT EXISTS {col} {ty}\b", sql), col
    for col, ty in USERS_COLUMNS.items():
        assert re.search(rf"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {ty}\b", sql), col
    assert re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS \w+ ON message_log \(user_id, client_ref\) WHERE client_ref IS NOT NULL", sql)
    assert re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS \w+ ON message_log \(message_sid\) WHERE message_sid IS NOT NULL", sql)
    assert "CREATE TABLE IF NOT EXISTS message_events" in sql
    assert "message_log_id INTEGER NOT NULL REFERENCES message_log(id) ON DELETE CASCADE" in sql
    assert "user_id VARCHAR(255) NOT NULL" in sql
    assert "event TEXT NOT NULL" in sql
    assert "at TIMESTAMPTZ NOT NULL" in sql
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT now()" in sql
    assert "UNIQUE (message_log_id, event, at)" in sql


def test_migration_adds_the_contract_schema():
    conn = _FakeConn()
    _load().migrate(conn)
    assert conn.commits == 1 and conn.rollbacks == 0
    _ddl_checks("\n".join(conn.sql))


def test_migration_is_additive_and_idempotent():
    conn = _FakeConn()
    _load().migrate(conn)
    for stmt in conn.sql:
        assert "IF NOT EXISTS" in stmt, stmt
        # The foreign key's ON DELETE CASCADE is a clause, not a delete.
        verbs = stmt.upper().replace("ON DELETE CASCADE", "")
        for verb in ("DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT"):
            assert not re.search(rf"\b{verb}\b", verbs), f"the migration must not {verb}: {stmt}"


def test_migration_rolls_back_on_error():
    mod = _load()

    class Boom(_FakeConn):
        def cursor(self):
            log = self.sql

            class C(_FakeCursor):
                def execute(self, sql, params=None):
                    if "message_events" in sql:
                        raise RuntimeError("boom")
                    log.append(sql)
            return C(log)

    conn = Boom()
    with pytest.raises(RuntimeError):
        mod.migrate(conn)
    assert conn.rollbacks == 1 and conn.commits == 0


def test_migration_reads_only_neon_db_url_and_does_nothing_without_it(monkeypatch):
    mod = _load()
    monkeypatch.delenv("NEON_DB_URL", raising=False)
    called = []
    monkeypatch.setattr(mod, "_connect", lambda url: called.append(url))
    assert mod.main() == 1
    assert called == []


def test_schema_sql_matches_the_migration():
    # CI builds its database from schema.sql, then runs every migration.
    _ddl_checks(_norm(SCHEMA.read_text()))


def test_contract_names_the_migration():
    assert "scripts/migrate_v10_message_events.py" in CONTRACT["schema"]["_doc"]
    assert set(CONTRACT["schema"]["message_log_new_columns"]) == set(MESSAGE_LOG_COLUMNS)
    assert set(CONTRACT["schema"]["users_new_columns"]) == set(USERS_COLUMNS)


# --- Spin manifests, deploy scripts and docs -------------------------------------------

@pytest.mark.parametrize("manifest", ["spin.toml", "spin.fermyon.toml"])
def test_spin_manifests_declare_the_status_callback_variable(manifest):
    toml = (SYNC / manifest).read_text()
    assert 'twilio_status_callback_url = { required = false, default = "" }' in toml
    assert 'twilio_status_callback_url = "{{ twilio_status_callback_url }}"' in toml


@pytest.mark.parametrize("script", ["deploy-akamai.sh", "deploy-fermyon.sh"])
def test_deploy_scripts_pass_the_optional_status_callback_url(script):
    sh = (SYNC / script).read_text()
    assert '--variable twilio_status_callback_url="${TWILIO_STATUS_CALLBACK_URL:-}"' in sh


def test_deployment_doc_lists_the_phase1_routes():
    doc = (ROOT / "mecris-go-spin" / "DEPLOYMENT.md").read_text()
    for needle in ("/internal/log-message-event", "/internal/twilio-status", "client_ref", "notifications_enabled",
                   "twilio_status_callback_url", "TWILIO_STATUS_CALLBACK_URL", "migrate_v10_message_events.py", "message_events"):
        assert needle in doc, needle


# --- a real, throwaway Postgres ----------------------------------------------------------

PG_URL = os.getenv("MECRIS_TEST_PG_URL")


def _local_pg_url():
    if not PG_URL:
        pytest.skip("MECRIS_TEST_PG_URL not set (throwaway local Postgres only)")
    if urlparse(PG_URL).hostname not in ("127.0.0.1", "localhost", "::1"):
        pytest.skip("MECRIS_TEST_PG_URL must point at localhost")
    return PG_URL


def _run_script(url):
    env = {k: v for k, v in os.environ.items() if k not in ("NEON_DB_URL", "DATABASE_URL")}
    env["NEON_DB_URL"] = url
    done = subprocess.run([sys.executable, str(SCRIPT)], env=env, cwd=ROOT, capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout + done.stderr


def _snapshot(cur):
    cur.execute("""SELECT table_name, column_name, data_type, is_nullable, COALESCE(column_default, '')
                   FROM information_schema.columns WHERE table_schema = 'public'
                   AND table_name IN ('users', 'message_log', 'message_events') ORDER BY 1, 2""")
    cols = cur.fetchall()
    cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1")
    idx = cur.fetchall()
    cur.execute("""SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
                   WHERE conrelid = 'message_events'::regclass ORDER BY 1""")
    return cols, idx, cur.fetchall()


@pytest.fixture
def pg():
    import psycopg2
    url = _local_pg_url()
    admin = psycopg2.connect(url)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS message_events, message_log, users CASCADE")
        # The live shape before phase 1: schema.sql's original users and message_log.
        cur.execute("CREATE TABLE users (pocket_id_sub VARCHAR(255) PRIMARY KEY, familiar_id VARCHAR(255))")
        cur.execute("""CREATE TABLE message_log (id SERIAL PRIMARY KEY,
                       user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
                       date DATE DEFAULT CURRENT_DATE, type VARCHAR(100) NOT NULL,
                       sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, content TEXT,
                       status VARCHAR(50), error_msg TEXT, channel VARCHAR(50) DEFAULT 'whatsapp')""")
        cur.execute("INSERT INTO users VALUES ('u1', 'f1'), ('u2', 'f2')")
        cur.execute("INSERT INTO message_log (user_id, type, status, channel) VALUES ('u1', 'walk_reminder', 'sent', 'whatsapp')")
    yield url, admin
    with admin.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS message_events, message_log, users CASCADE")
    admin.close()


class TestAgainstRealPostgres:
    def test_twice_and_the_second_run_changes_nothing(self, pg):
        import psycopg2
        url, admin = pg
        code, out = _run_script(url)
        assert code == 0, out
        with admin.cursor() as cur:
            first = _snapshot(cur)
            cur.execute("SELECT count(*) FROM message_log")
            assert cur.fetchone()[0] == 1, "existing rows are kept"
        code, out = _run_script(url)
        assert code == 0, out
        with admin.cursor() as cur:
            assert _snapshot(cur) == first

            # client_ref: unique per user when present; NULLs and other users are free.
            ins = "INSERT INTO message_log (user_id, type, status, channel, client_ref) VALUES (%s, 'walk_reminder', 'shown', 'android_native', %s) RETURNING id"
            cur.execute(ins, ("u1", "r-1"))
            nag = cur.fetchone()[0]
            cur.execute(ins, ("u2", "r-1"))
            cur.execute(ins, ("u1", None))
            cur.execute(ins, ("u1", None))
            with pytest.raises(psycopg2.errors.UniqueViolation):
                cur.execute(ins, ("u1", "r-1"))

            # message_sid: unique when present.
            sid = "INSERT INTO message_log (user_id, type, status, message_sid, delivery_status) VALUES ('u1', 'walk_reminder', 'sent', %s, 'queued')"
            cur.execute(sid, ("SM0123456789abcdef0123456789abcdef",))
            with pytest.raises(psycopg2.errors.UniqueViolation):
                cur.execute(sid, ("SM0123456789abcdef0123456789abcdef",))

            # message_events: (message_log_id, event, at) once; deleted with its nag.
            ev = "INSERT INTO message_events (message_log_id, user_id, event, at) VALUES (%s, 'u1', 'tapped', '2026-11-15T19:05:40Z') ON CONFLICT (message_log_id, event, at) DO NOTHING"
            cur.execute(ev, (nag,))
            assert cur.rowcount == 1
            cur.execute(ev, (nag,))
            assert cur.rowcount == 0
            cur.execute("DELETE FROM message_log WHERE id = %s", (nag,))
            cur.execute("SELECT count(*) FROM message_events")
            assert cur.fetchone()[0] == 0

            cur.execute("UPDATE users SET notifications_enabled = TRUE, notifications_checked_at = now() WHERE pocket_id_sub = 'u1'")
            assert cur.rowcount == 1
