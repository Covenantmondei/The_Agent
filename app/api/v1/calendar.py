from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
from ...services.calendar_service import GoogleCalendarService
from ...services.auth import user_dependency
from ...db.base import db_dependency
from ...schemas.calendar import CalendarEventCreate, CalendarEventUpdate, CalendarEventResponse, MeetingFromEmailRequest, FreeSlotsRequest


router = APIRouter(prefix='/calendar', tags=['calendar'])


@router.get("/calendars")
async def list_calendars(user: user_dependency, db: db_dependency):
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        calendars = calendar_service.list_calendars()
        return {"calendars": calendars}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
async def get_events(
    user: user_dependency,
    db: db_dependency,
    max_results: int = Query(10, ge=1, le=100),
    days_ahead: int = Query(7, ge=1, le=90),
    calendar_id: str = Query('primary'),
    search: Optional[str] = None
):
    # Fetch calendar events with filtering options
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        
        time_min = datetime.utcnow()
        time_max = time_min + timedelta(days=days_ahead)
        
        events = calendar_service.fetch_events(
            max_results=max_results,
            time_min=time_min,
            time_max=time_max,
            calendar_id=calendar_id,
            query=search
        )
        
        return {
            "events": events,
            "count": len(events),
            "time_range": {
                "from": time_min.isoformat(),
                "to": time_max.isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upcoming")
async def get_upcoming_events(
    user: user_dependency,
    db: db_dependency,
    limit: int = Query(5, ge=1, le=20)
):
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        events = calendar_service.fetch_events(max_results=limit)
        
        return {
            "upcoming_events": events,
            "count": len(events)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    user: user_dependency,
    db: db_dependency,
    calendar_id: str = Query('primary')
):
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        event = calendar_service.get_event(event_id, calendar_id)
        return {"event": event}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/event/create", status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: CalendarEventCreate,
    user: user_dependency,
    db: db_dependency
):
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        google_event = calendar_service.create_event(
            title=event_data.title,
            start_time=event_data.start_time,
            end_time=event_data.end_time,
            description=event_data.description,
            location=event_data.location,
            attendees=event_data.attendees,
            timezone=event_data.timezone or 'Africa/Lagos',
            conference_data=event_data.add_meet_link
        )
        
        return {
            "message": "Event created successfully",
            "event": google_event
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/schedule", status_code=status.HTTP_201_CREATED)
async def schedule_meeting_from_email(
    request: MeetingFromEmailRequest,
    user: user_dependency,
    db: db_dependency
):
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        event = calendar_service.create_meeting_from_email(
            email_sender=request.email_sender,
            subject=request.subject,
            suggested_time=request.suggested_time,
            duration_minutes=request.duration_minutes or 60,
            description=request.description
        )
        
        return {
            "message": "Meeting scheduled successfully",
            "event": event,
            "meet_link": event.get('hangoutLink')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/events/{event_id}")
async def update_event(
    event_id: str,
    event_data: CalendarEventUpdate,
    user: user_dependency,
    db: db_dependency,
    calendar_id: str = Query('primary')
):
    # Update existing calendar event
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        
        update_data = event_data.dict(exclude_unset=True)
        updated_event = calendar_service.update_event(
            event_id,
            calendar_id=calendar_id,
            **update_data
        )
        
        return {
            "message": "Event updated successfully",
            "event": updated_event
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/events/{event_id}")
async def cancel_event(
    event_id: str,
    user: user_dependency,
    db: db_dependency,
    calendar_id: str = Query('primary'),
    notify_attendees: bool = Query(True)
):
    # Cancel/Delete calendar event
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        send_updates = 'all' if notify_attendees else 'none'
        
        calendar_service.cancel_event(
            event_id,
            calendar_id=calendar_id,
            send_updates=send_updates
        )
        
        return {"message": "Event cancelled successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slots/free")
async def find_free_slots(
    request: FreeSlotsRequest,
    user: user_dependency,
    db: db_dependency
):
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        free_slots = calendar_service.find_time_slot(
            date=request.date,
            duration_minutes=request.duration_minutes or 60,
            working_hours_start=request.working_hours_start or 9,
            working_hours_end=request.working_hours_end or 17
        )
        
        return {
            "date": request.date.isoformat(),
            "free_slots": free_slots,
            "count": len(free_slots)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))