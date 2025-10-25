from ..base import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime


class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    calendar_event_id = Column(String, nullable=True)
    meet_link = Column(String, nullable=False)
    title = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="scheduled")
    is_manual = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="meetings")
    transcripts = relationship("MeetingTranscript", back_populates="meeting", cascade="all, delete-orphan")
    summary = relationship("MeetingSummary", back_populates="meeting", uselist=False, cascade="all, delete-orphan")


class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    speaker = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    is_final = Column(Boolean, default=False)
    sequence_number = Column(Integer, nullable=False)
    
    # Relationships
    meeting = relationship("Meeting", back_populates="transcripts")


class MeetingSummary(Base):
    __tablename__ = "meeting_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    full_transcript = Column(Text, nullable=False)
    key_points = Column(Text, nullable=True)
    decisions = Column(Text, nullable=True)
    action_items = Column(JSON, nullable=True)
    follow_ups = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    meeting = relationship("Meeting", back_populates="summary")