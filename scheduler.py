import logging
import asyncio
import os
import sqlite3
import uuid
import psycopg2
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Callable, Coroutine
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

logger = logging.getLogger("mecris.scheduler")

# We need a separate task function that doesn't capture the Scheduler instance
# so it can be serialized by SQLAlchemyJobStore
async def _global_reminder_job(trigger_func_name: str, user_id: str):
    """
    Background job that runs on the leader.
    """
    try:
        from mcp_server import trigger_reminder_check, scheduler
        if not scheduler.is_leader:
            return
            
        logger.info(f"Background job (Leader) for {user_id}: Checking for reminders...")
        result = await trigger_reminder_check(user_id=user_id)
        if result.get("triggered"):
            logger.info(f"Reminder sent for {user_id}: {result.get('send', {}).get('method')}")
    except Exception as e:
        logger.error(f"Background reminder job failed for {user_id}: {e}")

async def _global_language_sync_job(user_id: str):
    """
    Background job that syncs Clozemaster stats to Beeminder and Neon DB.
    Now uses a fixed interval for reliability.
    """
    try:
        from mcp_server import scheduler, language_sync_service
        if not scheduler.is_leader:
            return
            
        logger.info(f"Background job (Leader) for {user_id}: Syncing Clozemaster stats to Beeminder...")
        
        # Perform sync
        result = await language_sync_service.sync_all(dry_run=False, user_id=user_id)
        min_safebuf = result.get("min_safebuf", 999)
        logger.info(f"Language sync completed for {user_id} (min safebuf: {min_safebuf})")
                    
    except Exception as e:
        logger.error(f"Clozemaster sync job failed for {user_id}: {e}")

