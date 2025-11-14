from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict
import logging
from ...db.base import get_db
from ...services.meeting_service import active_meetings, MeetingService
from ...services.auth import get_current_user_ws

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/ws', tags=['websocket'])


@router.websocket("/meeting/{meeting_id}")
async def meeting_websocket(
    websocket: WebSocket,
    meeting_id: int,
    token: str = Query(...)
):

    await websocket.accept()
    
    try:
        # TODO:
        # Verify user has access to this meeting
        # user = await get_current_user_ws(websocket)
        
        meeting_service = MeetingService(db)
        meeting = meeting_service.get_meeting(meeting_id, user['id'])
        
        if not meeting:
            await websocket.send_json({"error": "Meeting not found"})
            await websocket.close()
            return
        
        # Get transcription service
        if meeting_id not in active_meetings:
            await websocket.send_json({
                "error": "Meeting transcription not started. Call POST /meetings/join first."
            })
            await websocket.close()
            return
        
        transcription_service = active_meetings[meeting_id]
        transcription_service.add_websocket(websocket)
        
        logger.info(f"WebSocket connected: Meeting {meeting_id}, User {user['id']}")
        
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to meeting transcription",
            "meeting_id": meeting_id,
            "status": meeting.status
        })
        
        # Listen for incoming audio chunks and control messages
        while True:
            try:
                data = await websocket.receive()
                
                # Update last activity
                meeting_service.update_last_activity(meeting_id)
                
                if "bytes" in data:
                    # Binary audio chunk received from mobile
                    audio_chunk = data["bytes"]
                    await transcription_service.process_audio_chunk(audio_chunk)
                    
                elif "text" in data:
                    # JSON control message
                    import json
                    message = json.loads(data["text"])
                    
                    if message.get("action") == "ping":
                        await websocket.send_json({"type": "pong"})
                    
                    elif message.get("action") == "status":
                        await websocket.send_json({
                            "type": "status",
                            "meeting_id": meeting_id,
                            "is_recording": transcription_service.is_running,
                            "sequence_number": transcription_service.sequence_number,
                            "buffer_size": len(transcription_service.audio_byte_buffer)
                        })
                    
                    else:
                        logger.warning(f"Unknown action: {message.get('action')}")
                        
            except WebSocketDisconnect:
                logger.info(f"📱 Client disconnected from meeting {meeting_id}")
                break
            except Exception as receive_error:
                logger.error(f"Error receiving data: {receive_error}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"📱 WebSocket disconnected from meeting {meeting_id}")
    
    except Exception as e:
        logger.error(f"❌ WebSocket error for meeting {meeting_id}: {e}")
        try:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
        except:
            pass
    
    finally:
        # Remove from transcription service
        if meeting_id in active_meetings:
            active_meetings[meeting_id].remove_websocket(websocket)
        
        logger.info(f"📱 WebSocket cleanup complete for meeting {meeting_id}")