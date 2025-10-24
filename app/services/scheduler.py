from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from datetime import datetime
from ..db.models.task import Task
from ..db.models.user import User
from ..db.session import SessionLocal
from ..utils.notifications import send_task_reminder_email
from ..utils.logger import get_logger
from .summary_service import generate_all_daily_summaries
import logging

logger = get_logger(__name__)

# Reduce APScheduler logging noise
logging.getLogger('apscheduler').setLevel(logging.WARNING)

scheduler = BackgroundScheduler()


def check_due_tasks():
    """
    Background job that runs every minute to check for tasks
    where
    """
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        
        # Find tasks that are due and haven't been notified
        due_tasks = db.query(Task).filter(
            Task.due_date <= now,
            Task.is_notified == False,
            Task.is_completed == False
        ).all()
        
        for task in due_tasks:
            try:
                # Get user for email
                user = db.query(User).filter(User.id == task.user_id).first()
                if user and user.email:
                    # Send notification
                    send_task_reminder_email(
                        to_email=user.email,
                        task_title=task.title,
                        task_description=task.description,
                        due_date=task.due_date
                    )
                    logger.info(f"Sent reminder for task {task.id} to {user.email}")
                
                # Mark as notified
                task.is_notified = True
                db.commit()
                
            except Exception as e:
                logger.error(f"Error sending reminder for task {task.id}: {e}")
                db.rollback()
        
        if due_tasks:
            logger.info(f"Processed {len(due_tasks)} due task reminders")
            
    except Exception as e:
        logger.error(f"Error in check_due_tasks: {e}")
    finally:
        db.close()


def schedule_task_reminder(task_id: int, due_date: datetime, user_email: str):
    try:
        job_id = f"task_reminder_{task_id}"
        
        # Remove existing job if it exists
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        # Only schedule if due_date is in the future
        if due_date > datetime.utcnow():
            scheduler.add_job(
                func=lambda: send_reminder(task_id, user_email),
                trigger=DateTrigger(run_date=due_date),
                id=job_id,
                replace_existing=True
            )
            logger.info(f"Scheduled reminder for task {task_id} at {due_date}")
    except Exception as e:
        logger.error(f"Error scheduling task reminder: {e}")


def send_reminder(task_id: int, user_email: str):
    db: Session = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task and not task.is_completed and not task.is_notified:
            send_task_reminder_email(
                to_email=user_email,
                task_title=task.title,
                task_description=task.description,
                due_date=task.due_date
            )
            task.is_notified = True
            db.commit()
            logger.info(f"Sent scheduled reminder for task {task_id}")
    except Exception as e:
        logger.error(f"Error in send_reminder for task {task_id}: {e}")
    finally:
        db.close()


def start_scheduler():
    try:
        # Check due tasks every minute
        scheduler.add_job(
            func=check_due_tasks,
            trigger='interval',
            minutes=1,
            id='check_due_tasks',
            replace_existing=True
        )
        logger.info("Scheduled: Check due tasks (every minute)")
        
        # Job 2: Generate daily summaries at midnight UTC (1 AM WAT)
        scheduler.add_job(
            func=generate_all_daily_summaries,
            trigger=CronTrigger(hour=0, minute=0),  # Midnight UTC
            id='generate_daily_summaries',
            replace_existing=True
        )
        logger.info("Scheduled: Generate daily summaries (midnight UTC / 1 AM WAT)")
        
        scheduler.start()
        logger.info("Task scheduler started successfully with all jobs")
        
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        raise


def shutdown_scheduler():
    try:
        scheduler.shutdown()
        logger.info("Task scheduler shutdown successfully")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}")