async def _global_walk_sync_job(user_id: str):
    """
    Background job that checks Neon for pending walk inferences and syncs them to Beeminder.
    """
    try:
        from mcp_server import scheduler, beeminder_client
        if not scheduler.is_leader:
            return
            
        neon_url = os.getenv("NEON_DB_URL")
        if not neon_url:
            return
            
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        pending_walks = []
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM walk_inferences WHERE status = 'pending' AND user_id = %s", (user_id,))
                pending_walks = cur.fetchall()
        
        if not pending_walks:
            return
            
        logger.info(f"Background job (Leader) for {user_id}: Found {len(pending_walks)} pending walks. Syncing to Beeminder...")
        for walk in pending_walks:
            try:
                # get user configuration
                with psycopg2.connect(neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("SELECT beeminder_goal FROM users WHERE pocket_id_sub = %s", (user_id,))
                        user = cur.fetchone()
                
                goal = user.get('beeminder_goal', 'bike') if user else 'bike'
                
                miles = float(walk['distance_meters']) / 1609.34
                comment = f"Logged via Mecris MCP Sync (Steps: {walk['step_count']}, Source: {walk['distance_source']})"
                request_id = f"{user_id}_{walk['start_time']}"
                
                # Push
                success = await beeminder_client.add_datapoint(goal, miles, comment=comment, requestid=request_id)
                if success:
                    with psycopg2.connect(neon_url) as conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE walk_inferences SET status = 'logged' WHERE id = %s", (walk['id'],))
                        conn.commit()
            except Exception as e:
                logger.error(f"Failed to sync walk {walk['id']} for user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Neon walk sync job failed for {user_id}: {e}")

async def _global_cooperative_monitor_job(user_id: str):
    """
    Background job that monitors the Android heartbeat and sends alerts if dark for > 4 hours.
    """
    try:
        from mcp_server import scheduler
        if not scheduler.is_leader:
            return
            
        neon_url = os.getenv("NEON_DB_URL")
        if not neon_url:
            return

        import psycopg2
        from psycopg2.extras import RealDictCursor
        from twilio_sender import smart_send_message

        with psycopg2.connect(neon_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Scoped by user_id
                cur.execute("SELECT heartbeat FROM scheduler_election WHERE role = 'android_client' AND user_id = %s", (user_id,))
                row = cur.fetchone()
                
                if row and row['heartbeat']:
                    last_hb = row['heartbeat']
                    if datetime.now(timezone.utc) - last_hb > timedelta(hours=4):
                        logger.warning(f"Android worker for {user_id} is DARK (> 4h). Sending alert.")
                        # Check message log to prevent spamming
                        today = datetime.now().date()
                        cur.execute("SELECT 1 FROM message_log WHERE date = %s AND type = 'android_dark' AND user_id = %s", (today, user_id))
                        if not cur.fetchone():
                            msg = "🤖 Mecris: I haven't heard from your phone's background worker in over 4 hours. Please open the Mecris-Go app to ensure sync is active! 🐕"
                            # Note: smart_send_message needs to be user-aware in the future
                            result = smart_send_message(msg)
                            if result.get("sent"):
                                cur.execute("INSERT INTO message_log (date, type, sent_at, user_id) VALUES (%s, 'android_dark', NOW(), %s)", (today, user_id))
                                conn.commit()
                else:
                    logger.info(f"No android_client heartbeat record found yet for {user_id}.")

    except Exception as e:
        logger.error(f"Cooperative monitor job failed for {user_id}: {e}")

class MecrisScheduler:
    def __init__(self, trigger_reminder_func: Optional[Callable] = None, user_id: str = None):
        self.neon_url = os.getenv("NEON_DB_URL")
        self.db_path = os.getenv("MECRIS_DB_PATH", "mecris_usage.db")
        self.user_id = user_id or os.getenv("DEFAULT_USER_ID")
        
        # Configure jobstore
        if self.neon_url:
            # APScheduler uses sqlalchemy, so we can use the same URL
            # but we need to replace postgres:// with postgresql:// if needed
            db_url = self.neon_url.replace("postgres://", "postgresql://")
            jobstores = {
                'default': SQLAlchemyJobStore(url=db_url)
            }
        else:
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
        if self.neon_url:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS scheduler_election (
                                user_id TEXT,
                                role TEXT,
                                process_id TEXT,
                                heartbeat TIMESTAMP WITH TIME ZONE,
                                PRIMARY KEY (user_id, role)
                            )
                        """)
                        if self.user_id:
                            cur.execute("INSERT INTO scheduler_election (user_id, role) VALUES (%s, 'leader') ON CONFLICT DO NOTHING", (self.user_id,))
                return
            except Exception as e:
                logger.error(f"Neon scheduler init failed: {e}. Falling back to SQLite.")

        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            with conn:
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
        if not self.user_id:
            return

        now = datetime.now(timezone.utc)
        timeout = now - timedelta(seconds=90)
        
        if self.neon_url:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        # 1. Try to claim if slot is empty or stale
                        cur.execute(
                            "UPDATE scheduler_election SET process_id = %s, heartbeat = %s "
                            "WHERE user_id = %s AND role = 'leader' AND (process_id = %s OR heartbeat < %s OR process_id IS NULL)",
                            (self.process_id, now, self.user_id, self.process_id, timeout)
                        )
                        
                        if cur.rowcount > 0:
                            if not self.is_leader:
                                logger.info(f"🏆 Process {self.process_id} ELECTED as Leader for {self.user_id} (Neon).")
                                self.is_leader = True
                        else:
                            # Check if WE are currently the leader
                            cur.execute("SELECT process_id FROM scheduler_election WHERE user_id = %s AND role = 'leader'", (self.user_id,))
                            row = cur.fetchone()
                            if self.is_leader and (not row or row[0] != self.process_id):
                                logger.warning(f"🏳️ Process {self.process_id} lost leadership for {self.user_id} (Neon).")
                                self.is_leader = False
                                self._stop_leader_jobs()
                if self.is_leader:
                    await self._start_leader_jobs()
                return
            except Exception as e:
                logger.error(f"Neon leadership attempt failed for {self.user_id}: {e}")

        # Fallback to SQLite
        conn = sqlite3.connect(self.db_path, timeout=20)
        try:
            with conn:
                cursor = conn.execute(
                    "UPDATE scheduler_election SET process_id = ?, heartbeat = ? "
                    "WHERE role = 'leader' AND (process_id = ? OR heartbeat < ? OR process_id IS NULL)",
                    (self.process_id, now.isoformat(), self.process_id, timeout.isoformat())
                )
                
                if cursor.rowcount > 0:
                    if not self.is_leader:
                        logger.info(f"🏆 Process {self.process_id} ELECTED as Leader (SQLite).")
                        self.is_leader = True
                else:
                    cursor = conn.execute("SELECT process_id FROM scheduler_election WHERE role = 'leader'")
                    row = cursor.fetchone()
                    if self.is_leader and (not row or row[0] != self.process_id):
                        logger.warning(f"🏳️ Process {self.process_id} lost leadership (SQLite).")
                        self.is_leader = False
                        self._stop_leader_jobs()
        except Exception as e:
            logger.error(f"Leadership attempt failed: {e}")
        finally:
            conn.close()

        if self.is_leader:
            await self._start_leader_jobs()

    async def _start_leader_jobs(self):
        """Register recurring jobs that only the leader should run."""
        for attempt in range(5):
            try:
                # IDs are scoped by user_id
                reminder_job_id = f'auto_reminder_check_{self.user_id}'
                lang_sync_job_id = f'auto_language_sync_{self.user_id}'
                walk_sync_job_id = f'auto_walk_sync_{self.user_id}'
                monitor_job_id = f'auto_cooperative_monitor_{self.user_id}'

                if not self.scheduler.get_job(reminder_job_id):
                    self.scheduler.add_job(
                        _global_reminder_job, 
                        'interval', 
                        minutes=30, 
                        id=reminder_job_id,
                        args=['trigger_reminder_check', self.user_id],
                        replace_existing=True
                    )
                
                if not self.scheduler.get_job(lang_sync_job_id):
                    self.scheduler.add_job(
                        _global_language_sync_job,
                        'interval',
                        minutes=60, # Regular interval instead of self-rescheduling
                        id=lang_sync_job_id,
                        args=[self.user_id],
                        replace_existing=True
                    )
                
                if not self.scheduler.get_job(walk_sync_job_id):
                    self.scheduler.add_job(
                        _global_walk_sync_job,
                        'interval',
                        minutes=15,
                        id=walk_sync_job_id,
                        args=[self.user_id],
                        replace_existing=True
                    )

                if not self.scheduler.get_job(monitor_job_id):
                    self.scheduler.add_job(
                        _global_cooperative_monitor_job,
                        'interval',
                        minutes=60,
                        id=monitor_job_id,
                        args=[self.user_id],
                        replace_existing=True
                    )
                break
            except Exception as e:
                if "database is locked" in str(e).lower() and attempt < 4:
                    await asyncio.sleep(1)
                else:
                    if attempt == 4:
                        logger.error(f"Failed to start leader jobs after 5 attempts for {self.user_id}: {e}")
                    break

    def _stop_leader_jobs(self):
        """Remove jobs when leadership is lost."""
        try:
            if self.scheduler.running:
                self.scheduler.remove_job(f'auto_reminder_check_{self.user_id}')
                self.scheduler.remove_job(f'auto_language_sync_{self.user_id}')
                self.scheduler.remove_job(f'auto_walk_sync_{self.user_id}')
                self.scheduler.remove_job(f'auto_cooperative_monitor_{self.user_id}')
        except: pass

    def enqueue_delayed_message(self, message: str, delay_minutes: int, to_number: Optional[str] = None):
        """Enqueue a job into the shared job store."""
        run_time = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
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
                if ("database is locked" in str(e).lower() or "deadlock" in str(e).lower()) and attempt < 4:
                    import time
                    time.sleep(1)
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
            if self.neon_url:
                try:
                    with psycopg2.connect(self.neon_url) as conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE scheduler_election SET process_id = NULL WHERE user_id = %s AND process_id = %s", (self.user_id, self.process_id))
                except: pass
            else:
                try:
                    conn = sqlite3.connect(self.db_path, timeout=5)
                    with conn:
                        conn.execute("UPDATE scheduler_election SET process_id = NULL WHERE process_id = ?", (self.process_id,))
                    conn.close()
                except: pass
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info(f"Mecris Coordination Engine shut down (PID: {self.process_id}).")
