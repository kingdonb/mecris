import logging
import asyncio
import os
import sqlite3
import uuid
import psycopg2
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

async def _global_language_sync_job():
    """
    Background job that syncs Clozemaster stats to Beeminder and Neon DB.
    """
    try:
        from mcp_server import scheduler
        if not scheduler.is_leader:
            return
            
        logger.info("Background job (Leader): Syncing Clozemaster stats to Beeminder...")
        from scripts.clozemaster_scraper import sync_clozemaster_to_beeminder
        
        # Scrape and push to Beeminder
        scraper_data = await sync_clozemaster_to_beeminder(dry_run=False)
        
        # Also update Neon database so the Android app gets fresh data
        if scraper_data:
            neon_url = os.getenv("NEON_DB_URL")
            if neon_url:
                try:
                    with psycopg2.connect(neon_url) as conn:
                        with conn.cursor() as cur:
                            for lang, data in scraper_data.items():
                                name = lang.upper()
                                count = data.get("count", 0)
                                forecast = data.get("forecast", {})
                                tomorrow = forecast.get("tomorrow", 0)
                                next_7 = forecast.get("next_7_days", 0)
                                
                                cur.execute("""
                                    INSERT INTO language_stats (language_name, current_reviews, tomorrow_reviews, next_7_days_reviews)
                                    VALUES (%s, %s, %s, %s)
                                    ON CONFLICT (language_name) DO UPDATE SET
                                        current_reviews = EXCLUDED.current_reviews,
                                        tomorrow_reviews = EXCLUDED.tomorrow_reviews,
                                        next_7_days_reviews = EXCLUDED.next_7_days_reviews,
                                        last_updated = CURRENT_TIMESTAMP
                                """, (name, count, tomorrow, next_7))
                            conn.commit()
                except Exception as e:
                    logger.error(f"Failed to update Neon DB with language stats: {e}")
                    
    except Exception as e:
        logger.error(f"Clozemaster sync job failed: {e}")

async def _global_walk_sync_job():
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
                cur.execute("SELECT * FROM walk_inferences WHERE status = 'pending'")
                pending_walks = cur.fetchall()
        
        if not pending_walks:
            return
            
        logger.info(f"Background job (Leader): Found {len(pending_walks)} pending walks. Syncing to Beeminder...")
        for walk in pending_walks:
            try:
                # get user configuration
                with psycopg2.connect(neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("SELECT beeminder_goal FROM users WHERE pocket_id_sub = %s", (walk['user_id'],))
                        user = cur.fetchone()
                
                goal = user.get('beeminder_goal', 'bike') if user else 'bike'
                
                miles = float(walk['distance_meters']) / 1609.34
                comment = f"Logged via Mecris MCP Sync (Steps: {walk['step_count']}, Source: {walk['distance_source']})"
                request_id = f"{walk['user_id']}_{walk['start_time']}"
                
                # Push
                success = await beeminder_client.add_datapoint(goal, miles, comment=comment, requestid=request_id)
                if success:
                    with psycopg2.connect(neon_url) as conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE walk_inferences SET status = 'logged' WHERE id = %s", (walk['id'],))
                        conn.commit()
            except Exception as e:
                logger.error(f"Failed to sync walk {walk['id']}: {e}")

    except Exception as e:
        logger.error(f"Neon walk sync job failed: {e}")

class MecrisScheduler:
    def __init__(self, trigger_reminder_func: Optional[Callable] = None):
        self.neon_url = os.getenv("NEON_DB_URL")
        self.db_path = os.getenv("MECRIS_DB_PATH", "mecris_usage.db")
        
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
                                role TEXT PRIMARY KEY,
                                process_id TEXT,
                                heartbeat TIMESTAMP WITH TIME ZONE
                            )
                        """)
                        cur.execute("INSERT INTO scheduler_election (role) VALUES ('leader') ON CONFLICT DO NOTHING")
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
        now = datetime.now()
        timeout = now - timedelta(seconds=90)
        
        if self.neon_url:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        # 1. Try to claim if slot is empty or stale
                        cur.execute(
                            "UPDATE scheduler_election SET process_id = %s, heartbeat = %s "
                            "WHERE role = 'leader' AND (process_id = %s OR heartbeat < %s OR process_id IS NULL)",
                            (self.process_id, now, self.process_id, timeout)
                        )
                        
                        if cur.rowcount > 0:
                            if not self.is_leader:
                                logger.info(f"🏆 Process {self.process_id} ELECTED as Leader (Neon).")
                                self.is_leader = True
                        else:
                            # Check if WE are currently the leader
                            cur.execute("SELECT process_id FROM scheduler_election WHERE role = 'leader'")
                            row = cur.fetchone()
                            if self.is_leader and (not row or row[0] != self.process_id):
                                logger.warning(f"🏳️ Process {self.process_id} lost leadership (Neon).")
                                self.is_leader = False
                                self._stop_leader_jobs()
                if self.is_leader:
                    await self._start_leader_jobs()
                return
            except Exception as e:
                logger.error(f"Neon leadership attempt failed: {e}")

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
                self.scheduler.add_job(
                    _global_reminder_job, 
                    'interval', 
                    minutes=30, 
                    id='auto_reminder_check',
                    args=['trigger_reminder_check'],
                    replace_existing=True
                )
                self.scheduler.add_job(
                    _global_language_sync_job,
                    'interval',
                    hours=4,
                    id='auto_language_sync',
                    replace_existing=True
                )
                self.scheduler.add_job(
                    _global_walk_sync_job,
                    'interval',
                    minutes=15,
                    id='auto_walk_sync',
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
                self.scheduler.remove_job('auto_language_sync')
                self.scheduler.remove_job('auto_walk_sync')
        except: pass

    def enqueue_delayed_message(self, message: str, delay_minutes: int, to_number: Optional[str] = None):
        """Enqueue a job into the shared job store."""
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
                            cur.execute("UPDATE scheduler_election SET process_id = NULL WHERE process_id = %s", (self.process_id,))
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
