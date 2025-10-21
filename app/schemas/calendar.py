from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class CalendarEventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    attendees: Optional[List[str]] = None
    timezone: Optional[str] = 'UTC'
    add_meet_link: bool = False

class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    attendees: Optional[List[str]] = None

class CalendarEventResponse(BaseModel):
    id: int
    google_event_id: str
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    location: Optional[str]
    
    class Config:
        from_attributes = True

class MeetingFromEmailRequest(BaseModel):
    email_sender: str
    subject: str
    suggested_time: Optional[datetime] = None
    duration_minutes: Optional[int] = 60
    description: Optional[str] = None

class FreeSlotsRequest(BaseModel):
    date: datetime
    duration_minutes: Optional[int] = 60
    working_hours_start: Optional[int] = 9
    working_hours_end: Optional[int] = 17