import logging
import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Coroutine
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

logger = logging.getLogger("mecris.scheduler")

# We need a separate task function that doesn't capture the Scheduler instance
# so it can be serialized by SQLAlchemyJobStore
async def _global_reminder_job(trigger_func_name: str):
    """
    Background job that runs on the leader.
    Since we can't easily serialize the coroutine object, we'll
    import the trigger from mcp_server inside the job.
    """
    try:
        from mcp_server import trigger_reminder_check, scheduler
        if not scheduler.is_leader:
            return
            
        logger.info("Background job (Leader): Checking for reminders...")
        result = await trigger_reminder_check()
        if result.get("triggered"):
            logger.info(f"Reminder sent: {result.get('send', {}).get('method')}")
    except Exception as e:
        logger.error(f"Background job failed: {e}")

class MecrisScheduler:
    def __init__(self, trigger_reminder_func: Optional[Callable] = None):
        self.db_path = os.getenv("MECRIS_DB_PATH", "mecris_usage.db")
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=f'sqlite:///{self.db_path}',
                engine_options={'connect_args': {'timeout': 15}}
            )
        }
        job_defaults = {
            'misfire_grace_time': 3600
        }
        self.scheduler = AsyncIOScheduler(jobstores=jobstores, job_defaults=job_defaults)
        self.process_id = str(uuid.uuid4())[:8]
        self.is_leader = False
        self.running = False
        self._election_task = None

    def start(self):
        """Start the coordination engine."""
        if not self.running:
            self._init_db()
            self.running = True
            self._election_task = asyncio.create_task(self._election_loop())
            self.scheduler.start()
            logger.info(f"Mecris Coordination Engine started (PID: {self.process_id}).")

    def _init_db(self):
        """Initialize the coordination tables."""
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            with conn:
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scheduler_election (
                        role TEXT PRIMARY KEY,
                        process_id TEXT,
                        heartbeat TIMESTAMP
                    )
                """)
                conn.execute("INSERT OR IGNORE INTO scheduler_election VALUES ('leader', NULL, NULL)")
        finally:
            conn.close()

    async def _election_loop(self):
        """Continuous leader election and heartbeat."""
        while self.running:
            try:
                await self._attempt_leadership()
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Election error: {e}")
                await asyncio.sleep(5)

    async def _attempt_leadership(self):
        """Try to claim or maintain the leader role."""
        # Use a longer timeout for the DB connect to handle contention
        conn = sqlite3.connect(self.db_path, timeout=20)
        now = datetime.now()
        timeout = now - timedelta(seconds=90)
        
        try:
            with conn:
                # 1. Try to claim if slot is empty or stale
                cursor = conn.execute(
                    "UPDATE scheduler_election SET process_id = ?, heartbeat = ? "
                    "WHERE role = 'leader' AND (process_id = ? OR heartbeat < ? OR process_id IS NULL)",
                    (self.process_id, now.isoformat(), self.process_id, timeout.isoformat())
                )
                
                if cursor.rowcount > 0:
                    if not self.is_leader:
                        logger.info(f"🏆 Process {self.process_id} ELECTED as Leader.")
                        self.is_leader = True
                        # Need to run this outside the transaction lock to avoid deadlocks
                else:
                    # Check if WE are currently the leader in DB but update failed (someone else took it)
                    cursor = conn.execute("SELECT process_id FROM scheduler_election WHERE role = 'leader'")
                    row = cursor.fetchone()
                    if self.is_leader and (not row or row[0] != self.process_id):
                        logger.warning(f"🏳️ Process {self.process_id} lost leadership.")
                        self.is_leader = False
                        self._stop_leader_jobs()
        except Exception as e:
            logger.error(f"Leadership attempt failed: {e}")
        finally:
            conn.close()

        # Call this outside the DB lock to prevent contention
        if self.is_leader:
            await self._start_leader_jobs()

    async def _start_leader_jobs(self):
        """Register recurring jobs that only the leader should run."""
        # Use the global function for serialization safety
        for attempt in range(5):
            try:
                self.scheduler.add_job(
                    _global_reminder_job, 
                    'interval', 
                    minutes=30, 
                    id='auto_reminder_check',
                    args=['trigger_reminder_check'],
                    replace_existing=True
                )
                break
            except Exception as e:
                if "database is locked" in str(e).lower() and attempt < 4:
                    await asyncio.sleep(1)
                else:
                    if attempt == 4:
                        logger.error(f"Failed to start leader jobs after 5 attempts: {e}")
                    break

    def _stop_leader_jobs(self):
        """Remove jobs when leadership is lost."""
        try:
            if self.scheduler.running:
                self.scheduler.remove_job('auto_reminder_check')
        except: pass

    def enqueue_delayed_message(self, message: str, delay_minutes: int, to_number: Optional[str] = None):
        """Enqueue a job into the shared SQLite store."""
        run_time = datetime.now() + timedelta(minutes=delay_minutes)
        job_id = f"msg_{int(run_time.timestamp())}_{self.process_id}"
        
        from twilio_sender import smart_send_message
        
        for attempt in range(5):
            try:
                self.scheduler.add_job(
                    smart_send_message,
                    trigger=DateTrigger(run_date=run_time),
                    args=[message, to_number],
                    id=job_id
                )
                logger.info(f"Enqueued delayed message at {run_time.isoformat()} (ID: {job_id})")
                return {"job_id": job_id, "run_at": run_time.isoformat(), "leader": self.is_leader}
            except Exception as e:
                if "database is locked" in str(e).lower() and attempt < 4:
                    import time
                    time.sleep(1) # Safe here since it's a sync function
                else:
                    logger.error(f"Failed to enqueue message: {e}")
                    return {"error": str(e), "leader": self.is_leader}
        
        return {"error": "Failed to enqueue after retries", "leader": self.is_leader}

    def get_queue(self):
        """View all pending jobs in the shared store."""
        try:
            jobs = self.scheduler.get_jobs()
            return [
                {
                    "id": j.id, 
                    "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
                    "func": j.func_ref
                } 
                for j in jobs
            ]
        except:
            return []

    def shutdown(self):
        self.running = False
        if self._election_task:
            self._election_task.cancel()
        if self.is_leader:
            try:
                conn = sqlite3.connect(self.db_path, timeout=5)
                with conn:
                    conn.execute("UPDATE scheduler_election SET process_id = NULL WHERE process_id = ?", (self.process_id,))
                conn.close()
            except: pass
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info(f"Mecris Coordination Engine shut down (PID: {self.process_id}).")
