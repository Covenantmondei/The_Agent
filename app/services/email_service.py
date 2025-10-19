from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError
from email.mime.text import MIMEText
import base64
import os
import dotenv
from typing import List, Dict, Optional
import re
from bs4 import BeautifulSoup
from .ai_processor import ai_processor

dotenv.load_dotenv()


class GmailService:
    def __init__(self, user, db=None):
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
            scopes=[
                'https://www.googleapis.com/auth/gmail.modify',
                'https://www.googleapis.com/auth/gmail.readonly'
            ]
        )
        self.service = build('gmail', 'v1', credentials=self.creds)

    def _refresh_tokens_if_needed(self):
        """Check if tokens were refreshed and update database"""
        if self.db and self.creds.token != self.user.google_access_token:
            self.user.google_access_token = self.creds.token
            if self.creds.refresh_token:
                self.user.google_refresh_token = self.creds.refresh_token
            self.db.commit()

    def list_messages(self, max_results=10, query="is:unread"):
        """List emails with optional query filter"""
        try:
            results = self.service.users().messages().list(
                userId='me',
                maxResults=max_results,
                q=query
            ).execute()
            
            self._refresh_tokens_if_needed()
            return results.get('messages', [])
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")

    def get_message(self, message_id: str) -> Dict:
        """Get full email content and parse it"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')

            # Extract body
            body = self._extract_body(message['payload'])
            
            self._refresh_tokens_if_needed()

            return {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body,
                'snippet': message.get('snippet', ''),
                'thread_id': message.get('threadId', '')
            }
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")

    def _extract_body(self, payload: Dict) -> str:
        """Extract email body from payload"""
        body = ""

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
                elif part['mimeType'] == 'text/html':
                    if 'data' in part['body']:
                        html_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        body = self._html_to_text(html_body)
        else:
            if 'body' in payload and 'data' in payload['body']:
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

        return body.strip()

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text"""
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text(separator='\n', strip=True)

    def mark_as_read(self, message_id: str):
        """Mark email as read"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            self._refresh_tokens_if_needed()
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")

    def send_email(self, to: str, subject: str, body: str, reply_to_message_id: str = None):
        """Send email via Gmail"""
        try:
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject

            if reply_to_message_id:
                # Get original message to include In-Reply-To and References headers
                original = self.service.users().messages().get(
                    userId='me',
                    id=reply_to_message_id,
                    format='metadata',
                    metadataHeaders=['Message-ID']
                ).execute()

                headers = original['payload']['headers']
                message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)

                if message_id:
                    message['In-Reply-To'] = message_id
                    message['References'] = message_id

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message, 'threadId': reply_to_message_id}
            ).execute()
            
            self._refresh_tokens_if_needed()
            return send_message
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")

    def process_email_with_ai(self, message_id: str) -> Dict:
        """
        Fetch email, summarize it, and draft a reply using AI
        
        Returns:
            Dict with email details, summary, drafted reply, and action items
        """
        # Get email
        email = self.get_message(message_id)

        # AI Processing
        summary = ai_processor.summarize_email(
            email['body'],
            email['sender'],
            email['subject']
        )

        drafted_reply = ai_processor.draft_reply(
            email['body'],
            email['sender'],
            email['subject']
        )

        category = ai_processor.categorize_email(
            email['body'],
            email['subject']
        )

        action_items = ai_processor.extract_action_items(email['body'])

        return {
            **email,
            'summary': summary,
            'drafted_reply': drafted_reply,
            'category': category,
            'action_items': action_items
        }

    def fetch_and_process_unread_emails(self, max_results: int = 10) -> List[Dict]:
        """
        Fetch all unread emails and process them with AI
        
        Returns:
            List of processed emails with summaries and drafted replies
        """
        unread_messages = self.list_messages(max_results=max_results, query="is:unread")
        processed_emails = []

        for msg in unread_messages:
            try:
                processed = self.process_email_with_ai(msg['id'])
                processed_emails.append(processed)
            except Exception as e:
                print(f"Error processing email {msg['id']}: {e}")
                continue

        return processed_emails