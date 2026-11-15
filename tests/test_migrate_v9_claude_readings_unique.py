"""
scripts/migrate_v9_claude_readings_unique.py and the race it closes (kingdonb/mecris#344).

Unit tests use a fake connection, so they need no database.

TestAgainstRealPostgres runs only when MECRIS_TEST_PG_URL points at a throwaway
Postgres on localhost (for example a postgres:18 container). It never reads
NEON_DB_URL, and it refuses any other host.
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

import claude_plan_usage as cpu
from scripts import migrate_v9_claude_readings_unique as mig

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "migrate_v9_claude_readings_unique.py"


def _norm(sql):
    return " ".join(sql.split()).upper()


class FakeConn:
    """Answers the migration's queries from fixed values and records every statement."""

    def __init__(self, version=170012, table=True, index=False, duplicates=0):
        self.version, self.table, self.index, self.duplicates = version, table, index, duplicates
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        conn = self

        class Cursor:
            result = None
            rowcount = -1

            def execute(self, sql, params=None):
                text = _norm(sql)
                conn.statements.append((text, params))
                if "SERVER_VERSION_NUM" in text:
                    self.result = (conn.version,)
                elif text.startswith("SELECT TO_REGCLASS"):
                    name = params[0] if params else None
                    self.result = (conn.index if name == mig.INDEX else conn.table,)
                elif text.startswith("SELECT COUNT(*)"):
                    self.result = (conn.duplicates,)
                elif text.startswith("DELETE"):
                    self.rowcount = conn.duplicates

            def fetchone(self):
                return self.result

            def close(self):
                pass

        return Cursor()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True

    def writes(self):
        return [s for s, _ in self.statements
                if s.startswith(("DELETE", "CREATE", "LOCK", "INSERT", "UPDATE", "ALTER", "DROP"))]


class TestMigrationShape:
    def test_one_transaction_locks_then_dedupes_then_indexes(self):
        conn = FakeConn(duplicates=3)
        result = mig.migrate(conn)
        writes = conn.writes()
        assert [w.split()[0] for w in writes] == ["LOCK", "DELETE", "CREATE"]
        assert writes[0] == "LOCK TABLE CLAUDE_PLAN_USAGE_READINGS IN SHARE ROW EXCLUSIVE MODE"
        assert conn.commits == 1 and conn.rollbacks == 0
        assert result["deleted"] == 3
        assert result["index_existed"] is False

    def test_dedupe_keeps_the_lowest_id_of_each_key_nulls_included(self):
        conn = FakeConn(duplicates=1)
        mig.migrate(conn)
        delete = next(w for w in conn.writes() if w.startswith("DELETE"))
        # PARTITION BY puts NULLs in one group, so NULL user_id twins are deduped too.
        assert "PARTITION BY USER_ID, SOURCE, OBSERVED_AT ORDER BY ID" in delete
        assert "> 1" in delete

    def test_the_index_is_unique_nulls_not_distinct_and_named(self):
        conn = FakeConn()
        mig.migrate(conn)
        create = next(w for w in conn.writes() if w.startswith("CREATE"))
        assert create == (
            "CREATE UNIQUE INDEX IF NOT EXISTS CLAUDE_PLAN_USAGE_READINGS_USER_SOURCE_OBSERVED_UNIQ "
            "ON CLAUDE_PLAN_USAGE_READINGS (USER_ID, SOURCE, OBSERVED_AT) NULLS NOT DISTINCT")
        assert mig.INDEX == "claude_plan_usage_readings_user_source_observed_uniq"

    def test_a_lock_wait_is_bounded(self):
        conn = FakeConn()
        mig.migrate(conn)
        texts = [s for s, _ in conn.statements]
        assert any(t.startswith("SET LOCAL LOCK_TIMEOUT") for t in texts)
        assert texts.index(next(t for t in texts if t.startswith("SET LOCAL LOCK_TIMEOUT"))) < \
            texts.index(next(t for t in texts if t.startswith("LOCK")))

    def test_below_postgres_15_it_fails_clearly_and_changes_nothing(self):
        conn = FakeConn(version=140011, duplicates=2)
        with pytest.raises(mig.UnsupportedServer, match="15"):
            mig.migrate(conn)
        assert conn.writes() == []
        assert conn.commits == 0

    def test_a_missing_table_is_reported_not_created(self):
        conn = FakeConn(table=False)
        result = mig.migrate(conn)
        assert result["table_exists"] is False
        assert conn.writes() == []
        assert conn.commits == 0

    def test_a_failure_rolls_back(self):
        conn = FakeConn(duplicates=1)
        real_cursor = conn.cursor

        def failing_cursor():
            cur = real_cursor()
            execute = cur.execute

            def maybe_fail(sql, params=None):
                execute(sql, params)
                if _norm(sql).startswith("CREATE"):
                    raise RuntimeError("boom")
            cur.execute = maybe_fail
            return cur

        conn.cursor = failing_cursor
        with pytest.raises(RuntimeError):
            mig.migrate(conn)
        assert conn.rollbacks == 1 and conn.commits == 0


