"""
Mecris Harmony Report

Queries the jet_divergence table to report on any discord between
the Python Vanguard (Source) and the Rust Iron Core (Jet).
"""

import os
import psycopg2
import json
from datetime import datetime

def get_neon_conn():
    url = os.environ.get("NEON_DB_URL")
    if not url:
        raise ValueError("NEON_DB_URL not set")
    return psycopg2.connect(url)

def check_harmony():
    print("--- Mecris Harmony Report: Source vs Jet ---")
    conn = get_neon_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM jet_divergence")
    count = cur.fetchone()[0]
    
    if count == 0:
        print("✨ PERFECT HARMONY: No divergences detected in the last window.")
        return
    
    print(f"⚠️ DISCORD DETECTED: {count} divergence event(s) recorded.\n")
    
    cur.execute("""
        SELECT component_name, user_id, source_result, jet_result, detected_at 
        FROM jet_divergence 
        ORDER BY detected_at DESC LIMIT 5
    """)
    
    for row in cur.fetchall():
        comp, uid, source, jet, ts = row
        print(f"[{ts}] Component: {comp} (User: {uid})")
        print(f"  Source (PY): {source}")
        print(f"  Jet    (RS): {jet}")
        print("-" * 40)

if __name__ == "__main__":
    try:
        check_harmony()
    except Exception as e:
        print(f"Error checking harmony: {e}")
