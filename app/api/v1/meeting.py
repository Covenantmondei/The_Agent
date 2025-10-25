from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
from ...services.meeting_service import (
    MeetingService, 
    start_meeting_transcription, 
    stop_meeting_transcription,
    active_meetings
)
from ...services.auth import user_dependency
from ...db.base import db_dependency
from ...schemas.meeting import (
    MeetingCreate,
    MeetingResponse,
    LiveMeetingResponse,
    MeetingSummaryResponse,
    TranscriptChunk
)
from ...db.models.meeting import Meeting, MeetingTranscript

router = APIRouter(prefix='/meetings', tags=['meetings'])


@router.get("/live", response_model=LiveMeetingResponse)
async def get_live_meetings(
    user: user_dependency,
    db: db_dependency
):
    # Get currently active and upcoming Google Meet events
    meeting_service = MeetingService(db)
    
    active = meeting_service.get_active_meetings(user.id)
    upcoming = meeting_service.get_upcoming_meetings(user.id)
    
    return {
        "active_meetings": active,
        "upcoming_meetings": upcoming
    }


@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_meeting(
    meeting_data: MeetingCreate,
    user: user_dependency,
    db: db_dependency
):
    # Manually start recording for a meeting
    try:
        meeting_service = MeetingService(db)
        
        # Create meeting record
        meeting = meeting_service.create_meeting(
            user_id=user.id,
            meet_link=meeting_data.meet_link,
            title=meeting_data.title,
            start_time=meeting_data.start_time,
            end_time=meeting_data.end_time,
            is_manual=True
        )
        
        import asyncio
        asyncio.create_task(start_meeting_transcription(meeting.id))
        
        return {
            "message": "Meeting transcription started",
            "meeting_id": meeting.id,
            "websocket_url": f"/ws/meeting/{meeting.id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{meeting_id}/stop")
async def stop_meeting(
    meeting_id: int,
    user: user_dependency,
    db: db_dependency
):
    try:
        meeting_service = MeetingService(db)
        meeting = meeting_service.get_meeting(meeting_id, user.id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if meeting.status != "active":
            raise HTTPException(status_code=400, detail="Meeting is not active")
        
        # Stop transcription and generate summary
        import asyncio
        asyncio.create_task(stop_meeting_transcription(meeting_id))
        
        return {
            "message": "Meeting transcription stopped. Summary will be generated.",
            "meeting_id": meeting_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{meeting_id}/transcript")
async def get_meeting_transcript(
    meeting_id: int,
    user: user_dependency,
    db: db_dependency
):
    # Fetch full transcript and summary
    try:
        meeting_service = MeetingService(db)
        meeting = meeting_service.get_meeting(meeting_id, user.id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Get transcripts
        transcripts = db.query(MeetingTranscript).filter(
            MeetingTranscript.meeting_id == meeting_id
        ).order_by(MeetingTranscript.sequence_number).all()
        
        # Get summary if available
        summary = meeting.summary
        
        return {
            "meeting": meeting,
            "transcripts": transcripts,
            "summary": summary,
            "is_active": meeting_id in active_meetings
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{meeting_id}/summary", response_model=MeetingSummaryResponse)
async def get_meeting_summary(
    meeting_id: int,
    user: user_dependency,
    db: db_dependency
):
    # Get meeting summary
    try:
        meeting_service = MeetingService(db)
        meeting = meeting_service.get_meeting(meeting_id, user.id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if not meeting.summary:
            raise HTTPException(status_code=404, detail="Summary not available yet")
        
        return meeting.summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meeting/all", response_model=List[MeetingResponse])
async def get_all_meetings(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = Query(None, description="Filter by status: scheduled, active, completed, failed")
):
    try:
        query = db.query(Meeting).filter(Meeting.user_id == user.id)
        
        if status:
            query = query.filter(Meeting.status == status)
        
        meetings = query.order_by(Meeting.start_time.desc()).offset(skip).limit(limit).all()
        
        return meetings
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{meeting_id}")
async def delete_meeting(
    meeting_id: int,
    user: user_dependency,
    db: db_dependency
):
    try:
        meeting_service = MeetingService(db)
        meeting = meeting_service.get_meeting(meeting_id, user.id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Stop if active
        if meeting_id in active_meetings:
            await stop_meeting_transcription(meeting_id)
        
        db.delete(meeting)
        db.commit()
        
        return {"message": "Meeting deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))