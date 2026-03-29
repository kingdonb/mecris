import asyncio
import logging
import sqlite3
import os
from scheduler import MecrisScheduler

# Minimal mock for testing
async def mock_trigger():
    print(" [MOCK] Trigger called")
    return {"triggered": False, "reason": "test"}

async def run_test():
    db = "mecris_usage.db"
    print(f"--- Coordination Test (DB: {db}) ---")
    
    # Instance 1
    s1 = MecrisScheduler()
    s1.start()
    
    # Instance 2
    s2 = MecrisScheduler()
    s2.start()
    
    print("Both instances started. Waiting for election...")
    await asyncio.sleep(2)
    
    print(f"Instance 1 ({s1.process_id}) leader: {s1.is_leader}")
    print(f"Instance 2 ({s2.process_id}) leader: {s2.is_leader}")
    
    # Instance 1 (let's assume it's leader or follower) enqueues a job
    print("\nEnqueuing a delayed job via Instance 2...")
    s2.enqueue_delayed_message("Hello from Follower!", 1)
    
    print("\nChecking shared queue via Instance 1...")
    queue = s1.get_queue()
    for job in queue:
        print(f" - Job {job['id']} next run: {job['next_run']}")
        
    print("\nSimulating Leader death (Instance 1)...")
    if s1.is_leader:
        s1.shutdown()
        print("Instance 1 shut down. Instance 2 should take over in next cycle...")
    else:
        s2.shutdown()
        print("Instance 2 shut down. Instance 1 should maintain leadership...")

    await asyncio.sleep(2)
    
    # Final check
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT process_id FROM scheduler_election WHERE role = 'leader'").fetchone()
    print(f"\nCurrent Leader in DB: {row[0]}")
    conn.close()
    
    s1.shutdown()
    s2.shutdown()

if __name__ == "__main__":
    asyncio.run(run_test())
