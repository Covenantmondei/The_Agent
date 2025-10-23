from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from ..db.models.user import User
from ..services.email_service import GmailService
from ..db.session import SessionLocal
from .logger import get_logger

logger = get_logger(__name__)


def send_task_reminder_email(
    to_email: str,
    task_title: str,
    task_description: Optional[str],
    due_date: datetime
):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == to_email).first()
        
        if not user:
            logger.error(f"User with email {to_email} not found")
            return False
        
        if not user.google_access_token:
            logger.warning(f"User {to_email} doesn't have Gmail connected")
            return False
        
        gmail_service = GmailService(user, db)
        
        due_str = due_date.strftime("%B %d, %Y at %I:%M %p")
        
        # Create HTML email body
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
                    <h2 style="color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px;">
                        ⏰ Task Reminder
                    </h2>
                    <div style="background-color: white; padding: 20px; border-radius: 5px; margin-top: 20px;">
                        <h3 style="color: #007bff; margin-top: 0;">{task_title}</h3>
                        <p style="margin: 10px 0;">
                            <strong>📅 Due:</strong> 
                            <span style="color: #dc3545;">{due_str}</span>
                        </p>
                        {f'<div style="margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #007bff;"><strong>Description:</strong><br>{task_description}</div>' if task_description else ''}
                        <p style="margin-top: 20px; padding: 15px; background-color: #fff3cd; border-radius: 5px;">
                            ⚡ This task is now due. Please complete it at your earliest convenience.
                        </p>
                    </div>
                    <p style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
                        📬 Sent from your Productivity Assistant - Task Manager
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Send email using Gmail API
        subject = f"⏰ Task Reminder: {task_title}"
        
        gmail_service.send_email(
            to=to_email,
            subject=subject,
            body=html_body
        )
        
        logger.info(f"Task reminder sent via Gmail to {to_email} for task: {task_title}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending task reminder via Gmail: {e}")

        # Fallback to console notification
        print(f"\nTASK REMINDER:")
        print(f"To: {to_email}")
        print(f"Task: {task_title}")
        print(f"Due: {due_date.strftime('%B %d, %Y at %I:%M %p')}")
        if task_description:
            print(f"Description: {task_description}")
        return False
    finally:
        db.close()


def send_task_completion_email(to_email: str, task_title: str):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == to_email).first()
        
        if not user or not user.google_access_token:
            logger.warning(f"Cannot send completion email to {to_email} - Gmail not connected")
            return False
        
        gmail_service = GmailService(user, db)
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
                    <h2 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 10px;">
                        ✅ Task Completed!
                    </h2>
                    <div style="background-color: white; padding: 20px; border-radius: 5px; margin-top: 20px;">
                        <p style="font-size: 18px; margin: 0;">
                            <strong style="color: #28a745;">{task_title}</strong>
                        </p>
                        <p style="margin-top: 20px; padding: 15px; background-color: #d4edda; border-radius: 5px; color: #155724;">
                            🎉 Great job! This task has been marked as completed.
                        </p>
                        <p style="margin-top: 15px; color: #666;">
                            Keep up the excellent work staying on top of your tasks!
                        </p>
                    </div>
                    <p style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
                        📬 Sent from your Productivity Assistant - Task Manager
                    </p>
                </div>
            </body>
        </html>
        """
        
        gmail_service.send_email(
            to=to_email,
            subject=f"✅ Task Completed: {task_title}",
            body=html_body
        )
        
        logger.info(f"Task completion email sent via Gmail to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending completion email via Gmail: {e}")
        return False
    finally:
        db.close()


def send_daily_task_summary(to_email: str, stats: dict):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == to_email).first()
        
        if not user or not user.google_access_token:
            logger.warning(f"Cannot send daily summary to {to_email} - Gmail not connected")
            return False
        
        gmail_service = GmailService(user, db)
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
                    <h2 style="color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px;">
                        📊 Daily Task Summary
                    </h2>
                    <div style="background-color: white; padding: 20px; border-radius: 5px; margin-top: 20px;">
                        <div style="display: grid; gap: 15px;">
                            <div style="padding: 15px; background-color: #e3f2fd; border-radius: 5px;">
                                <h3 style="margin: 0; color: #1976d2;">📝 Total Tasks: {stats.get('total', 0)}</h3>
                            </div>
                            <div style="padding: 15px; background-color: #d4edda; border-radius: 5px;">
                                <h3 style="margin: 0; color: #28a745;">✅ Completed: {stats.get('completed', 0)}</h3>
                            </div>
                            <div style="padding: 15px; background-color: #fff3cd; border-radius: 5px;">
                                <h3 style="margin: 0; color: #856404;">⏳ Pending: {stats.get('pending', 0)}</h3>
                            </div>
                            <div style="padding: 15px; background-color: #f8d7da; border-radius: 5px;">
                                <h3 style="margin: 0; color: #721c24;">⚠️ Overdue: {stats.get('overdue', 0)}</h3>
                            </div>
                            <div style="padding: 15px; background-color: #d1ecf1; border-radius: 5px;">
                                <h3 style="margin: 0; color: #0c5460;">📅 Due Today: {stats.get('due_today', 0)}</h3>
                            </div>
                        </div>
                    </div>
                    <p style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
                        📬 Sent from your Productivity Assistant - Task Manager
                    </p>
                </div>
            </body>
        </html>
        """
        
        gmail_service.send_email(
            to=to_email,
            subject="📊 Your Daily Task Summary",
            body=html_body
        )
        
        logger.info(f"Daily task summary sent via Gmail to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending daily summary via Gmail: {e}")
        return False
    finally:
        db.close()