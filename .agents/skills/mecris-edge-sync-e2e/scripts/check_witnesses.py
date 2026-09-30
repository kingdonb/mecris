#!/usr/bin/env python3
"""Query Neon Postgres for the latest Helix balance request & execution witnesses."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
neon_url = os.getenv("NEON_DB_URL")
if not neon_url:
    print("Error: NEON_DB_URL not set in environment or .env", file=sys.stderr)
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 not found. Run: source .venv/bin/activate", file=sys.stderr)
    sys.exit(1)

conn = psycopg2.connect(neon_url)
cur = conn.cursor()

print("--- Latest Requests (helix_balance_requests) ---")
try:
    cur.execute("SELECT user_id, requested_at, processed_at FROM helix_balance_requests ORDER BY requested_at DESC LIMIT 3;")
    rows = cur.fetchall()
    for r in rows:
        print(f"User: {r[0]} | Requested: {r[1]} | Processed: {r[2]}")
except Exception as e:
    print(f"Error querying requests: {e}")

print("\n--- Latest Log Entries (helix_balance_log) ---")
try:
    cur.execute("SELECT id, ts, fetch_status, balance, delta, pushed_value, last_error FROM helix_balance_log ORDER BY id DESC LIMIT 5;")
    rows = cur.fetchall()
    for r in rows:
        print(f"ID #{r[0]} | TS: {r[1]} | Status: {r[2]} | Bal: {r[3]} | Delta: {r[4]} | Pushed: {r[5]} | Error: {r[6]}")
except Exception as e:
    print(f"Error querying logs: {e}")

cur.close()
conn.close()
