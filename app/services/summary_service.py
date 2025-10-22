from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, date, timedelta
import pytz
from typing import Dict, List
from ..db.models.summary import DailySummary
from ..db.models.task import Task
from ..db.models.calendar import CalendarEvent
from ..db.models.email_manage import EmailSummary
from ..db.models.user import User
from ..db.session import SessionLocal
from ..utils.logger import get_logger
from ..utils.notifications import send_daily_task_summary
from .email_service import GmailService

logger = get_logger(__name__)

WAT = pytz.timezone('Africa/Lagos')


class SummaryService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_wat_date(self) -> date:
        return datetime.now(WAT).date()
    
    def get_wat_day_range(self, target_date: date = None) -> tuple:
        if not target_date:
            target_date = self.get_wat_date()
        
        # Start of day in WAT
        start = WAT.localize(datetime.combine(target_date, datetime.min.time()))
        # End of day in WAT
        end = WAT.localize(datetime.combine(target_date, datetime.max.time()))
        
        # Convert to UTC for database queries
        start_utc = start.astimezone(pytz.UTC)
        end_utc = end.astimezone(pytz.UTC)
        
        return start_utc, end_utc
    
    def collect_user_daily_stats(self, user: User, target_date: date = None) -> Dict:
        try:
            if not target_date:
                target_date = self.get_wat_date()
            
            day_start, day_end = self.get_wat_day_range(target_date)
            
            # Task statistics
            total_tasks = self.db.query(Task).filter(
                Task.user_id == user.id,
                Task.created_at <= day_end
            ).count()
            
            completed_tasks = self.db.query(Task).filter(
                and_(
                    Task.user_id == user.id,
                    Task.is_completed == True,
                    Task.updated_at >= day_start,
                    Task.updated_at <= day_end
                )
            ).count()
            
            pending_tasks = self.db.query(Task).filter(
                and_(
                    Task.user_id == user.id,
                    Task.is_completed == False
                )
            ).count()
            
            overdue_tasks = self.db.query(Task).filter(
                and_(
                    Task.user_id == user.id,
                    Task.is_completed == False,
                    Task.due_date < datetime.now(pytz.UTC),
                    Task.due_date.isnot(None)
                )
            ).count()
            
            # Calendar statistics - meetings that occurred today
            meetings_count = self.db.query(CalendarEvent).filter(
                and_(
                    CalendarEvent.user_id == user.id,
                    CalendarEvent.start_time >= day_start,
                    CalendarEvent.start_time <= day_end
                )
            ).count()
            
            # Email statistics - emails processed today
            emails_processed = self.db.query(EmailSummary).filter(
                and_(
                    EmailSummary.user_id == user.id,
                    EmailSummary.created_at >= day_start,
                    EmailSummary.created_at <= day_end
                )
            ).count()
            
            # TODO:
            # Emails sent (would need tracking in your email service)
            # For now, we'll set it to 0 or estimate based on processed emails
            emails_sent = 0
            
            return {
                'user_id': user.id,
                'target_date': target_date,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'pending_tasks': pending_tasks,
                'overdue_tasks': overdue_tasks,
                'meetings_count': meetings_count,
                'emails_processed': emails_processed,
                'emails_sent': emails_sent
            }
            
        except Exception as e:
            logger.error(f"Error collecting stats for user {user.id}: {e}")
            raise
    
    def generate_summary_text(self, stats: Dict) -> str:
        try:
            completed = stats['completed_tasks']
            total = stats['total_tasks']
            meetings = stats['meetings_count']
            emails = stats['emails_processed']
            overdue = stats['overdue_tasks']
            
            # Build dynamic summary
            parts = []
            
            # Task summary
            if completed > 0:
                if total > 0:
                    parts.append(f"You completed {completed} out of {total} tasks")
                else:
                    parts.append(f"You completed {completed} task{'s' if completed != 1 else ''}")
            elif total > 0:
                parts.append(f"You have {total} task{'s' if total != 1 else ''} in your list")
            
            # Meeting summary
            if meetings > 0:
                parts.append(f"attended {meetings} meeting{'s' if meetings != 1 else ''}")
            
            # Email summary
            if emails > 0:
                parts.append(f"processed {emails} email{'s' if emails != 1 else ''}")
            
            # Build final message
            if parts:
                summary = ", ".join(parts) + " today"
                # Capitalize first letter
                summary = summary[0].upper() + summary[1:] + "."
            else:
                summary = "No activity recorded today. Time to get productive!"
            
            # Add encouragement
            if completed > 0 or meetings > 0 or emails > 0:
                if completed >= 5 or meetings >= 3:
                    summary += " Excellent work! 🎉"
                elif completed >= 3 or meetings >= 2:
                    summary += " Great job! 👏"
                else:
                    summary += " Keep it up! 💪"
            
            # Add warning for overdue tasks
            if overdue > 0:
                summary += f" Note: You have {overdue} overdue task{'s' if overdue != 1 else ''}. ⚠️"
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary text: {e}")
            return "Summary generation failed."
    
    def create_or_update_daily_summary(self, user: User, target_date: date = None) -> DailySummary:
        try:
            if not target_date:
                target_date = self.get_wat_date()
            
            # Collect stats
            stats = self.collect_user_daily_stats(user, target_date)
            
            # Generate summary text
            summary_text = self.generate_summary_text(stats)
            
            # Check if summary already exists for this date
            existing_summary = self.db.query(DailySummary).filter(
                and_(
                    DailySummary.user_id == user.id,
                    DailySummary.summary_date == target_date
                )
            ).first()
            
            if existing_summary:
                # Update existing summary
                existing_summary.total_tasks = stats['total_tasks']
                existing_summary.completed_tasks = stats['completed_tasks']
                existing_summary.pending_tasks = stats['pending_tasks']
                existing_summary.overdue_tasks = stats['overdue_tasks']
                existing_summary.meetings_count = stats['meetings_count']
                existing_summary.emails_processed = stats['emails_processed']
                existing_summary.emails_sent = stats['emails_sent']
                existing_summary.summary_text = summary_text
                existing_summary.updated_at = datetime.now(WAT)
                
                self.db.commit()
                self.db.refresh(existing_summary)
                
                logger.info(f"Updated daily summary for user {user.id} on {target_date}")
                return existing_summary
            else:
                # Create new summary
                new_summary = DailySummary(
                    user_id=user.id,
                    summary_date=target_date,
                    total_tasks=stats['total_tasks'],
                    completed_tasks=stats['completed_tasks'],
                    pending_tasks=stats['pending_tasks'],
                    overdue_tasks=stats['overdue_tasks'],
                    meetings_count=stats['meetings_count'],
                    emails_processed=stats['emails_processed'],
                    emails_sent=stats['emails_sent'],
                    summary_text=summary_text
                )
                
                self.db.add(new_summary)
                self.db.commit()
                self.db.refresh(new_summary)
                
                logger.info(f"Created daily summary for user {user.id} on {target_date}")
                return new_summary
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating/updating summary for user {user.id}: {e}")
            raise
    
    def get_user_summary(self, user: User, target_date: date = None) -> DailySummary:
        try:
            if not target_date:
                target_date = self.get_wat_date()
            
            summary = self.db.query(DailySummary).filter(
                and_(
                    DailySummary.user_id == user.id,
                    DailySummary.summary_date == target_date
                )
            ).first()
            
            return summary
            
        except Exception as e:
            logger.error(f"Error retrieving summary for user {user.id}: {e}")
            raise
    
    def get_user_summaries_range(self, user: User, start_date: date, end_date: date) -> List[DailySummary]:
        try:
            summaries = self.db.query(DailySummary).filter(
                and_(
                    DailySummary.user_id == user.id,
                    DailySummary.summary_date >= start_date,
                    DailySummary.summary_date <= end_date
                )
            ).order_by(DailySummary.summary_date.desc()).all()
            
            return summaries
            
        except Exception as e:
            logger.error(f"Error retrieving summary range for user {user.id}: {e}")
            raise


