"""
Migration v11: allow source_type 'helix_grant' in budget_tracking (kingdonb/mecris#393).

v9 added the CHECK constraint budget_tracking_source_type_check with
api_credit, subscription and retired. This replaces it with the same list plus
helix_grant: the budget that follows the Helix monthly grant, computed on read
from the wallet's own period and the helix_balance_log.

Idempotent: the constraint is dropped if present and added again with the
wider list, in one transaction. No rows change. Converting the live row is a
separate update_budget call (source_type='helix_grant', total_budget=100).

Run: python scripts/migrate_v11_helix_grant_budget.py   (needs NEON_DB_URL)
"""
import os

CONSTRAINT = "budget_tracking_source_type_check"
ALLOWED = ("api_credit", "subscription", "retired", "helix_grant")

STATEMENTS = [
    f"ALTER TABLE budget_tracking DROP CONSTRAINT IF EXISTS {CONSTRAINT}",
    f"ALTER TABLE budget_tracking ADD CONSTRAINT {CONSTRAINT} "
    f"CHECK (source_type IN ({', '.join(repr(v) for v in ALLOWED)}))",
]


def migrate(conn) -> None:
    """Apply every statement on an open connection, then commit."""
    cur = conn.cursor()
    try:
        for statement in STATEMENTS:
            cur.execute(statement)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def main() -> int:
    from dotenv import load_dotenv
    import psycopg2

    load_dotenv()
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        print("Error: NEON_DB_URL not found")
        return 1
    conn = psycopg2.connect(neon_url)
    try:
        migrate(conn)
    except Exception as e:
        # Exception class only: driver messages can echo connection details.
        print(f"Migration v11 (helix grant budget) failed: {type(e).__name__}")
        return 1
    finally:
        conn.close()
    print("Migration v11 (helix grant budget) completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
