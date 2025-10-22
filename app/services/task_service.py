from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from typing import List, Optional
from ..db.models.task import Task
from ..db.models.user import User
from ..schemas.task import TaskCreate, TaskUpdate, TaskStats
from ..utils.logger import get_logger
from .scheduler import schedule_task_reminder

logger = get_logger(__name__)

class TaskService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
    
    def create_task(self, task_data: TaskCreate) -> Task:
        try:
            task = Task(
                user_id=self.user.id,
                title=task_data.title,
                description=task_data.description,
                due_date=task_data.due_date,
                priority=task_data.priority or "medium"
            )
            
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            
            if task.due_date:
                schedule_task_reminder(task.id, task.due_date, self.user.email)
                logger.info(f"Scheduled reminder for task {task.id} at {task.due_date}")
            
            logger.info(f"Task created: {task.id} - {task.title}")
            return task
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating task: {e}")
            raise
    
    def get_tasks(
        self,
        skip: int = 0,
        limit: int = 20,
        filter_type: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Task]:
        try:
            query = self.db.query(Task).filter(Task.user_id == self.user.id)
            
            if filter_type == "due_today":
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + timedelta(days=1)
                query = query.filter(
                    and_(
                        Task.due_date >= today_start,
                        Task.due_date < today_end,
                        Task.is_completed == False
                    )
                )
            elif filter_type == "overdue":
                query = query.filter(
                    and_(
                        Task.due_date < datetime.utcnow(),
                        Task.is_completed == False
                    )
                )
            elif filter_type == "completed":
                query = query.filter(Task.is_completed == True)
            elif filter_type == "pending":
                query = query.filter(Task.is_completed == False)
            
            if priority:
                query = query.filter(Task.priority == priority)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Task.title.ilike(search_term),
                        Task.description.ilike(search_term)
                    )
                )
            
            query = query.order_by(
                Task.due_date.asc().nullslast(),
                Task.created_at.desc()
            )
            
            tasks = query.offset(skip).limit(limit).all()
            logger.info(f"Retrieved {len(tasks)} tasks with filter: {filter_type}")
            return tasks
            
        except Exception as e:
            logger.error(f"Error retrieving tasks: {e}")
            raise
    
    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        try:
            task = self.db.query(Task).filter(
                and_(
                    Task.id == task_id,
                    Task.user_id == self.user.id
                )
            ).first()
            
            if not task:
                logger.warning(f"Task {task_id} not found for user {self.user.id}")
            
            return task
            
        except Exception as e:
            logger.error(f"Error retrieving task {task_id}: {e}")
            raise
    
    def update_task(self, task_id: int, task_data: TaskUpdate) -> Optional[Task]:
        try:
            task = self.get_task_by_id(task_id)
            if not task:
                return None
            
            update_data = task_data.dict(exclude_unset=True)
            
            for field, value in update_data.items():
                setattr(task, field, value)
            
            task.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(task)
            
            if 'due_date' in update_data and task.due_date:
                schedule_task_reminder(task.id, task.due_date, self.user.email)
                logger.info(f"Rescheduled reminder for task {task.id}")
            
            logger.info(f"Task updated: {task.id}")
            return task
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating task {task_id}: {e}")
            raise
    
    def delete_task(self, task_id: int) -> bool:
        try:
            task = self.get_task_by_id(task_id)
            if not task:
                return False
            
            self.db.delete(task)
            self.db.commit()
            
            logger.info(f"Task deleted: {task_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting task {task_id}: {e}")
            raise
    
    def mark_as_completed(self, task_id: int) -> Optional[Task]:
        try:
            task = self.get_task_by_id(task_id)
            if not task:
                return None
            
            task.is_completed = True
            task.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(task)
            
            logger.info(f"Task marked as completed: {task_id}")
            return task
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error marking task as completed {task_id}: {e}")
            raise
    
    def get_task_stats(self) -> TaskStats:
        try:
            total = self.db.query(Task).filter(Task.user_id == self.user.id).count()
            completed = self.db.query(Task).filter(
                and_(Task.user_id == self.user.id, Task.is_completed == True)
            ).count()
            pending = total - completed
            
            overdue = self.db.query(Task).filter(
                and_(
                    Task.user_id == self.user.id,
                    Task.due_date < datetime.utcnow(),
                    Task.is_completed == False
                )
            ).count()
            
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            due_today = self.db.query(Task).filter(
                and_(
                    Task.user_id == self.user.id,
                    Task.due_date >= today_start,
                    Task.due_date < today_end,
                    Task.is_completed == False
                )
            ).count()
            
            return TaskStats(
                total=total,
                completed=completed,
                pending=pending,
                overdue=overdue,
                due_today=due_today
            )
            
        except Exception as e:
            logger.error(f"Error getting task stats: {e}")
            raise