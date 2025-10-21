from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError
from sqlalchemy.orm import Session
from ..db.models.user import User
from ..db.models.calendar import CalendarEvent
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import dotenv
dotenv.load_dotenv()

# Match EXACTLY the scopes from auth.py
CALENDAR_SCOPES = [
    'openid',
    'email',
    'profile',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.modify'
]

class GoogleCalendarService:
    def __init__(self, user: User, db: Session = None):
        self.user = user
        self.db = db
        
        if not user.google_refresh_token:
            raise ValueError("User does not have a valid Google refresh token")
        
        self.creds = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
            scopes=CALENDAR_SCOPES
        )
        self.service = build('calendar', 'v3', credentials=self.creds)
    
    def refresh_tokens(self):
        try:
            if self.db and self.creds.token != self.user.google_access_token:
                self.user.google_access_token = self.creds.token
                if self.creds.refresh_token:
                    self.user.google_refresh_token = self.creds.refresh_token
                self.db.commit()
                self.db.refresh(self.user)
        except Exception as e:
            print(f"Error updating tokens: {e}")
    
    def list_calendars(self) -> List[Dict]:
        try:
            calendar_list = self.service.calendarList().list().execute()
            self.refresh_tokens()
            return calendar_list.get('items', [])
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def fetch_events(
        self, 
        max_results: int = 10, 
        time_min: datetime = None, 
        time_max: datetime = None,
        calendar_id: str = 'primary',
        query: str = None
    ) -> List[Dict]:
        """Fetch events from Google Calendar with flexible filtering"""
        try:
            if not time_min:
                time_min = datetime.utcnow()
            
            params = {
                'calendarId': calendar_id,
                'timeMin': time_min.isoformat() + 'Z',
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            
            if time_max:
                params['timeMax'] = time_max.isoformat() + 'Z'
            
            if query:
                params['q'] = query
            
            events_result = self.service.events().list(**params).execute()
            
            self.refresh_tokens()
            return events_result.get('items', [])
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def get_event(self, event_id: str, calendar_id: str = 'primary') -> Dict:
        """Get specific event details"""
        try:
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            self.refresh_tokens()
            return event
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str = None,
        location: str = None,
        attendees: List[str] = None,
        timezone: str = 'UTC',
        reminders: Dict = None,
        calendar_id: str = 'primary',
        conference_data: bool = False
    ) -> Dict:
        try:
            event = {
                'summary': title,
                'description': description,
                'location': location,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': timezone
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': timezone
                },
            }
            
            # Add attendees if provided
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            # Add reminders
            if reminders:
                event['reminders'] = reminders
            else:
                event['reminders'] = {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 30},
                    ],
                }
            
            # Add Google Meet link if requested
            if conference_data:
                event['conferenceData'] = {
                    'createRequest': {
                        'requestId': f"meet-{datetime.utcnow().timestamp()}",
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                }
            
            # Create event
            params = {'calendarId': calendar_id, 'body': event}
            if conference_data:
                params['conferenceDataVersion'] = 1
            
            result = self.service.events().insert(**params).execute()
            
            self.refresh_tokens()
            
            # Store in local database
            if self.db:
                self.store_event(result)
            
            return result
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def create_meeting_from_email(
        self,
        email_sender: str,
        subject: str,
        suggested_time: datetime = None,
        duration_minutes: int = 60,
        description: str = None
    ) -> Dict:
        if not suggested_time:
            # Default to next business day at 10 AM
            suggested_time = datetime.utcnow() + timedelta(days=1)
            suggested_time = suggested_time.replace(hour=10, minute=0, second=0, microsecond=0)
        
        end_time = suggested_time + timedelta(minutes=duration_minutes)
        
        # Extract email from sender string
        sender_email = email_sender
        if '<' in email_sender:
            sender_email = email_sender.split('<')[1].strip('>')
        
        title = f"Meeting: {subject}"
        if not description:
            description = f"Meeting scheduled via email with {email_sender}"
        
        return self.create_event(
            title=title,
            start_time=suggested_time,
            end_time=end_time,
            description=description,
            attendees=[sender_email],
            conference_data=True
        )
    
    def update_event(
        self,
        event_id: str,
        calendar_id: str = 'primary',
        **kwargs
    ) -> Dict:
        try:
            # Get current event
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update fields
            if 'title' in kwargs:
                event['summary'] = kwargs.pop('title')
            if 'start_time' in kwargs:
                event['start']['dateTime'] = kwargs.pop('start_time').isoformat()
            if 'end_time' in kwargs:
                event['end']['dateTime'] = kwargs.pop('end_time').isoformat()
            if 'attendees' in kwargs:
                event['attendees'] = [{'email': email} for email in kwargs.pop('attendees')]
            
            # Update remaining kwargs
            event.update(kwargs)
            
            # Send update
            result = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            self.refresh_tokens()
            
            # Update local database
            if self.db:
                self.update_event(result)
            
            return result
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def cancel_event(self, event_id: str, calendar_id: str = 'primary', send_updates: str = 'all'):
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates=send_updates  # 'all', 'externalOnly', 'none'
            ).execute()
            
            self.refresh_tokens()
            
            # Remove from local database
            if self.db:
                self.delete_event(event_id)
                
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def find_time_slot(
        self,
        date: datetime,
        duration_minutes: int = 60,
        working_hours_start: int = 9,
        working_hours_end: int = 17
    ) -> List[Dict]:
        """Find available time slots on a given date"""
        try:
            # Set time range for the day
            time_min = date.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
            time_max = date.replace(hour=working_hours_end, minute=0, second=0, microsecond=0)
            
            # Get busy times from freebusy query
            body = {
                "timeMin": time_min.isoformat() + 'Z',
                "timeMax": time_max.isoformat() + 'Z',
                "items": [{"id": "primary"}]
            }
            
            freebusy_result = self.service.freebusy().query(body=body).execute()
            busy_times = freebusy_result['calendars']['primary']['busy']
            
            # Calculate free slots
            free_slots = []
            current_time = time_min
            
            for busy in busy_times:
                busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                
                # Add free slot before busy period
                if (busy_start - current_time).total_seconds() >= duration_minutes * 60:
                    free_slots.append({
                        'start': current_time.isoformat(),
                        'end': busy_start.isoformat(),
                        'duration_minutes': int((busy_start - current_time).total_seconds() / 60)
                    })
                
                current_time = max(current_time, busy_end)
            
            # Add final slot if there's time left
            if (time_max - current_time).total_seconds() >= duration_minutes * 60:
                free_slots.append({
                    'start': current_time.isoformat(),
                    'end': time_max.isoformat(),
                    'duration_minutes': int((time_max - current_time).total_seconds() / 60)
                })
            
            self.refresh_tokens()
            return free_slots
            
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def store_event(self, google_event: Dict):
        try:
            existing = self.db.query(CalendarEvent).filter(
                CalendarEvent.google_event_id == google_event['id']
            ).first()
            
            if not existing:
                start_time = datetime.fromisoformat(
                    google_event['start'].get('dateTime', google_event['start'].get('date'))
                )
                end_time = datetime.fromisoformat(
                    google_event['end'].get('dateTime', google_event['end'].get('date'))
                )
                
                event = CalendarEvent(
                    user_id=self.user.id,
                    google_event_id=google_event['id'],
                    title=google_event.get('summary', 'No Title'),
                    description=google_event.get('description'),
                    start_time=start_time,
                    end_time=end_time,
                    location=google_event.get('location')
                )
                self.db.add(event)
                self.db.commit()
        except Exception as e:
            print(f"Error storing event locally: {e}")
    
    def update_event(self, google_event: Dict):
        try:
            event = self.db.query(CalendarEvent).filter(
                CalendarEvent.google_event_id == google_event['id']
            ).first()
            
            if event:
                event.title = google_event.get('summary', event.title)
                event.description = google_event.get('description')
                event.location = google_event.get('location')
                self.db.commit()
        except Exception as e:
            print(f"Error updating event locally: {e}")
    
    def delete_event(self, event_id: str):
        try:
            event = self.db.query(CalendarEvent).filter(
                CalendarEvent.google_event_id == event_id
            ).first()
            if event:
                self.db.delete(event)
                self.db.commit()
        except Exception as e:
            print(f"Error deleting event locally: {e}")