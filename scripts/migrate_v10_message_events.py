"""
Migration v10: see what happens to every reminder (kingdonb/mecris#363, phase 1 of
docs/WALK_REMINDERS.md). The shapes are contracts/message_events.json.

- message_log.client_ref: the phone's id for a shown nag, unique per user when present.
- message_log.message_sid / delivery_status / delivery_error / status_updated_at:
  Twilio's SID for a WhatsApp send and the latest delivery status from its callback.
- message_events: what happened to a message afterwards (tapped, dismissed, the
  notification actions, and Twilio's delivery statuses), once per (message, event, time).
- users.notifications_enabled / notifications_checked_at: from the phone's heartbeat.

No message text, phone numbers or names are stored in any of them.

Additive and idempotent: ADD COLUMN / CREATE ... IF NOT EXISTS only. Nothing is dropped,
updated or deleted. Run it before deploying the Spin release that writes them.

Usage: python scripts/migrate_v10_message_events.py   (reads NEON_DB_URL)
"""
import os
import sys

STATEMENTS = [
    "ALTER TABLE message_log ADD COLUMN IF NOT EXISTS client_ref TEXT",
    "ALTER TABLE message_log ADD COLUMN IF NOT EXISTS message_sid TEXT",
    "ALTER TABLE message_log ADD COLUMN IF NOT EXISTS delivery_status TEXT",
    "ALTER TABLE message_log ADD COLUMN IF NOT EXISTS delivery_error INTEGER",
    "ALTER TABLE message_log ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMPTZ",
    "CREATE UNIQUE INDEX IF NOT EXISTS message_log_user_client_ref_uniq ON message_log (user_id, client_ref) WHERE client_ref IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS message_log_message_sid_uniq ON message_log (message_sid) WHERE message_sid IS NOT NULL",
    """
    CREATE TABLE IF NOT EXISTS message_events (
        id SERIAL PRIMARY KEY,
        message_log_id INTEGER NOT NULL REFERENCES message_log(id) ON DELETE CASCADE,
        user_id VARCHAR(255) NOT NULL,
        event TEXT NOT NULL,
        at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (message_log_id, event, at)
    )
    """,
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_checked_at TIMESTAMPTZ",
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
        print(f"Migration v10 failed: {type(e).__name__}")
        return 1
    finally:
        conn.close()
    print("Migration v10 completed: message_log delivery columns, message_events and users.notifications_enabled are in place.")
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
