"""
Migration v9: model the Claude subscription in budget_tracking (kingdonb/mecris#345).

Adds three columns to budget_tracking:
- source_type TEXT NOT NULL DEFAULT 'api_credit', one of api_credit, subscription, retired;
- plan TEXT (for example 'ultra');
- monthly_price_usd DOUBLE PRECISION (optional).

Additive and idempotent: ADD COLUMN IF NOT EXISTS, and the CHECK constraint is
added only when pg_constraint does not already have it. Existing rows become
api_credit, so readers that only use the numeric remaining_budget (the Spin
aggregate and the web dashboard) see no change.

Converting the live row to the Ultra grant is a separate, explicit
update_budget call (source_type='subscription', plan, period_start, period_end).

Run: python scripts/migrate_v9_subscription_budget.py   (needs NEON_DB_URL)
"""
import os

CONSTRAINT = "budget_tracking_source_type_check"

STATEMENTS = [
    """
    ALTER TABLE budget_tracking
    ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'api_credit'
    """,
    """
    ALTER TABLE budget_tracking
    ADD COLUMN IF NOT EXISTS plan TEXT
    """,
    """
    ALTER TABLE budget_tracking
    ADD COLUMN IF NOT EXISTS monthly_price_usd DOUBLE PRECISION
    """,
    f"""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{CONSTRAINT}') THEN
            ALTER TABLE budget_tracking
            ADD CONSTRAINT {CONSTRAINT}
            CHECK (source_type IN ('api_credit', 'subscription', 'retired'));
        END IF;
    END
    $$
    """,
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
        print(f"Migration v9 (subscription budget) failed: {type(e).__name__}")
        return 1
    finally:
        conn.close()
    print("Migration v9 (subscription budget) completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
