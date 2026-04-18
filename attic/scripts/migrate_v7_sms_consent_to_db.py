import os
import json
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

def migrate():
    load_dotenv()
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        print("❌ NEON_DB_URL not set")
        return

    consent_file = Path("data/sms_consent.json")
    if not consent_file.exists():
        print("ℹ️ data/sms_consent.json not found, nothing to migrate.")
        return

    with open(consent_file, "r") as f:
        data = json.load(f)

    conn = psycopg2.connect(neon_url)
    cur = conn.cursor()

    try:
        # For now, we only have one user 'yebyen' we're sure about
        # In a real multi-tenant system we'd need to match by phone number
        # but phone numbers are encrypted in the DB.
        # Since this is a pre-beta hardening, we'll map the known record to 'yebyen'.
        
        target_familiar_id = "yebyen"
        
        # Find the specific record for the user's number (redacted for privacy)
        # Use TWILIO_TO_NUMBER from env as the lookup key for the migration
        target_number = os.getenv('TWILIO_TO_NUMBER')
        if not target_number:
            print("❌ TWILIO_TO_NUMBER not set in env, cannot identify which record to migrate.")
            return

        user_key = target_number.replace('+', '').replace('-', '').replace(' ', '')
        
        if user_key in data["users"]:
            record = data["users"][user_key]
            print(f"Migrating record for [REDACTED] to user '{target_familiar_id}'")
            
            # Prepare notification_prefs JSON
            prefs = {
                "sms_opted_in": record.get("opted_in", False),
                "sms_opt_in_date": record.get("opt_in_date"),
                "sms_opt_in_method": record.get("opt_in_method"),
                "message_types": record.get("message_types", []),
                "time_window_start": record.get("preferences", {}).get("time_window_start", 14),
                "time_window_end": record.get("preferences", {}).get("time_window_end", 17),
                "max_messages_per_day": record.get("preferences", {}).get("max_messages_per_day", 3),
                "enabled_days": record.get("preferences", {}).get("enabled_days", []),
                "vacation_mode": record.get("preferences", {}).get("vacation_mode", False)
            }
            
            cur.execute("""
                UPDATE users 
                SET notification_prefs = %s 
                WHERE familiar_id = %s
            """, (json.dumps(prefs), target_familiar_id))
            
            conn.commit()
            print(f"✅ Successfully migrated preferences for {target_familiar_id}")
            
            # Keep the old file as backup but rename it to show it's migrated
            backup_file = consent_file.with_suffix(".json.migrated")
            os.rename(consent_file, backup_file)
            print(f"ℹ️ Original file moved to {backup_file}")
        else:
            print(f"⚠️ No record found for {yebyen_number} in {consent_file}")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
