import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_
import pytz
from ..db.models.meeting import Meeting, MeetingTranscript, MeetingSummary
from ..db.models.user import User
from ..db.session import SessionLocal
from .calendar_service import GoogleCalendarService
from .transcription_service import TranscriptionService
from .ai_processor import ai_processor

logger = logging.getLogger(__name__)

# Active meeting sessions {meeting_id: TranscriptionService}
active_meetings: Dict[int, TranscriptionService] = {}

# Grace period for disconnected sessions (seconds)
GRACE_PERIOD = 90


class MeetingService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_meeting_session(
        self, 
        user_id: int, 
        meet_url: str, 
        title: str,
        calendar_event_id: Optional[str] = None,
        is_manual: bool = True
    ) -> Meeting:
        """Create a new meeting session (ad-hoc or calendar-based)"""
        meeting = Meeting(
            user_id=user_id,
            meet_link=meet_url,
            title=title,
            start_time=datetime.utcnow(),
            calendar_event_id=calendar_event_id,
            is_manual=is_manual,
            status="active",  # Start as active immediately
            last_activity=datetime.utcnow()
        )
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        logger.info(f"Created meeting session {meeting.id}: {title}")
        return meeting
    
    def get_meeting(self, meeting_id: int, user_id: int) -> Optional[Meeting]:
        """Get meeting by ID"""
        return self.db.query(Meeting).filter(
            and_(
                Meeting.id == meeting_id,
                Meeting.user_id == user_id
            )
        ).first()
    
    def get_active_meetings(self, user_id: int) -> List[Meeting]:
        """Get all active meetings for a user"""
        return self.db.query(Meeting).filter(
            and_(
                Meeting.user_id == user_id,
                Meeting.status.in_(["active", "finalizing"])
            )
        ).all()
    
    def get_upcoming_meetings(self, user_id: int) -> List[Meeting]:
        """Get upcoming calendar meetings within the next hour"""
        now = datetime.utcnow()
        one_hour_later = now + timedelta(hours=1)
        
        return self.db.query(Meeting).filter(
            and_(
                Meeting.user_id == user_id,
                Meeting.status == "scheduled",
                Meeting.start_time >= now,
                Meeting.start_time <= one_hour_later,
                Meeting.is_manual == False
            )
        ).order_by(Meeting.start_time).all()
    
    def update_meeting_status(self, meeting_id: int, status: str):
        """Update meeting status"""
        meeting = self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = status
            meeting.last_activity = datetime.utcnow()
            self.db.commit()
            logger.info(f"Meeting {meeting_id} status updated to {status}")
    
    def update_last_activity(self, meeting_id: int):
        """Update last activity timestamp (for grace period tracking)"""
        meeting = self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.last_activity = datetime.utcnow()
            self.db.commit()
    
    def save_transcript_chunk(
        self, 
        meeting_id: int, 
        text: str, 
        sequence_number: int,
        is_final: bool = False,
        speaker: Optional[str] = None
    ) -> MeetingTranscript:
        """Save a transcript chunk"""
        transcript = MeetingTranscript(
            meeting_id=meeting_id,
            text=text,
            sequence_number=sequence_number,
            is_final=is_final,
            speaker=speaker
        )
        self.db.add(transcript)
        self.db.commit()
        self.db.refresh(transcript)
        
        # Update last activity
        self.update_last_activity(meeting_id)
        
        return transcript
    
    def get_full_transcript(self, meeting_id: int) -> str:
        """Get complete meeting transcript"""
        transcripts = self.db.query(MeetingTranscript).filter(
            MeetingTranscript.meeting_id == meeting_id
        ).order_by(MeetingTranscript.sequence_number).all()
        
        return "\n".join([t.text for t in transcripts if t.text.strip()])
    
    async def generate_summary(self, meeting_id: int, retry: bool = False) -> MeetingSummary:
        """Generate AI summary of meeting (async, non-blocking)"""
        try:
            full_transcript = self.get_full_transcript(meeting_id)
            
            if not full_transcript or len(full_transcript.strip()) < 10:
                raise ValueError("Transcript is too short or empty for summarization")
            
            # Check if summary already exists and not retrying
            existing_summary = self.db.query(MeetingSummary).filter(
                MeetingSummary.meeting_id == meeting_id
            ).first()
            
            if existing_summary and not retry:
                return existing_summary
            
            # Use AI to generate structured summary (run in thread pool to avoid blocking)
            loop = asyncio.get_event_loop()
            summary_text = await loop.run_in_executor(
                None, 
                self._summarize_with_ai_sync, 
                full_transcript
            )
            
            # Parse the summary into sections
            parsed = self._parse_summary(summary_text)
            
            # Update or create summary
            if existing_summary:
                existing_summary.full_transcript = full_transcript
                existing_summary.key_points = parsed.get('key_points')
                existing_summary.decisions = parsed.get('decisions')
                existing_summary.action_items = parsed.get('action_items')
                existing_summary.follow_ups = parsed.get('follow_ups')
                existing_summary.summary_unavailable = False
                existing_summary.error_message = None
                self.db.commit()
                self.db.refresh(existing_summary)
                summary = existing_summary
            else:
                summary = MeetingSummary(
                    meeting_id=meeting_id,
                    full_transcript=full_transcript,
                    key_points=parsed.get('key_points'),
                    decisions=parsed.get('decisions'),
                    action_items=parsed.get('action_items'),
                    follow_ups=parsed.get('follow_ups'),
                    summary_unavailable=False
                )
                self.db.add(summary)
                self.db.commit()
                self.db.refresh(summary)
            
            logger.info(f"✅ Generated summary for meeting {meeting_id}")
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error generating summary for meeting {meeting_id}: {e}")
            
            # Create/update summary with error flag
            existing_summary = self.db.query(MeetingSummary).filter(
                MeetingSummary.meeting_id == meeting_id
            ).first()
            
            full_transcript = self.get_full_transcript(meeting_id)
            
            if existing_summary:
                existing_summary.full_transcript = full_transcript
                existing_summary.summary_unavailable = True
                existing_summary.error_message = str(e)
                self.db.commit()
                self.db.refresh(existing_summary)
                return existing_summary
            else:
                summary = MeetingSummary(
                    meeting_id=meeting_id,
                    full_transcript=full_transcript,
                    summary_unavailable=True,
                    error_message=str(e)
                )
                self.db.add(summary)
                self.db.commit()
                self.db.refresh(summary)
                return summary
    
    def _summarize_with_ai_sync(self, transcript: str) -> str:
        """Synchronous wrapper for AI summarization (runs in thread pool)"""
        prompt = f"""
        Summarize this meeting transcript into the following sections:

        ## Key Points
        List the main topics and important points discussed.

        ## Decisions
        List any decisions that were made during the meeting.

        ## Action Items
        List specific tasks or action items that were assigned, including who is responsible if mentioned.

        ## Follow-ups
        List any topics that need follow-up or future discussion.

        Meeting Transcript:
        {transcript}
        """
        
        response = ai_processor.client.chat.completions.create(
            model=ai_processor.model,
            messages=[
                {"role": "system", "content": "You are a professional meeting assistant that creates clear, structured meeting summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1000
        )
        
        return response.choices[0].message.content.strip()
    
    def _parse_summary(self, summary_text: str) -> Dict:
        sections = {
            'key_points': '',
            'decisions': '',
            'action_items': [],
            'follow_ups': ''
        }
        
        try:
            parts = summary_text.split('##')
            
            for part in parts:
                part = part.strip()
                if part.lower().startswith('key points'):
                    sections['key_points'] = part.split('\n', 1)[1].strip() if '\n' in part else ''
                elif part.lower().startswith('decisions'):
                    sections['decisions'] = part.split('\n', 1)[1].strip() if '\n' in part else ''
                elif part.lower().startswith('action items'):
                    content = part.split('\n', 1)[1] if '\n' in part else ''
                    items = [line.strip('- ').strip() for line in content.split('\n') if line.strip().startswith('-')]
                    sections['action_items'] = items
                elif part.lower().startswith('follow-ups') or part.lower().startswith('follow ups'):
                    sections['follow_ups'] = part.split('\n', 1)[1].strip() if '\n' in part else ''
        except Exception as e:
            logger.warning(f"Error parsing summary sections: {e}")
        
        return sections


async def start_meeting_transcription(meeting_id: int):
    """Start transcription service for a meeting session"""
    try:
        db: Session = SessionLocal()
        meeting_service = MeetingService(db)
        
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            logger.error(f"Meeting {meeting_id} not found")
            return
        
        # Update status to active if not already
        if meeting.status != "active":
            meeting_service.update_meeting_status(meeting_id, "active")
        
        # Create transcription service
        transcription_service = TranscriptionService(meeting_id, db)
        active_meetings[meeting_id] = transcription_service
        
        logger.info(f"Started transcription for meeting {meeting_id}")
        
        # Start transcription (will run until stopped)
        await transcription_service.start()
        
    except Exception as e:
        logger.error(f" Error starting transcription for meeting {meeting_id}: {e}")
    finally:
        db.close()


async def stop_meeting_transcription(meeting_id: int, force: bool = False):
    """Stop transcription and generate summary"""
    try:
        if meeting_id in active_meetings:
            transcription_service = active_meetings[meeting_id]
            await transcription_service.stop()
            del active_meetings[meeting_id]
            
            logger.info(f"Stopped transcription for meeting {meeting_id}")
        
        # Update status to finalizing
        db: Session = SessionLocal()
        meeting_service = MeetingService(db)
        meeting_service.update_meeting_status(meeting_id, "finalizing")
        
        # Generate summary in background
        try:
            summary = await meeting_service.generate_summary(meeting_id)
            meeting_service.update_meeting_status(meeting_id, "completed")
            logger.info(f"Generated summary for meeting {meeting_id}")
        except Exception as summary_error:
            logger.error(f"Summary generation failed for meeting {meeting_id}: {summary_error}")
            meeting_service.update_meeting_status(meeting_id, "completed")
        
        # Set end time
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.end_time = datetime.utcnow()
            db.commit()
        
        db.close()
            
    except Exception as e:
        logger.error(f"❌Error stopping meeting {meeting_id}: {e}")


async def check_inactive_sessions():
    """Background task to check for inactive sessions and auto-finalize after grace period"""
    while True:
        try:
            db: Session = SessionLocal()
            
            # Find active meetings that haven't had activity in GRACE_PERIOD
            cutoff_time = datetime.utcnow() - timedelta(seconds=GRACE_PERIOD)
            
            inactive_meetings = db.query(Meeting).filter(
                and_(
                    Meeting.status == "active",
                    Meeting.last_activity < cutoff_time
                )
            ).all()
            
            for meeting in inactive_meetings:
                logger.warning(f"Meeting {meeting.id} inactive for {GRACE_PERIOD}s, auto-finalizing...")
                asyncio.create_task(stop_meeting_transcription(meeting.id, force=True))
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error in inactive session checker: {e}")
        
        # Check every 30 seconds
        await asyncio.sleep(30)


async def poll_calendar_for_meetings():
    # Background task to poll Google Calendar for upcoming meetings
    logger.info("Starting calendar polling service...")
    
    while True:
        try:
            db: Session = SessionLocal()
            
            users = db.query(User).filter(
                and_(
                    User.google_access_token.isnot(None),
                    User.is_active == True
                )
            ).all()
            
            now = datetime.utcnow()
            one_minute_later = now + timedelta(minutes=1)
            
            for user in users:
                try:
                    calendar_service = GoogleCalendarService(user, db)
                    meeting_service = MeetingService(db)
                    
                    upcoming_events = calendar_service.get_upcoming_events(time_min=now, time_max=one_minute_later)
                    
                    for event in upcoming_events:
                        meet_link = event.get('hangoutLink')
                        if not meet_link:
                            continue
                        
                        event_id = event['id']
                        
                        existing = db.query(Meeting).filter(
                            and_(
                                Meeting.user_id == user.id,
                                Meeting.calendar_event_id == event_id
                            )
                        ).first()
                        
                        if existing and existing.status == "active":
                            continue
                        
                        if not existing:
                            start_time = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')).replace('Z', '+00:00'))
                            
                            meeting = meeting_service.create_meeting_session(
                                user_id=user.id,
                                meet_url=meet_link,
                                title=event.get('summary', 'Untitled Meeting'),
                                calendar_event_id=event_id,
                                is_manual=False
                            )
                            
                            asyncio.create_task(start_meeting_transcription(meeting.id))
                            logger.info(f"Auto-started meeting {meeting.id} from calendar")
                
                except Exception as user_error:
                    logger.error(f"Error processing calendar for user {user.id}: {user_error}")
                    continue
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error in calendar polling service: {e}")
        
        await asyncio.sleep(60)