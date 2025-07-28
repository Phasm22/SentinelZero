"""
Scheduler configuration and initialization
"""
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import atexit

def init_scheduler():
    """Initialize and configure the background scheduler"""
    # Ensure instance directory exists
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # Configure job store to persist jobs with absolute path
    jobs_db_path = os.path.join(instance_dir, 'jobs.sqlite')
    jobstores = {
        'default': SQLAlchemyJobStore(url=f'sqlite:///{jobs_db_path}')
    }
    
    job_defaults = {
        'coalesce': False,
        'max_instances': 1
    }
    
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        job_defaults=job_defaults,
        timezone='America/Denver'
    )
    
    # Start the scheduler
    try:
        scheduler.start()
        print(f'[INFO] Scheduler initialized with job store: {jobs_db_path}')
    except Exception as e:
        print(f'[ERROR] Failed to start scheduler: {e}')
        raise
    
    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())
    
    return scheduler
