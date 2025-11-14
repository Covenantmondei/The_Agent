from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks
from typing import List, Optional
from datetime import datetime
import asyncio
from ...services.meeting_service import (
    MeetingService, 
    start_meeting_transcription, 
    stop_meeting_transcription,
    active_meetings
)
from ...services.auth import user_dependency
from ...db.base import db_dependency
from ...schemas.meeting import (
    MeetingJoinRequest,
    MeetingResponse,
    LiveMeetingResponse,
    MeetingSummaryResponse,
    MeetingSessionResponse
)
from ...db.models.meeting import Meeting, MeetingTranscript

router = APIRouter(prefix='/meetings', tags=['meetings'])


@router.get("/live", response_model=LiveMeetingResponse)
async def get_live_meetings(
    user: user_dependency,
    db: db_dependency
):
    """Get currently active and upcoming Google Meet events"""
    meeting_service = MeetingService(db)
    
    active = meeting_service.get_active_meetings(user.id)
    upcoming = meeting_service.get_upcoming_meetings(user.id)
    
    return {
        "active_meetings": active,
        "upcoming_meetings": upcoming
    }


@router.post("/join", status_code=status.HTTP_201_CREATED, response_model=MeetingSessionResponse)
async def join_meeting(
    request: MeetingJoinRequest,
    user: user_dependency,
    db: db_dependency,
    background_tasks: BackgroundTasks
):
    """
    Ad-hoc join: Mobile app joins a Meet link and starts transcription session
    
    Mobile is responsible for:
    - Actually joining the Google Meet as a participant
    - Capturing system/device audio via MediaProjection/ReplayKit
    - Streaming audio to the WebSocket endpoint
    
    This endpoint:
    - Creates a meeting session record
    - Returns WebSocket URL for audio streaming
    - Starts transcription service in background
    """
    try:
        meeting_service = MeetingService(db)
        
        # Check if there's already an active session for this meet_url
        existing = db.query(Meeting).filter(
            Meeting.user_id == user.id,
            Meeting.meet_link == request.meet_url,
            Meeting.status.in_(["active", "finalizing"])
        ).first()
        
        if existing:
            return {
                "session_id": existing.id,
                "meet_url": existing.meet_link,
                "websocket_url": f"/ws/meeting/{existing.id}",
                "status": existing.status,
                "message": "Session already active for this meeting"
            }
        
        # Create new meeting session
        meeting = meeting_service.create_meeting_session(
            user_id=user.id,
            meet_url=request.meet_url,
            title=request.title or "Untitled Meeting",
            is_manual=True
        )
        
        # Start transcription in background
        background_tasks.add_task(start_meeting_transcription, meeting.id)
        
        return {
            "session_id": meeting.id,
            "meet_url": meeting.meet_link,
            "websocket_url": f"/ws/meeting/{meeting.id}",
            "status": "active",
            "message": "Meeting session created. Connect to WebSocket to stream audio."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{meeting_id}/stop")
async def stop_meeting(
    meeting_id: int,
    user: user_dependency,
    db: db_dependency,
    background_tasks: BackgroundTasks
):
    """
    Stop meeting transcription and trigger summary generation
    
    Mobile calls this when:
    - User leaves the meeting
    - Meeting ends naturally
    """
    try:
        meeting_service = MeetingService(db)
        meeting = meeting_service.get_meeting(meeting_id, user.id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if meeting.status not in ["active", "finalizing"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Meeting is already {meeting.status}"
            )
        
        # Stop transcription and generate summary in background
        background_tasks.add_task(stop_meeting_transcription, meeting_id, False)
        
        return {
            "message": "Meeting transcription stopped. Summary is being generated.",
            "meeting_id": meeting_id,
            "status": "finalizing"
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
            "meeting": {
                "id": meeting.id,
                "title": meeting.title,
                "meet_link": meeting.meet_link,
                "start_time": meeting.start_time,
                "end_time": meeting.end_time,
                "status": meeting.status,
                "is_manual": meeting.is_manual
            },
            "transcripts": [
                {
                    "sequence_number": t.sequence_number,
                    "timestamp": t.timestamp,
                    "text": t.text,
                    "speaker": t.speaker
                }
                for t in transcripts
            ],
            "summary": {
                "key_points": summary.key_points if summary else None,
                "decisions": summary.decisions if summary else None,
                "action_items": summary.action_items if summary else None,
                "follow_ups": summary.follow_ups if summary else None,
                "summary_unavailable": summary.summary_unavailable if summary else False,
                "error_message": summary.error_message if summary else None
            } if summary else None,
            "is_active": meeting_id in active_meetings,
            "total_transcript_length": len(transcripts)
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
            raise HTTPException(
                status_code=404, 
                detail="Summary not available yet. Meeting may still be active or finalizing."
            )
        
        return meeting.summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{meeting_id}/summary/retry", response_model=MeetingSummaryResponse)
async def retry_summary_generation(
    meeting_id: int,
    user: user_dependency,
    db: db_dependency,
    background_tasks: BackgroundTasks
):

    try:
        meeting_service = MeetingService(db)
        meeting = meeting_service.get_meeting(meeting_id, user.id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if meeting.status not in ["completed", "finalizing"]:
            raise HTTPException(
                status_code=400,
                detail="Meeting must be completed or finalizing to retry summary"
            )
        
        # Check if there's a transcript
        full_transcript = meeting_service.get_full_transcript(meeting_id)
        if not full_transcript or len(full_transcript.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Transcript is too short or empty for summarization"
            )
        
        # Generate summary (will run in background thread pool)
        summary = await meeting_service.generate_summary(meeting_id, retry=True)
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[MeetingResponse])
async def get_all_meetings(
    user: user_dependency,
    db: db_dependency,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(
        None, 
        alias="status",
        description="Filter by status: scheduled, active, finalizing, completed, failed"
    )
):
    try:
        query = db.query(Meeting).filter(Meeting.user_id == user.id)
        
        if status_filter:
            query = query.filter(Meeting.status == status_filter)
        
        meetings = query.order_by(
            Meeting.start_time.desc()
        ).offset(skip).limit(limit).all()
        
        return meetings
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{meeting_id}")
async def delete_meeting(
    meeting_id: int,
    user: user_dependency,
    db: db_dependency,
    background_tasks: BackgroundTasks
):
    try:
        meeting_service = MeetingService(db)
        meeting = meeting_service.get_meeting(meeting_id, user.id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Stop if active
        if meeting_id in active_meetings:
            background_tasks.add_task(stop_meeting_transcription, meeting_id, True)
        
        # Delete from database (cascade will handle transcripts and summary)
        db.delete(meeting)
        db.commit()
        
        return {
            "message": "Meeting deleted successfully",
            "meeting_id": meeting_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{meeting_id}/status")
async def get_meeting_status(
    meeting_id: int,
    user: user_dependency,
    db: db_dependency
):

    try:
        meeting_service = MeetingService(db)
        meeting = meeting_service.get_meeting(meeting_id, user.id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Count transcripts
        transcript_count = db.query(MeetingTranscript).filter(
            MeetingTranscript.meeting_id == meeting_id
        ).count()
        
        return {
            "meeting_id": meeting.id,
            "status": meeting.status,
            "is_active": meeting_id in active_meetings,
            "start_time": meeting.start_time,
            "end_time": meeting.end_time,
            "last_activity": meeting.last_activity,
            "transcript_chunks": transcript_count,
            "has_summary": meeting.summary is not None,
            "summary_unavailable": meeting.summary.summary_unavailable if meeting.summary else False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))