import pytest
from unittest.mock import MagicMock, patch
import asyncio
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_scheduler_job_replacement_resets_timer_theory():
    """
    Test the theory that calling add_job with replace_existing=True 
    on a frequent loop prevents the job from ever running.
    """
    
    # We'll use a real AsyncIOScheduler but with a very long interval
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.jobstores.memory import MemoryJobStore
    
    jobstores = {'default': MemoryJobStore()}
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    scheduler.start()
    
    counter = 0
    async def my_job():
        nonlocal counter
        counter += 1
        
    # 1. Add job with 1 hour interval
    scheduler.add_job(my_job, 'interval', hours=1, id='test_job')
    
    # 2. Simulate the leader loop: replace it every 0.1 seconds for a bit
    for _ in range(5):
        scheduler.add_job(my_job, 'interval', hours=1, id='test_job', replace_existing=True)
        await asyncio.sleep(0.1)
        
    # 3. Check if it ran (it shouldn't have)
    assert counter == 0
    
    # 4. Now, what if we check the 'next_run_time'?
    job = scheduler.get_job('test_job')
    initial_run_time = job.next_run_time
    
    await asyncio.sleep(0.2)
    scheduler.add_job(my_job, 'interval', hours=1, id='test_job', replace_existing=True)
    
    new_run_time = scheduler.get_job('test_job').next_run_time
    
    # If the timer reset, the new run time should be later than the initial one
    assert new_run_time > initial_run_time
    
    scheduler.shutdown()

@pytest.mark.asyncio
async def test_mecris_scheduler_idempotent_start():
    """
    Verify that our proposed fix (only start jobs if not already started)
    would allow the job to eventually fire.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    scheduler.start()
    
    mock_job = MagicMock()
    
    # Simulate the election loop calling _start_leader_jobs repeatedly
    for _ in range(3):
        # The FIX: Check if job exists before adding
        if not scheduler.get_job('my_id'):
            scheduler.add_job(mock_job, 'interval', seconds=1, id='my_id')
        await asyncio.sleep(0.1)
        
    # Wait for the job to fire
    await asyncio.sleep(1.2)
    assert mock_job.call_count >= 1
    
    scheduler.shutdown()
