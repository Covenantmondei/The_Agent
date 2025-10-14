from ..base import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

class EmailSummary(Base):
    __tablename__ = "email_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    gmail_message_id = Column(String, unique=True, nullable=False)
    thread_id = Column(String, nullable=True)
    subject = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    email_body = Column(Text, nullable=True)
    summary = Column(Text, nullable=False)
    drafted_reply = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    reply_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="email_summaries")
    action_items = relationship("EmailActionItem", back_populates="email", cascade="all, delete-orphan")


class EmailActionItem(Base):
    __tablename__ = "email_action_items"
    
    id = Column(Integer, primary_key=True, index=True)
    email_summary_id = Column(Integer, ForeignKey("email_summaries.id"), nullable=False)
    action_text = Column(Text, nullable=False)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    email = relationship("EmailSummary", back_populates="action_items")