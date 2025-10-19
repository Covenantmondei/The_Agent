from fastapi import APIRouter, HTTPException, status
from ...services.calendar_service import GoogleCalendarService
from ...services.auth import user_dependency
from ...db.base import db_dependency
from ...schemas.calendar import CalendarEventCreate, CalendarEventUpdate, CalendarEventResponse

router = APIRouter(prefix='/calendar', tags=['calendar'])

@router.get("/events")
async def get_events(user: user_dependency, db: db_dependency):
    """Fetch calendar events from Google Calendar"""
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    if not user.google_refresh_token:
        raise HTTPException(status_code=400, detail="Please reconnect your Google account")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        events = calendar_service.fetch_events()
        return {"events": events}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: CalendarEventCreate,
    user: user_dependency,
    db: db_dependency
):
    """Create a new calendar event"""
    if not user.google_access_token:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")
    
    if not user.google_refresh_token:
        raise HTTPException(status_code=400, detail="Please reconnect your Google account")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        google_event = calendar_service.create_event(
            title=event_data.title,
            start_time=event_data.start_time,
            end_time=event_data.end_time,
            description=event_data.description,
            location=event_data.location
        )
        
        return {"message": "Event created", "event": google_event}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{event_id}")
async def update_event(
    event_id: str,
    event_data: CalendarEventUpdate,
    user: user_dependency,
    db: db_dependency
):
    """Update existing calendar event"""
    if not user.google_refresh_token:
        raise HTTPException(status_code=400, detail="Please reconnect your Google account")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        updated_event = calendar_service.update_event(event_id, **event_data.dict(exclude_unset=True))
        return {"message": "Event updated", "event": updated_event}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{event_id}")
async def delete_event(event_id: str, user: user_dependency, db: db_dependency):
    """Delete calendar event"""
    if not user.google_refresh_token:
        raise HTTPException(status_code=400, detail="Please reconnect your Google account")
    
    try:
        calendar_service = GoogleCalendarService(user, db)
        calendar_service.delete_event(event_id)
        return {"message": "Event deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))