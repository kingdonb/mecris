import logging
import asyncio
import os
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
            
        logger.info(f"Background job (Leader) for {user_id}: Checking for reminders (with fuzz)...")
        result = await trigger_reminder_check(user_id=user_id, apply_fuzz=True)
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
        from mcp_server import scheduler, get_user_beeminder_client
        if not scheduler.is_leader:
            return
            
        beeminder_client = get_user_beeminder_client(user_id)
            
        neon_url = os.getenv("NEON_DB_URL")
        if not neon_url:
            return
            
        import psycopg2
        
        pending_walks = []
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                # We target 'logging' status which is used by the Spin backend
                cur.execute("SELECT id, start_time, step_count, distance_meters, distance_source FROM walk_inferences WHERE status = 'logging' AND user_id = %s", (user_id,))
                rows = cur.fetchall()
                for row in rows:
                    pending_walks.append({
                        'id': row[0],
                        'start_time': row[1],
                        'step_count': row[2],
                        'distance_meters': row[3],
                        'distance_source': row[4]
                    })
        
        if not pending_walks:
            return
            
        logger.info(f"Background job (Leader) for {user_id}: Found {len(pending_walks)} walks to sync. Synchronizing...")
        for walk in pending_walks:
            try:
                # get user configuration
                with psycopg2.connect(neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT beeminder_goal FROM users WHERE pocket_id_sub = %s", (user_id,))
                        row = cur.fetchone()
                        beeminder_goal = row[0] if row else 'bike'
                
                goal = beeminder_goal
                
                # Health Connect distance is the TOTAL for the day so far.
                # We use a daystamp-based request_id so Beeminder overwrites the day's total
                # instead of summing snapshots.
                miles = float(walk['distance_meters']) / 1609.34
                
                # Use US/Eastern daystamp for the request_id to align with Beeminder
                import zoneinfo
                eastern = zoneinfo.ZoneInfo("US/Eastern")
                if isinstance(walk['start_time'], datetime):
                    dt = walk['start_time']
                else:
                    # Parse ISO string if needed
                    from dateutil.parser import parse
                    dt = parse(walk['start_time'])
                
                daystamp = dt.astimezone(eastern).strftime("%Y%m%d")
                request_id = f"{user_id}_{daystamp}"
                
                comment = f"Logged via Mecris MCP Sync (Steps: {walk['step_count']}, Source: {walk['distance_source']})"
                
                # Push (Beeminder handles deduplication/update via requestid)
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

async def _global_archivist_job(user_id: str):
    """
    Background job that fires a ghost archivist pulse every 15 minutes.
    Yields silently when a human session is active.
    """
    try:
        from mcp_server import scheduler
        if not scheduler.is_leader:
            return

        from ghost.archivist import run as archivist_run
        await archivist_run(user_id=user_id)
        logger.info(f"Archivist pulse logged for {user_id}")
    except Exception as e:
        logger.error(f"Archivist job failed for {user_id}: {e}")


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

from services.credentials_manager import credentials_manager

class MecrisScheduler:
    def __init__(self, trigger_reminder_func: Optional[Callable] = None, user_id: str = None):
        self.neon_url = os.getenv("NEON_DB_URL")
        self.user_id = user_id or credentials_manager.resolve_user_id()
        
        # Configure jobstore
        if self.neon_url:
            # APScheduler uses sqlalchemy, so we can use the same URL
            # but we need to replace postgres:// with postgresql:// if needed
            db_url = self.neon_url.replace("postgres://", "postgresql://")
            jobstores = {
                'default': SQLAlchemyJobStore(url=db_url)
            }
        else:
            logger.error("MecrisScheduler: NEON_DB_URL not found. Scheduler will not persist jobs.")
            raise EnvironmentError("NEON_DB_URL must be set for persistent scheduler operation.")
            
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
                logger.error(f"Neon scheduler init failed: {e}. SQLite fallback is disabled.")
                raise ConnectionError(f"Critical error: Neon database is required but unreachable: {e}")
        else:
            raise EnvironmentError("NEON_DB_URL must be set. SQLite fallback is no longer supported.")

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
                            cur.execute("SELECT process_id, heartbeat FROM scheduler_election WHERE user_id = %s AND role = 'leader'", (self.user_id,))
                            row = cur.fetchone()
                            if self.is_leader:
                                if not row or row[0] != self.process_id:
                                    logger.warning(f"🏳️ Process {self.process_id} LOST leadership for {self.user_id} (Neon). Current leader: {row[0] if row else 'None'}")
                                    self.is_leader = False
                                    self._stop_leader_jobs()
                                else:
                                    # We are still leader, maintain heartbeat
                                    cur.execute("UPDATE scheduler_election SET heartbeat = %s WHERE user_id = %s AND role = 'leader' AND process_id = %s", (now, self.user_id, self.process_id))
                                    if attempt % 20 == 0: # Log roughly every 10 minutes
                                        logger.info(f"💓 Leader {self.process_id} heartbeat active.")
                if self.is_leader:
                    await self._start_leader_jobs()
                return
            except Exception as e:
                logger.error(f"Neon leadership attempt failed for {self.user_id}: {e}")

        raise RuntimeError("MecrisScheduler: Neon connection not active. Cannot attempt leadership.")

    async def _start_leader_jobs(self):
        """Register recurring jobs that only the leader should run."""
        for attempt in range(5):
            try:
                # IDs are scoped by user_id
                reminder_job_id = f'auto_reminder_check_{self.user_id}'
                lang_sync_job_id = f'auto_language_sync_{self.user_id}'
                walk_sync_job_id = f'auto_walk_sync_{self.user_id}'
                monitor_job_id = f'auto_cooperative_monitor_{self.user_id}'
                archivist_job_id = f'auto_archivist_{self.user_id}'

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

                if not self.scheduler.get_job(archivist_job_id):
                    self.scheduler.add_job(
                        _global_archivist_job,
                        'interval',
                        minutes=15,
                        id=archivist_job_id,
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
                self.scheduler.remove_job(f'auto_archivist_{self.user_id}')
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
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info(f"Mecris Coordination Engine shut down (PID: {self.process_id}).")
