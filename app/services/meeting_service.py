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


class MeetingService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_meeting(
        self, 
        user_id: int, 
        meet_link: str, 
        title: str, 
        start_time: datetime,
        end_time: Optional[datetime] = None,
        calendar_event_id: Optional[str] = None,
        is_manual: bool = False
    ) -> Meeting:
        # Create a new meeting record
        meeting = Meeting(
            user_id=user_id,
            meet_link=meet_link,
            title=title,
            start_time=start_time,
            end_time=end_time,
            calendar_event_id=calendar_event_id,
            is_manual=is_manual,
            status="scheduled"
        )
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        logger.info(f"Created meeting {meeting.id}: {title}")
        return meeting
    
    def get_meeting(self, meeting_id: int, user_id: int) -> Optional[Meeting]:
        return self.db.query(Meeting).filter(
            and_(
                Meeting.id == meeting_id,
                Meeting.user_id == user_id
            )
        ).first()
    
    def get_active_meetings(self, user_id: int) -> List[Meeting]:
        return self.db.query(Meeting).filter(
            and_(
                Meeting.user_id == user_id,
                Meeting.status == "active"
            )
        ).all()
    
    def get_upcoming_meetings(self, user_id: int) -> List[Meeting]:
        # Get upcoming meetings within the next hour
        now = datetime.utcnow()
        one_hour_later = now + timedelta(hours=1)
        
        return self.db.query(Meeting).filter(
            and_(
                Meeting.user_id == user_id,
                Meeting.status == "scheduled",
                Meeting.start_time >= now,
                Meeting.start_time <= one_hour_later
            )
        ).order_by(Meeting.start_time).all()
    
    def update_meeting_status(self, meeting_id: int, status: str):
        meeting = self.db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = status
            self.db.commit()
            logger.info(f"Meeting {meeting_id} status updated to {status}")
    
    def save_transcript_chunk(
        self, 
        meeting_id: int, 
        text: str, 
        sequence_number: int,
        is_final: bool = False,
        speaker: Optional[str] = None
    ) -> MeetingTranscript:
        
        # Save a transcript
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
        return transcript
    
    def get_full_transcript(self, meeting_id: int) -> str:
        transcripts = self.db.query(MeetingTranscript).filter(
            MeetingTranscript.meeting_id == meeting_id
        ).order_by(MeetingTranscript.sequence_number).all()
        
        return "\n".join([t.text for t in transcripts])
    
    async def generate_summary(self, meeting_id: int) -> MeetingSummary:
        try:
            full_transcript = self.get_full_transcript(meeting_id)
            
            if not full_transcript:
                raise ValueError("No transcript available for summarization")
            
            # Use AI to generate structured summary
            summary_text = await self.ai_summary(full_transcript)
            
            # Parse the summary into sections
            parsed = self.parse_summary(summary_text)
            
            summary = MeetingSummary(
                meeting_id=meeting_id,
                full_transcript=full_transcript,
                key_points=parsed.get('key_points'),
                decisions=parsed.get('decisions'),
                action_items=parsed.get('action_items'),
                follow_ups=parsed.get('follow_ups')
            )
            
            self.db.add(summary)
            self.db.commit()
            self.db.refresh(summary)
            
            logger.info(f"Generated summary for meeting {meeting_id}")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary for meeting {meeting_id}: {e}")
            raise
    
    async def ai_summary(self, transcript: str) -> str:
        # Use LLM to summarize transcript
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
    
    def parse_summary(self, summary_text: str) -> Dict:
        sections = {
            'key_points': '',
            'decisions': '',
            'action_items': [],
            'follow_ups': ''
        }
        
        try:
            # Split by section headers
            parts = summary_text.split('##')
            
            for part in parts:
                part = part.strip()
                if part.lower().startswith('key points'):
                    sections['key_points'] = part.split('\n', 1)[1].strip() if '\n' in part else ''
                elif part.lower().startswith('decisions'):
                    sections['decisions'] = part.split('\n', 1)[1].strip() if '\n' in part else ''
                elif part.lower().startswith('action items'):
                    content = part.split('\n', 1)[1] if '\n' in part else ''
                    # Extract bullet points
                    items = [line.strip('- ').strip() for line in content.split('\n') if line.strip().startswith('-')]
                    sections['action_items'] = items
                elif part.lower().startswith('follow-ups'):
                    sections['follow_ups'] = part.split('\n', 1)[1].strip() if '\n' in part else ''
        except Exception as e:
            logger.warning(f"Error parsing summary sections: {e}")
        
        return sections


