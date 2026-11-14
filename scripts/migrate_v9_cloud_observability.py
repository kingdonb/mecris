"""
Migration v9: cloud cron observability (kingdonb/mecris#183, #245).

- internal_refusals: refused callers of the Spin cron endpoints and the Twilio webhook,
  one row per America/New_York day, endpoint and reason (no_key, bad_key, burned_key,
  bad_signature), so scanners cannot grow it.
- scheduler_election.last_status / last_error / intent: re-asserted (v8 added them live),
  so a fresh database gets them too. Spin writes every cron run's outcome there.

Additive and idempotent: CREATE TABLE / ADD COLUMN IF NOT EXISTS only. Nothing is
dropped, updated or deleted. Run before deploying the Spin release that writes them;
Spin treats a missing table as best-effort, so order is not critical.

Usage: python scripts/migrate_v9_cloud_observability.py   (reads NEON_DB_URL)
"""
import os
import sys

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS internal_refusals (
        day DATE NOT NULL,
        endpoint VARCHAR(50) NOT NULL,
        reason VARCHAR(50) NOT NULL,
        count BIGINT NOT NULL DEFAULT 0,
        last_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (day, endpoint, reason)
    )
    """,
    "ALTER TABLE scheduler_election ADD COLUMN IF NOT EXISTS last_status VARCHAR(255)",
    "ALTER TABLE scheduler_election ADD COLUMN IF NOT EXISTS last_error TEXT",
    "ALTER TABLE scheduler_election ADD COLUMN IF NOT EXISTS intent VARCHAR(255)",
]


def migrate(conn):
    """Apply every statement in one transaction."""
    cur = conn.cursor()
    try:
        for sql in STATEMENTS:
            cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _connect(url):
    import psycopg2
    return psycopg2.connect(url)


def main():
    url = os.getenv("NEON_DB_URL")
    if not url:
        print("Error: NEON_DB_URL not found")
        return 1
    conn = _connect(url)
    try:
        migrate(conn)
    except Exception as e:
        print(f"Migration v9 failed: {type(e).__name__}")
        return 1
    finally:
        conn.close()
    print("Migration v9 completed: internal_refusals and scheduler_election outcome columns are in place.")
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
