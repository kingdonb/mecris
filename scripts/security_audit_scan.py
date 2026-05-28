import os
import psycopg2
from dotenv import load_dotenv
import binascii

load_dotenv()
neon_url = os.getenv("NEON_DB_URL")

def is_hex(s):
    if not s: return False
    try:
        int(s, 16)
        return len(s) % 2 == 0
    except:
        return False

print(f"Scanning Neon DB for PII vulnerabilities...")
try:
    with psycopg2.connect(neon_url) as conn:
        with conn.cursor() as cur:
            # Check users table
            print("\n--- Users Table ---")
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users';")
            cols = [r[0] for r in cur.fetchall()]
            print(f"Columns: {cols}")
            
            cur.execute("SELECT familiar_id, phone_number_encrypted, location_lat, location_lon FROM users LIMIT 5;")
            for row in cur.fetchall():
                familiar_id, phone, lat, lon = row
                phone_status = "ENCRYPTED" if is_hex(phone) else "PLAINTEXT (!!!)" if phone else "NULL"
                lat_status = "PLAINTEXT (!!!)" if lat else "NULL"
                lon_status = "PLAINTEXT (!!!)" if lon else "NULL"
                print(f"User: {familiar_id} | Phone: {phone_status} | Lat: {lat_status} | Lon: {lon_status}")

            # Check walk_inferences table
            print("\n--- Walk Inferences Table ---")
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'walk_inferences';")
            cols = [r[0] for r in cur.fetchall()]
            print(f"Columns: {cols}")
            
            cur.execute("SELECT user_id, start_time, distance_source, gps_route_points FROM walk_inferences LIMIT 5;")
            for row in cur.fetchall():
                uid, start, source, gps = row
                gps_status = "ENCRYPTED" if is_hex(gps) else "PLAINTEXT"
                print(f"Walk: {start} | Source: {source} | GPS Points Field: {gps_status}")

            # Check message_log table
            print("\n--- Message Log Table ---")
            cur.execute("SELECT type, content, error_msg FROM message_log LIMIT 5;")
            for row in cur.fetchall():
                mtype, content, error = row
                content_status = "ENCRYPTED" if is_hex(content) else "PLAINTEXT (!!!)" if content else "NULL"
                print(f"Type: {mtype} | Content: {content_status}")

except Exception as e:
    print(f"Scan failed: {e}")
