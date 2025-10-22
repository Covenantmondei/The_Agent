from ..base import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime
import pytz

# WAT timezone
WAT = pytz.timezone('Africa/Lagos')

class DailySummary(Base):
    __tablename__ = "daily_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    summary_date = Column(Date, nullable=False, index=True)  # Date in WAT
    
    # Task stats
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    pending_tasks = Column(Integer, default=0)
    overdue_tasks = Column(Integer, default=0)
    
    # Calendar stats
    meetings_count = Column(Integer, default=0)
    
    # Email stats
    emails_processed = Column(Integer, default=0)
    emails_sent = Column(Integer, default=0)
    
    # Human-readable summary
    summary_text = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(WAT))
    updated_at = Column(DateTime, default=lambda: datetime.now(WAT), onupdate=lambda: datetime.now(WAT))
    
    user = relationship("User", back_populates="daily_summaries")
    
    def __repr__(self):
        return f"<DailySummary(user_id={self.user_id}, date={self.summary_date})>"