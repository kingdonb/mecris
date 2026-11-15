"""
Migration v9: one stored Claude plan usage reading per user, source and
observed_at (kingdonb/mecris#344).

ClaudePlanUsageStore.record skips a reading that is already stored, but without
a unique index two inserts at the same instant (say, two scheduler leaders
during a handover) can both land. This adds the index that closes that race:

    claude_plan_usage_readings_user_source_observed_uniq
    ON claude_plan_usage_readings (user_id, source, observed_at) NULLS NOT DISTINCT

In one transaction it locks the table against concurrent writes (reads still
work), deletes duplicate rows keeping the lowest id of each key, and creates the
index if it does not exist. Running it again deletes nothing and keeps the index.
NULLS NOT DISTINCT needs PostgreSQL 15 or later; an older server is refused
before anything changes. If the table does not exist yet, nothing is done.

Only counts and the index name are printed, never the URL or row contents.

Usage: python scripts/migrate_v9_claude_readings_unique.py [--dry-run]   (reads NEON_DB_URL)
"""
import argparse
import os
import sys

TABLE = "claude_plan_usage_readings"
INDEX = "claude_plan_usage_readings_user_source_observed_uniq"
MIN_SERVER_VERSION_NUM = 150000  # NULLS NOT DISTINCT
LOCK_TIMEOUT = "10s"

# Every row after the first (lowest id) of its key. PARTITION BY groups NULLs
# together, matching NULLS NOT DISTINCT.
_DUPLICATE_IDS = f"""
    SELECT id FROM (
        SELECT id, row_number() OVER (PARTITION BY user_id, source, observed_at ORDER BY id) AS n
        FROM {TABLE}
    ) ranked
    WHERE n > 1
"""
SERVER_VERSION = "SELECT current_setting('server_version_num')::int"
RELATION_EXISTS = "SELECT to_regclass(%s) IS NOT NULL"
COUNT_DUPLICATES = f"SELECT count(*) FROM ({_DUPLICATE_IDS}) duplicates"
LOCK = f"LOCK TABLE {TABLE} IN SHARE ROW EXCLUSIVE MODE"
DELETE_DUPLICATES = f"DELETE FROM {TABLE} WHERE id IN ({_DUPLICATE_IDS})"
CREATE_INDEX = (f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX} "
                f"ON {TABLE} (user_id, source, observed_at) NULLS NOT DISTINCT")


class UnsupportedServer(RuntimeError):
    """The server is older than PostgreSQL 15."""


def _one(cur, sql, params=None):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def migrate(conn, dry_run=False):
    """Dedupe and add the unique index in one transaction, or with dry_run only count.

    Returns {"table_exists", "index", "index_existed", "duplicates", "deleted", "dry_run"}.
    """
    cur = conn.cursor()
    try:
        if dry_run:
            cur.execute("SET TRANSACTION READ ONLY")
        version = _one(cur, SERVER_VERSION)
        if version < MIN_SERVER_VERSION_NUM:
            raise UnsupportedServer(
                f"needs PostgreSQL 15 or later for NULLS NOT DISTINCT (server_version_num {version})")
        result = {"table_exists": bool(_one(cur, RELATION_EXISTS, (TABLE,))), "index": INDEX,
                  "index_existed": False, "duplicates": 0, "deleted": 0, "dry_run": dry_run}
        if not result["table_exists"]:
            conn.rollback()
            return result
        result["index_existed"] = bool(_one(cur, RELATION_EXISTS, (INDEX,)))
        if dry_run:
            result["duplicates"] = _one(cur, COUNT_DUPLICATES)
            conn.rollback()
            return result
        # Wait at most LOCK_TIMEOUT for the lock, so the migration never queues
        # the server's inserts behind it for long.
        cur.execute(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'")
        # Blocks inserts, updates and deletes (not reads) until commit, so no new
        # duplicate can arrive between the delete and the index.
        cur.execute(LOCK)
        cur.execute(DELETE_DUPLICATES)
        result["deleted"] = result["duplicates"] = cur.rowcount
        cur.execute(CREATE_INDEX)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _connect(url):
    import psycopg2
    return psycopg2.connect(url)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Add the unique index on Claude plan usage readings.")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be deleted and whether the index exists; change nothing")
    args = parser.parse_args(argv)

    url = os.getenv("NEON_DB_URL")
    if not url:
        print("Error: NEON_DB_URL not found")
        return 1
    try:
        conn = _connect(url)
    except Exception as e:
        # Exception class only: driver messages can echo connection details.
        print(f"Migration v9 (claude readings unique) failed to connect: {type(e).__name__}")
        return 1
    try:
        result = migrate(conn, dry_run=args.dry_run)
    except UnsupportedServer as e:
        print(f"Migration v9 (claude readings unique) failed: {e}")
        return 1
    except Exception as e:
        print(f"Migration v9 (claude readings unique) failed: {type(e).__name__}")
        return 1
    finally:
        conn.close()

    if not result["table_exists"]:
        print(f"Migration v9 (claude readings unique): {TABLE} does not exist yet; nothing to do. "
              "The MCP server creates it on first use; run this again after that.")
        return 0
    if args.dry_run:
        exists = "yes" if result["index_existed"] else "no"
        print(f"Dry run: would delete {result['duplicates']} duplicate rows; "
              f"index {INDEX} exists: {exists}. Nothing changed.")
        return 0
    index = "already existed" if result["index_existed"] else "created"
    print(f"Migration v9 (claude readings unique) completed: deleted {result['deleted']} duplicate rows; "
          f"index {INDEX} {index}.")
    return 0


if __name__ == "__main__":
    # Only the command line reads .env; importing this module (tests) never does.
    # load_dotenv never overrides a NEON_DB_URL already in the environment.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    sys.exit(main())
