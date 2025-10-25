import asyncio
import logging
import subprocess
import tempfile
import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
import whisper
from ..db.models.meeting import Meeting
from .meeting_service import MeetingService

logger = logging.getLogger(__name__)


class TranscriptionService:
    # Handles audio capture and real-time transcription using Whisper
    
    def __init__(self, meeting_id: int, db: Session):
        self.meeting_id = meeting_id
        self.db = db
        self.meeting_service = MeetingService(db)
        self.is_running = False
        self.sequence_number = 0
        self.audio_buffer = []
        
        logger.info("Loading Whisper model...")
        self.whisper_model = whisper.load_model("base")
        logger.info("Whisper model loaded successfully")
        
        # WebSocket connections for this meeting
        self.websocket_connections = []
        
        # FFmpeg process
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.temp_audio_file = None
    
    async def start(self):
        self.is_running = True
        logger.info(f"Starting transcription service for meeting {self.meeting_id}")
        
        try:
            # Create temporary file for audio chunks
            self.temp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            
            # Start FFmpeg to capture system audio
            await self.start_capture()
            
            # Start transcription loop
            await self.transcription_loop()
            
        except Exception as e:
            logger.error(f"Error in transcription service: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        logger.info(f"Stopping transcription service for meeting {self.meeting_id}")
        self.is_running = False
        
        # Stop FFmpeg
        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            self.ffmpeg_process.wait()
        
        # Clean up temporary file
        if self.temp_audio_file:
            try:
                os.unlink(self.temp_audio_file.name)
            except:
                pass
        
        # Close all WebSocket connections
        for ws in self.websocket_connections:
            try:
                await ws.close()
            except:
                pass
    
    async def start_capture(self):
        try:
            # For desktop (Windows example using DirectShow)
            # On Linux, use PulseAudio or ALSA
            # On macOS, use avfoundation
            
            # Windows example:
            # ffmpeg_cmd = [
            #     'ffmpeg',
            #     '-f', 'dshow',
            #     '-i', 'audio=Stereo Mix',  # System audio device
            #     '-ar', '16000',  # Whisper prefers 16kHz
            #     '-ac', '1',  # Mono
            #     '-f', 'wav',
            #     self.temp_audio_file.name
            # ]
            
            # For now, we'll implement audio streaming from client (mobile)
            # The client will send audio chunks via WebSocket
            logger.info("Audio capture ready - waiting for client audio stream")
            
        except Exception as e:
            logger.error(f"Error starting audio capture: {e}")
            raise
    
    async def process_audio_chunk(self, audio_data: bytes):
        try:
            # Write audio chunk to temporary file
            self.temp_audio_file.write(audio_data)
            self.temp_audio_file.flush()
            
            # Add to buffer for transcription
            self.audio_buffer.append(audio_data)
            
            # Trigger transcription every N chunks or N seconds
            if len(self.audio_buffer) >= 10:  # Process every 10 chunks
                await self.transcribe_buffer()
                
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
    
    async def transcription_loop(self):
        retry_count = 0
        max_retries = 4
        
        while self.is_running:
            try:
                # Wait for audio buffer to accumulate
                await asyncio.sleep(3)  # Transcribe every 3 seconds
                
                if self.audio_buffer:
                    await self.transcribe_buffer()
                    retry_count = 0  # Reset retry count on success
                    
            except Exception as e:
                retry_count += 1
                logger.error(f"Transcription error (attempt {retry_count}/{max_retries}): {e}")
                
                if retry_count >= max_retries:
                    logger.error(f"Max retries reached for meeting {self.meeting_id}")
                    self.is_running = False
                    break
                
                # Wait before retrying
                await asyncio.sleep(2)
    
    async def transcribe_buffer(self):
        if not self.audio_buffer:
            return
        
        try:
            # Use the temporary audio file for transcription
            # Whisper expects a file path
            result = self.whisper_model.transcribe(
                self.temp_audio_file.name,
                language="en",  # Auto-detect if None
                fp16=False  # Set to True if using GPU
            )
            
            text = result['text'].strip()
            
            if text:
                # Save transcript to database
                self.sequence_number += 1
                transcript = self.meeting_service.save_transcript_chunk(
                    meeting_id=self.meeting_id,
                    text=text,
                    sequence_number=self.sequence_number,
                    is_final=True
                )
                
                logger.info(f"Transcribed (meeting {self.meeting_id}): {text[:50]}...")
                
                # Broadcast to WebSocket clients
                await self.broadcast_transcript({
                    "meeting_id": self.meeting_id,
                    "timestamp": transcript.timestamp.isoformat(),
                    "text": text,
                    "sequence_number": self.sequence_number,
                    "is_final": True
                })
            
            # Clear buffer and reset temp file
            self.audio_buffer = []
            self.temp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise
    
    async def broadcast_transcript(self, data: dict):
        disconnected = []
        
        for ws in self.websocket_connections:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket client: {e}")
                disconnected.append(ws)
        
        # Remove disconnected clients
        for ws in disconnected:
            self.websocket_connections.remove(ws)
    
    def add_websocket(self, websocket):
        # Add a WebSocket connection for this meeting
        self.websocket_connections.append(websocket)
        logger.info(f"WebSocket connected for meeting {self.meeting_id}")
    
    def remove_websocket(self, websocket):
        # Remove a WebSocket connection
        if websocket in self.websocket_connections:
            self.websocket_connections.remove(websocket)
            logger.info(f"WebSocket disconnected from meeting {self.meeting_id}")