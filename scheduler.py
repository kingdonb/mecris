import logging
import asyncio
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Coroutine
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger("mecris.scheduler")

class MecrisScheduler:
    def __init__(self, trigger_reminder_func: Callable[[], Coroutine[Any, Any, Dict[str, Any]]]):
        self.scheduler = AsyncIOScheduler()
        self.trigger_reminder_func = trigger_reminder_func
        self.is_started = False

    def start(self):
        if not self.is_started:
            # Add recurring jobs
            self.scheduler.add_job(
                self._safe_trigger_reminder, 
                'interval', 
                minutes=30, 
                id='auto_reminder_check',
                replace_existing=True
            )
            self.scheduler.start()
            self.is_started = True
            logger.info("Mecris Background Scheduler started.")

    async def _safe_trigger_reminder(self):
        """Job wrapper to handle exceptions."""
        try:
            logger.info("Background job: Checking for reminders...")
            result = await self.trigger_reminder_func()
            if result.get("triggered"):
                logger.info(f"Background reminder sent: {result.get('send', {}).get('method')}")
            else:
                logger.info(f"No reminder needed: {result.get('reason')}")
        except Exception as e:
            logger.error(f"Background job failed: {e}")

    def enqueue_delayed_message(self, message: str, delay_minutes: int, to_number: Optional[str] = None):
        """Sidekiq-like delayed execution for messages."""
        run_time = datetime.now() + timedelta(minutes=delay_minutes)
        job_id = f"delayed_msg_{int(run_time.timestamp())}"
        
        from twilio_sender import smart_send_message
        
        self.scheduler.add_job(
            smart_send_message,
            trigger=DateTrigger(run_at=run_time),
            args=[message, to_number],
            id=job_id
        )
        logger.info(f"Enqueued delayed message in {delay_minutes}m (at {run_time.isoformat()})")
        return {"job_id": job_id, "run_at": run_time.isoformat()}

    def shutdown(self):
        if self.is_started:
            self.scheduler.shutdown()
            self.is_started = False
            logger.info("Mecris Background Scheduler shut down.")