async def poll_calendar_for_meetings():
    # Background task to poll Google Calendar for upcoming meetings
    logger.info("Starting calendar polling service...")
    
    while True:
        try:
            db: Session = SessionLocal()
            
            # Get all users with active Google Calendar tokens
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
                    
                    # Get upcoming events from Google Calendar
                    upcoming_events = calendar_service.get_upcoming_events(time_min=now, time_max=one_minute_later)
                    
                    for event in upcoming_events:
                        # Check if event has Google Meet link
                        meet_link = event.get('hangoutLink')
                        if not meet_link:
                            continue
                        
                        event_id = event['id']
                        
                        # Check if meeting already exists
                        existing = db.query(Meeting).filter(
                            and_(
                                Meeting.user_id == user.id,
                                Meeting.calendar_event_id == event_id
                            )
                        ).first()
                        
                        if existing:
                            if existing.status == "scheduled":
                                # Start transcription
                                asyncio.create_task(start_meeting_transcription(existing.id))
                        else:
                            # Create new meeting and start transcription
                            start_time = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
                            end_time = datetime.fromisoformat(event['end'].get('dateTime', event['end'].get('date')))
                            
                            meeting = meeting_service.create_meeting(
                                user_id=user.id,
                                meet_link=meet_link,
                                title=event.get('summary', 'Untitled Meeting'),
                                start_time=start_time,
                                end_time=end_time,
                                calendar_event_id=event_id,
                                is_manual=False
                            )
                            
                            # Start transcription in background
                            asyncio.create_task(start_meeting_transcription(meeting.id))
                
                except Exception as user_error:
                    logger.error(f"Error processing calendar for user {user.id}: {user_error}")
                    continue
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error in calendar polling service: {e}")
        
        # Poll every minute
        await asyncio.sleep(60)


async def start_meeting_transcription(meeting_id: int):
    try:
        db: Session = SessionLocal()
        meeting_service = MeetingService(db)
        
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            logger.error(f"Meeting {meeting_id} not found")
            return
        
        # Update status to active
        meeting_service.update_meeting_status(meeting_id, "active")
        
        # Create transcription service
        transcription_service = TranscriptionService(meeting_id, db)
        active_meetings[meeting_id] = transcription_service
        
        logger.info(f"Started transcription for meeting {meeting_id}")
        
        # Start transcription (will run until stopped)
        await transcription_service.start()
        
    except Exception as e:
        logger.error(f"Error starting transcription for meeting {meeting_id}: {e}")
    finally:
        db.close()


async def stop_meeting_transcription(meeting_id: int):
    # Stop transcription and generate summary
    try:
        if meeting_id in active_meetings:
            transcription_service = active_meetings[meeting_id]
            await transcription_service.stop()
            del active_meetings[meeting_id]
            
            logger.info(f"Stopped transcription for meeting {meeting_id}")
            
            # Generate summary
            db: Session = SessionLocal()
            meeting_service = MeetingService(db)
            meeting_service.update_meeting_status(meeting_id, "completed")
            
            summary = await meeting_service.generate_summary(meeting_id)
            logger.info(f"Generated summary for meeting {meeting_id}")
            
            db.close()
        else:
            logger.warning(f"Meeting {meeting_id} not found in active meetings")
            
    except Exception as e:
        logger.error(f"Error stopping meeting {meeting_id}: {e}")