import psycopg2
import os

db_url = os.environ.get('NEON_DB_URL')
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'walk_inferences' ORDER BY ordinal_position;")
rows = cur.fetchall()
for r in rows:
    print(r)
cur.close()
conn.close()
