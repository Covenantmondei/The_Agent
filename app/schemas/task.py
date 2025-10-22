from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = Field(default="medium", pattern="^(low|medium|high)$")

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    is_completed: Optional[bool] = None

class TaskResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    is_completed: bool
    is_notified: bool
    priority: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TaskStats(BaseModel):
    total: int
    completed: int
    pending: int
    overdue: int
    due_today: int