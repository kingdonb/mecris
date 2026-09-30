"""Migration: helix_balance_log + helix_balance_requests (task 588, lever C2).

Two tables (design.md §3 C2 + the Android hook):

  helix_balance_log      — every reading of the Helix wallet (odometer history).
                           R2: user_id-scoped, source-tagged; velocity (delta) is
                           computed HERE, by differencing our own history — never
                           from Beeminder (R8: the sink is a sink).
  helix_balance_requests — the Android→backend job hook (the walk-sync pattern):
                           the app POSTs /helix-balance/request → the Rust edge
                           upserts a row here → the laptop leader polls it and
                           runs the sync. One row per user; processed_at gates it.

Run once against production Neon (NEON_DB_URL in .env):

    python scripts/migrate_helix_balance_log.py
"""
import os
import sys

import psycopg2
from dotenv import load_dotenv

# Same env loading pattern as migrate_budget_governor_spend_log.py
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

NEON_DB_URL = os.getenv("NEON_DB_URL")

if not NEON_DB_URL:
    print("ERROR: NEON_DB_URL not set in environment")
    exit(1)

SQL = """
-- Helix balance odometer log (task 588: Helix billing -> Beeminder helix-ml goal)
CREATE TABLE IF NOT EXISTS helix_balance_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    day TEXT NOT NULL,                    -- US/Eastern YYYY-MM-DD (reviewstack daystamp, D3 default)
    balance NUMERIC(10, 4),               -- NULL iff fetch failed (unknown is never $0)
    delta NUMERIC(10, 4),                 -- signed balance change vs previous ok reading
    source TEXT NOT NULL DEFAULT 'api',   -- api | manual
    fetch_status TEXT NOT NULL,           -- ok | failed
    inflow BOOLEAN NOT NULL DEFAULT FALSE,-- positive delta flagged, never absorbed into "burned"
    pushed_value NUMERIC(10, 4),          -- value this reading pushed to Beeminder (NULL = no push)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS helix_balance_log_user_ts_idx
    ON helix_balance_log (user_id, ts DESC);

-- Android hook: app requests a balance sync; leader polls and marks processed.
CREATE TABLE IF NOT EXISTS helix_balance_requests (
    user_id TEXT PRIMARY KEY,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- Edge-primary sync (rev: Android + edge are the always-on server; leader = fallback).
-- The laptop leader provisions this column from HELIX_BILLING_API_TOKEN via
-- scripts/helix_balance_scraper.provision_helix_token (AES-256-GCM, Rust-compatible).
ALTER TABLE users ADD COLUMN IF NOT EXISTS helix_api_token_encrypted TEXT NOT NULL DEFAULT '';

-- Failure diagnostics (rev 7 debug): every edge-side failure persists its reason here.
ALTER TABLE helix_balance_log ADD COLUMN IF NOT EXISTS last_error TEXT;
"""


def main():
    print("Creating helix_balance_log + helix_balance_requests tables...")
    try:
        with psycopg2.connect(NEON_DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(SQL)
                print("✅ Tables created successfully")

                for table in ("helix_balance_log", "helix_balance_requests"):
                    cur.execute("""
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_name = %s ORDER BY ordinal_position
                    """, (table,))
                    rows = cur.fetchall()
                    print(f"\nSchema of {table}:")
                    for name, dtype in rows:
                        print(f"  - {name}: {dtype}")

                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name IN ('users', 'helix_balance_log')
                      AND column_name IN ('helix_api_token_encrypted', 'last_error')
                """)
                found = {r[0] for r in cur.fetchall()}
                for col in ("helix_api_token_encrypted", "last_error"):
                    print(f"{col}: {'OK' if col in found else 'MISSING'}")
                if not all(c in found for c in ("helix_api_token_encrypted", "last_error")):
                    sys.exit(1)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
