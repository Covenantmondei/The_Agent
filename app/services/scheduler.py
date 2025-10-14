from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from ..db.models.task import Task
from datetime import datetime

scheduler = BackgroundScheduler()

def check_task_reminders(db: Session):
    """Check and send task reminders"""
    now = datetime.utcnow()
    tasks = db.query(Task).filter(
        Task.reminder_enabled == True,
        Task.reminder_time <= now,
        Task.is_completed == False
    ).all()
    
    for task in tasks:
        # Send notification/email
        print(f"Reminder: {task.title}")

def start_scheduler():
    scheduler.add_job(check_task_reminders, 'interval', minutes=5)
    scheduler.start()