class TestDryRun:
    def test_dry_run_counts_and_reports_the_index_without_writing(self):
        conn = FakeConn(duplicates=4, index=False)
        result = mig.migrate(conn, dry_run=True)
        assert conn.writes() == []
        assert conn.commits == 0 and conn.rollbacks == 1
        assert result == {"table_exists": True, "index": mig.INDEX, "index_existed": False,
                          "duplicates": 4, "deleted": 0, "dry_run": True}

    def test_dry_run_is_a_read_only_transaction(self):
        conn = FakeConn()
        mig.migrate(conn, dry_run=True)
        assert conn.statements[0][0] == "SET TRANSACTION READ ONLY"

    def test_dry_run_cli_prints_counts_and_index_name_only(self, monkeypatch, capsys):
        conn = FakeConn(duplicates=4, index=True)
        monkeypatch.setenv("NEON_DB_URL", "postgresql://someone:hunter2@db.example/neondb")
        monkeypatch.setattr(mig, "_connect", lambda url: conn)
        assert mig.main(["--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "would delete 4 duplicate rows" in out
        assert f"index {mig.INDEX} exists: yes" in out
        assert "hunter2" not in out and "db.example" not in out
        assert conn.writes() == [] and conn.closed


class TestCli:
    def test_no_url_is_an_error(self, monkeypatch, capsys):
        monkeypatch.delenv("NEON_DB_URL", raising=False)
        assert mig.main([]) == 1
        assert "NEON_DB_URL" in capsys.readouterr().out

    def test_run_prints_only_counts_and_the_index_name(self, monkeypatch, capsys):
        conn = FakeConn(duplicates=2)
        monkeypatch.setenv("NEON_DB_URL", "postgresql://someone:hunter2@db.example/neondb")
        monkeypatch.setattr(mig, "_connect", lambda url: conn)
        assert mig.main([]) == 0
        out = capsys.readouterr().out
        assert "deleted 2 duplicate rows" in out
        assert f"index {mig.INDEX} created" in out
        assert "hunter2" not in out and "db.example" not in out

    def test_second_run_says_the_index_already_existed(self, monkeypatch, capsys):
        conn = FakeConn(duplicates=0, index=True)
        monkeypatch.setenv("NEON_DB_URL", "postgresql://x")
        monkeypatch.setattr(mig, "_connect", lambda url: conn)
        assert mig.main([]) == 0
        out = capsys.readouterr().out
        assert "deleted 0 duplicate rows" in out
        assert f"index {mig.INDEX} already existed" in out

    def test_old_server_message_names_the_requirement(self, monkeypatch, capsys):
        monkeypatch.setenv("NEON_DB_URL", "postgresql://x")
        monkeypatch.setattr(mig, "_connect", lambda url: FakeConn(version=140011))
        assert mig.main([]) == 1
        assert "PostgreSQL 15" in capsys.readouterr().out

    def test_driver_errors_print_the_class_only(self, monkeypatch, capsys):
        monkeypatch.setenv("NEON_DB_URL", "postgresql://x")

        def refuse(url):
            raise RuntimeError("could not connect to host db.example user someone")
        monkeypatch.setattr(mig, "_connect", refuse)
        assert mig.main([]) == 1
        out = capsys.readouterr().out
        assert "RuntimeError" in out and "db.example" not in out

    def test_importing_the_module_does_not_read_dotenv(self):
        assert "load_dotenv" not in SCRIPT.read_text().split('if __name__ == "__main__":')[0]


class TestRecordSql:
    def test_insert_keeps_the_guard_and_ignores_any_unique_conflict(self):
        executed = []

        class Cur:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params=()):
                executed.append(_norm(sql))

            def fetchone(self):
                return None

        class Conn:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def cursor(self):
                return Cur()

        store = cpu.ClaudePlanUsageStore("postgres://fake")
        store._initialized = True
        store._connect = lambda: Conn()
        reading = cpu.make_reading(cpu.build_windows(30, "2026-11-16T09:00:00+00:00"),
                                   source="claude_code_cli", observed_at="2026-11-14T23:50:00+00:00")
        assert store.record("u1", reading) == {"recorded": False, "reason": "already stored"}
        insert = next(s for s in executed if s.startswith("INSERT"))
        assert "WHERE NOT EXISTS" in insert
        # No conflict target: it works before the index exists and after it.
        assert "ON CONFLICT DO NOTHING RETURNING ID" in insert
        assert "ON CONFLICT (" not in insert


# --- Real Postgres --------------------------------------------------------------

PG_URL = os.getenv("MECRIS_TEST_PG_URL")


def _local_pg_url():
    if not PG_URL:
        pytest.skip("MECRIS_TEST_PG_URL not set (throwaway local Postgres only)")
    if urlparse(PG_URL).hostname not in ("127.0.0.1", "localhost", "::1"):
        pytest.skip("MECRIS_TEST_PG_URL must point at localhost")
    return PG_URL


@pytest.fixture
def pg():
    import psycopg2
    url = _local_pg_url()
    admin = psycopg2.connect(url)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS claude_plan_usage_readings")
        cur.execute("CREATE TABLE IF NOT EXISTS users (pocket_id_sub TEXT PRIMARY KEY)")
        cur.execute("INSERT INTO users VALUES ('u1'), ('u2') ON CONFLICT DO NOTHING")
    # The table exactly as the server creates it.
    cpu.ClaudePlanUsageStore(url).init_database()
    yield url, admin
    admin.close()


def _run_script(url, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("NEON_DB_URL", "DATABASE_URL")}
    env["NEON_DB_URL"] = url
    done = subprocess.run([sys.executable, str(SCRIPT), *args], env=env, cwd=ROOT,
                          capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout + done.stderr


def _ids(admin):
    with admin.cursor() as cur:
        cur.execute("SELECT id FROM claude_plan_usage_readings ORDER BY id")
        return [r[0] for r in cur.fetchall()]


def _index_def(admin):
    with admin.cursor() as cur:
        cur.execute("SELECT indexdef FROM pg_indexes WHERE indexname = %s", (mig.INDEX,))
        row = cur.fetchone()
    return row[0] if row else None


class TestAgainstRealPostgres:
    def test_migration_dedupes_keeps_lowest_ids_and_a_second_run_changes_nothing(self, pg):
        url, admin = pg
        t1, t2 = "2026-11-14T23:00:00+00:00", "2026-11-14T23:15:00+00:00"
        rows = [
            ("u1", "claude_code_cli", t1),  # 1 kept
            ("u1", "claude_code_cli", t1),  # 2 duplicate
            ("u1", "claude_code_cli", t1),  # 3 duplicate
            ("u1", "manual", t1),           # 4 kept: another source
            ("u2", "claude_code_cli", t1),  # 5 kept: another user
            ("u1", "claude_code_cli", t2),  # 6 kept: another time
            (None, "claude_code_cli", t1),  # 7 kept
            (None, "claude_code_cli", t1),  # 8 duplicate: NULLs count as equal
            ("u2", "claude_code_cli", t1),  # 9 duplicate of 5
        ]
        with admin.cursor() as cur:
            # The server's table has user_id NOT NULL; drop it here only to prove the
            # dedupe and the index treat NULL user_ids as one key.
            cur.execute("ALTER TABLE claude_plan_usage_readings ALTER COLUMN user_id DROP NOT NULL")
            for user, source, observed in rows:
                cur.execute(
                    """INSERT INTO claude_plan_usage_readings (user_id, plan, windows, source, observed_at)
                       VALUES (%s, 'ultra', '[]'::jsonb, %s, %s)""", (user, source, observed))
        assert _ids(admin) == list(range(1, 10))

        code, out = _run_script(url, "--dry-run")
        assert code == 0, out
        assert "would delete 4 duplicate rows" in out
        assert f"index {mig.INDEX} exists: no" in out
        assert _ids(admin) == list(range(1, 10)) and _index_def(admin) is None

        code, out = _run_script(url)
        assert code == 0, out
        assert "deleted 4 duplicate rows" in out and f"index {mig.INDEX} created" in out
        assert _ids(admin) == [1, 4, 5, 6, 7]
        indexdef = _index_def(admin)
        assert "UNIQUE" in indexdef and "NULLS NOT DISTINCT" in indexdef
        assert "(user_id, source, observed_at)" in indexdef

        code, out = _run_script(url)
        assert code == 0, out
        assert "deleted 0 duplicate rows" in out and f"index {mig.INDEX} already existed" in out
        assert _ids(admin) == [1, 4, 5, 6, 7]

        import psycopg2
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with admin.cursor() as cur:
                cur.execute(
                    """INSERT INTO claude_plan_usage_readings (user_id, plan, windows, source, observed_at)
                       VALUES (NULL, 'ultra', '[]'::jsonb, 'claude_code_cli', %s)""", (t1,))

    def test_two_interleaved_records_both_land_before_the_index_and_one_after(self, pg):
        url, admin = pg
        windows = cpu.build_windows(30, "2026-11-16T09:00:00+00:00")
        before = cpu.make_reading(windows, source="claude_code_cli", observed_at="2026-11-14T23:00:00+00:00")
        after = cpu.make_reading(windows, source="claude_code_cli", observed_at="2026-11-14T23:30:00+00:00")

        a, b, b_waited = _interleaved_records(url, admin, before)
        assert a["recorded"] is True and b["recorded"] is True
        assert b_waited is False
        assert _count(admin, before) == 2

        code, out = _run_script(url)
        assert code == 0, out
        assert "deleted 1 duplicate rows" in out
        assert _count(admin, before) == 1

        a, b, b_waited = _interleaved_records(url, admin, after)
        assert a["recorded"] is True
        assert b == {"recorded": False, "reason": "already stored"}
        # b blocked on the index, so its NOT EXISTS check had passed: the index closed the race.
        assert b_waited is True
        assert _count(admin, after) == 1


def _count(admin, reading):
    with admin.cursor() as cur:
        cur.execute("""SELECT count(*) FROM claude_plan_usage_readings
                       WHERE user_id = 'u1' AND source = %s AND observed_at = %s::timestamptz""",
                    (reading["source"], reading["observed_at"]))
        return cur.fetchone()[0]


def _interleaved_records(url, admin, reading):
    """Two stores record the same reading. A inserts and holds its transaction open;
    B runs while A's row is uncommitted, so B's NOT EXISTS check passes too. Then A
    commits. Returns (A's result, B's result, whether B had to wait on a lock)."""
    import psycopg2

    a_inserted, release_a = threading.Event(), threading.Event()

    class HeldConn:
        def __init__(self):
            self.conn = psycopg2.connect(url)

        def __enter__(self):
            return self.conn.__enter__()

        def __exit__(self, *exc):
            a_inserted.set()
            release_a.wait(30)
            try:
                return self.conn.__exit__(*exc)
            finally:
                self.conn.close()

    class ClosingConn(HeldConn):
        def __exit__(self, *exc):
            try:
                return self.conn.__exit__(*exc)
            finally:
                self.conn.close()

    store_a, store_b = cpu.ClaudePlanUsageStore(url), cpu.ClaudePlanUsageStore(url)
    # Initialize up front: CREATE INDEX IF NOT EXISTS would wait on A's open transaction.
    store_a.init_database()
    store_b.init_database()
    store_a._connect = HeldConn
    store_b._connect = ClosingConn

    results, errors = {}, []

    def run(name, store):
        try:
            results[name] = store.record("u1", reading)
        except Exception as e:  # surfaced by the assertion below
            errors.append(e)

    ta = threading.Thread(target=run, args=("a", store_a))
    ta.start()
    assert a_inserted.wait(30)
    tb = threading.Thread(target=run, args=("b", store_b))
    tb.start()

    b_waited = False
    deadline = time.monotonic() + 30
    while tb.is_alive() and time.monotonic() < deadline:
        with admin.cursor() as cur:
            cur.execute("""SELECT count(*) FROM pg_stat_activity
                           WHERE wait_event_type = 'Lock' AND pid <> pg_backend_pid()
                             AND query LIKE '%INSERT INTO claude_plan_usage_readings%'""")
            if cur.fetchone()[0]:
                b_waited = True
                break
        time.sleep(0.05)

    release_a.set()
    ta.join(30)
    tb.join(30)
    assert errors == []
    return results["a"], results["b"], b_waited
