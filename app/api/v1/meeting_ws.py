from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict
import logging
from ...services.auth import get_current_user_ws
from ...db.base import db_dependency
from ...services.meeting_service import active_meetings, MeetingService
from ...db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/ws', tags=['websocket'])


@router.websocket("/meeting/{meeting_id}")
async def meeting_websocket(
    websocket: WebSocket,
    meeting_id: int,
    db: db_dependency
):

    await websocket.accept()
    
    try:
        # TODO:
        # Verify user has access to this meeting
        # user = await get_current_user_ws(websocket)
        
        meeting_service = MeetingService(db)
        meeting = db.query(meeting_service.db.query(meeting_service.db.models.Meeting).filter_by(id=meeting_id).first())
        
        if not meeting:
            await websocket.send_json({"error": "Meeting not found"})
            await websocket.close()
            return
        
        if meeting_id not in active_meetings:
            await websocket.send_json({"error": "Meeting transcription not started"})
            await websocket.close()
            return
        
        transcription_service = active_meetings[meeting_id]
        transcription_service.add_websocket(websocket)
        
        logger.info(f"WebSocket connected for meeting {meeting_id}")
        
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to meeting transcription",
            "meeting_id": meeting_id
        })
        
        # Listen for incoming messages (audio chunks or control messages)
        while True:
            data = await websocket.receive()
            
            if "bytes" in data:
                audio_chunk = data["bytes"]
                await transcription_service.process_audio_chunk(audio_chunk)
                
            elif "text" in data:
                import json
                message = json.loads(data["text"])
                
                if message.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
                
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected from meeting {meeting_id}")
        if meeting_id in active_meetings:
            active_meetings[meeting_id].remove_websocket(websocket)
    
    except Exception as e:
        logger.error(f"WebSocket error for meeting {meeting_id}: {e}")
        try:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
        except:
            pass
        
        if meeting_id in active_meetings:
            active_meetings[meeting_id].remove_websocket(websocket)