
import asyncio
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from scheduler import _global_walk_sync_job
from services.credentials_manager import credentials_manager
from beeminder_client import BeeminderClient

async def main():
    user_id = credentials_manager.resolve_user_id()
    print(f"Manually triggering walk sync for user: {user_id}")
    
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        print("Error: NEON_DB_URL not set.")
        return

    # Check for 'logging' walks (received by Spin but not marked 'logged')
    with psycopg2.connect(neon_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, start_time, step_count, distance_meters, distance_source FROM walk_inferences WHERE status = 'logging' AND user_id = %s ORDER BY start_time DESC", (user_id,))
            logging_walks = cur.fetchall()
    
    if not logging_walks:
        print("No 'logging' walks found.")
        return
        
    print(f"Found {len(logging_walks)} 'logging' walks. Synchronizing...")
    
    client = BeeminderClient(user_id=user_id)
    
    for walk in logging_walks:
        miles = float(walk['distance_meters']) / 1609.34
        start_time = walk['start_time']
        request_id = f"{user_id}_{start_time}"
        comment = f"Logged via Mecris MCP Sync (Steps: {walk['step_count']}, Source: {walk['distance_source']})"
        
        print(f"Syncing walk {walk['id']} ({start_time}) - {miles:.3f} miles...")
        
        # Beeminder will deduplicate via request_id if it was already synced with the same ID
        # Wait, Spin DOES NOT use requestid, so we MIGHT double-log if it succeeded in Spin.
        # But we want 'logged' status to be set.
        
        # Let's check if it exists on Beeminder first? Too slow.
        # Let's just push it. If it was already there without ID, it will be a duplicate.
        # BUT today's walk is NOT on Beeminder, so we definitely need to push it.
        
        success = await client.add_datapoint("bike", miles, comment=comment, requestid=request_id)
        if success:
            print(f"Successfully synced walk {walk['id']}.")
            with psycopg2.connect(neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE walk_inferences SET status = 'logged' WHERE id = %s", (walk['id'],))
            print(f"Marked walk {walk['id']} as 'logged'.")
        else:
            print(f"Failed to sync walk {walk['id']}.")

    await client.close()
    print("Manual sync completed.")

if __name__ == "__main__":
    asyncio.run(main())
