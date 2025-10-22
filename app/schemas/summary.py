from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional

class DailySummaryResponse(BaseModel):
    id: int
    user_id: int
    summary_date: date
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    overdue_tasks: int
    meetings_count: int
    emails_processed: int
    emails_sent: int
    summary_text: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SummaryRangeResponse(BaseModel):
    summaries: list[DailySummaryResponse]
    total_count: int