def generate_all_daily_summaries():
    """
    Background job to generate daily summaries for all users
    Runs at midnight UTC (1 AM WAT)
    """
    db: Session = SessionLocal()
    try:
        logger.info("Starting daily summary generation job...")
        
        # Get yesterday's date in WAT (since this runs at midnight UTC = 1 AM WAT)
        wat_now = datetime.now(WAT)
        # If it's early morning (before 6 AM), generate for yesterday
        if wat_now.hour < 6:
            target_date = (wat_now - timedelta(days=1)).date()
        else:
            target_date = wat_now.date()
        
        logger.info(f"Generating summaries for date: {target_date}")
        
        # Get all active users
        users = db.query(User).filter(User.is_active == True).all()
        
        summary_service = SummaryService(db)
        success_count = 0
        error_count = 0
        
        for user in users:
            try:
                # Generate summary
                summary = summary_service.create_or_update_daily_summary(user, target_date)
                
                # Send email notification
                if user.email and user.google_access_token:
                    try:
                        stats = {
                            'total': summary.total_tasks,
                            'completed': summary.completed_tasks,
                            'pending': summary.pending_tasks,
                            'overdue': summary.overdue_tasks,
                            'due_today': 0  # Not applicable for past day
                        }
                        send_daily_task_summary(user.email, stats)
                        logger.info(f"Sent daily summary email to {user.email}")
                    except Exception as email_error:
                        logger.warning(f"Failed to send summary email to {user.email}: {email_error}")
                
                success_count += 1
                logger.info(f"Generated summary for user {user.id}: {summary.summary_text}")
                
            except Exception as user_error:
                error_count += 1
                logger.error(f"Error generating summary for user {user.id}: {user_error}")
                continue
        
        logger.info(f"Daily summary job completed. Success: {success_count}, Errors: {error_count}")
        
    except Exception as e:
        logger.error(f"Critical error in daily summary job: {e}")
    finally:
        db.close()