import sqlite3
import os

db_path = os.getenv("MECRIS_DB_PATH", "mecris_usage.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT * FROM message_log ORDER BY date DESC LIMIT 10")
rows = cur.fetchall()
print("SQLite message_log:")
for r in rows: print(r)

try:
    import psycopg2
    neon_url = os.getenv("NEON_DB_URL")
    if neon_url:
        nconn = psycopg2.connect(neon_url)
        ncur = nconn.cursor()
        ncur.execute("SELECT * FROM message_log ORDER BY date DESC LIMIT 10")
        nrows = ncur.fetchall()
        print("\nNeon message_log:")
        for r in nrows: print(r)
except Exception as e:
    print(e)
