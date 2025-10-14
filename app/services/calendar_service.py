from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from ..db.models.user import User
from ..db.models.calendar import CalendarEvent
from datetime import datetime
import os
import dotenv
dotenv.load_dotenv()

class GoogleCalendarService:
    def __init__(self, user: User):
        self.user = user
        self.creds = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_CLIENT_SECRET")
        )
        self.service = build('calendar', 'v3', credentials=self.creds)
    
    def fetch_events(self, max_results=10):
        """Fetch upcoming events from Google Calendar"""
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=datetime.utcnow().isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            return events_result.get('items', [])
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def create_event(self, title: str, start_time: datetime, end_time: datetime, description: str = None):
        """Create a new calendar event"""
        event = {
            'summary': title,
            'description': description,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'UTC'},
        }
        
        return self.service.events().insert(calendarId='primary', body=event).execute()
    
    def update_event(self, event_id: str, **kwargs):
        """Update existing event"""
        event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
        event.update(kwargs)
        return self.service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
    
    def delete_event(self, event_id: str):
        """Delete calendar event"""
        self.service.events().delete(calendarId='primary', eventId=event_id).execute()