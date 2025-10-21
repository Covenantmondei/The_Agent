from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class EmailActionItemCreate(BaseModel):
    action_text: str


class EmailActionItemResponse(BaseModel):
    id: int
    action_text: str
    is_completed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class EmailSummaryCreate(BaseModel):
    gmail_message_id: str
    subject: str
    sender: str
    summary: str
    drafted_reply: Optional[str] = None
    category: Optional[str] = None


class EmailSummaryResponse(BaseModel):
    id: int
    gmail_message_id: str
    subject: str
    sender: str
    summary: str
    drafted_reply: Optional[str]
    category: Optional[str]
    is_read: bool
    reply_sent: bool
    action_items: List[EmailActionItemResponse] = []
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProcessEmailRequest(BaseModel):
    message_id: str


class SendReplyRequest(BaseModel):
    email_summary_id: int
    custom_reply: Optional[str] = None  # If provided, use this instead of drafted reply