from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional, List


class MeetingCreate(BaseModel):
    meet_link: str
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None


class MeetingResponse(BaseModel):
    id: int
    user_id: int
    calendar_event_id: Optional[str]
    meet_link: str
    title: str
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    is_manual: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TranscriptChunk(BaseModel):
    meeting_id: int
    timestamp: datetime
    text: str
    is_final: bool
    sequence_number: int


class MeetingSummaryResponse(BaseModel):
    id: int
    meeting_id: int
    full_transcript: str
    key_points: Optional[str]
    decisions: Optional[str]
    action_items: Optional[List[str]]
    follow_ups: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class LiveMeetingResponse(BaseModel):
    active_meetings: List[MeetingResponse]
    upcoming_meetings: List[MeetingResponse]