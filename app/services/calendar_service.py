from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError
from sqlalchemy.orm import Session
from ..db.models.user import User
from ..db.models.calendar import CalendarEvent
from datetime import datetime
import os
import dotenv
dotenv.load_dotenv()

class GoogleCalendarService:
    def __init__(self, user: User, db: Session = None):
        self.user = user
        self.db = db
        
        # Ensure all required fields are present
        if not user.google_refresh_token:
            raise ValueError("User does not have a valid Google refresh token")
        
        self.creds = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
            scopes=[
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/calendar.events'
            ]
        )
        self.service = build('calendar', 'v3', credentials=self.creds)
    
    def _refresh_tokens_if_needed(self):
        """Check if tokens were refreshed and update database"""
        if self.db and self.creds.token != self.user.google_access_token:
            self.user.google_access_token = self.creds.token
            if self.creds.refresh_token:
                self.user.google_refresh_token = self.creds.refresh_token
            self.db.commit()
    
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
            
            self._refresh_tokens_if_needed()
            return events_result.get('items', [])
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def create_event(self, title: str, start_time: datetime, end_time: datetime, description: str = None, location: str = None):
        """Create a new calendar event"""
        try:
            event = {
                'summary': title,
                'description': description,
                'location': location,
                'start': {'dateTime': start_time.isoformat(), 'timeZone': 'UTC'},
                'end': {'dateTime': end_time.isoformat(), 'timeZone': 'UTC'},
            }
            
            result = self.service.events().insert(calendarId='primary', body=event).execute()
            
            self._refresh_tokens_if_needed()
            return result
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def update_event(self, event_id: str, **kwargs):
        """Update existing event"""
        try:
            event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
            event.update(kwargs)
            result = self.service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            
            self._refresh_tokens_if_needed()
            return result
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")
    
    def delete_event(self, event_id: str):
        """Delete calendar event"""
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            self._refresh_tokens_if_needed()
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")