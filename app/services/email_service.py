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

# Match EXACTLY the scopes from auth.py OAuth registration
GMAIL_SCOPES = [
    'openid',
    'email',
    'profile',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.modify'
]

# Gmail category labels
GMAIL_CATEGORIES = {
    'CATEGORY_PERSONAL': 'primary',
    'CATEGORY_SOCIAL': 'social',
    'CATEGORY_PROMOTIONS': 'promotions',
    'CATEGORY_UPDATES': 'updates',
    'CATEGORY_FORUMS': 'forums',
    'SPAM': 'spam',
    'TRASH': 'trash'
}

# Priority mapping - higher number = higher priority
PRIORITY_SCORES = {
    'primary': 5,
    'updates': 3,
    'forums': 2,
    'social': 2,
    'promotions': 1,
    'spam': 0,
    'trash': 0,
    'unknown': 3
}


class GmailService:
    def __init__(self, user, db=None):
        self.user = user
        self.db = db
        
        if not user.google_refresh_token:
            raise ValueError("User does not have a valid Google refresh token")
        
        # Use the EXACT same scopes that were authorized during OAuth
        self.creds = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
            scopes=GMAIL_SCOPES
        )
        
        try:
            self.service = build('gmail', 'v1', credentials=self.creds)
        except Exception as e:
            raise ValueError(f"Failed to build Gmail service: {str(e)}")

    def refresh_tokens_if_needed(self):
        try:
            if self.db and self.creds.token != self.user.google_access_token:
                self.user.google_access_token = self.creds.token
                # Refresh token usually doesn't change, but update if it does
                if self.creds.refresh_token and self.creds.refresh_token != self.user.google_refresh_token:
                    self.user.google_refresh_token = self.creds.refresh_token
                self.db.commit()
                self.db.refresh(self.user)
        except Exception as e:
            print(f"Error updating tokens in database: {e}")

    def get_category_from_labels(self, labels: List[str]) -> str:
        if not labels:
            return 'unknown'
        
        for label in labels:
            if label in GMAIL_CATEGORIES:
                return GMAIL_CATEGORIES[label]
        
        if 'INBOX' in labels and 'UNREAD' in labels:
            return 'primary'
        
        return 'unknown'

    def calculate_priority(self, category: str, labels: List[str], sender: str = '') -> int:
        base_priority = PRIORITY_SCORES.get(category, 3)
        
        if 'IMPORTANT' in labels:
            base_priority += 3
        
        if 'STARRED' in labels:
            base_priority += 2
        
        if 'SPAM' in labels or 'TRASH' in labels:
            base_priority = 0
        
        # You can add more rules here
        # important_domains = ['@company.com', '@client.com']
        # for domain in important_domains:
        #     if domain in sender.lower():
        #         base_priority += 2
        #         break
        
        return min(base_priority, 10)

    def list_messages(self, max_results=10, query="is:unread", page_token=None):
        try:
            params = {
                'userId': 'me',
                'maxResults': max_results,
                'q': query
            }
            
            if page_token:
                params['pageToken'] = page_token
            
            results = self.service.users().messages().list(**params).execute()
            
            self.refresh_tokens_if_needed()
            
            return {
                'messages': results.get('messages', []),
                'next_page_token': results.get('nextPageToken'),
                'result_size_estimate': results.get('resultSizeEstimate', 0)
            }
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")

    def get_message_basic(self, message_id: str) -> Dict:
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='metadata',
                metadataHeaders=['Subject', 'From', 'Date']
            ).execute()

            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')

            labels = message.get('labelIds', [])
            category = self.get_category_from_labels(labels)
            priority = self.calculate_priority(category, labels, sender)
            
            # Determine if reply is needed
            requires_reply = category in ['primary', 'unknown'] and 'SENT' not in labels

            self.refresh_tokens_if_needed()

            return {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'snippet': message.get('snippet', ''),
                'thread_id': message.get('threadId', ''),
                'labels': labels,
                'category': category,
                'priority': priority,
                'requires_reply': requires_reply,
                'is_important': 'IMPORTANT' in labels,
                'is_starred': 'STARRED' in labels
            }
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")

    def get_message(self, message_id: str) -> Dict:
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
            body = self.extract_body(message['payload'])
            
            labels = message.get('labelIds', [])
            category = self.get_category_from_labels(labels)
            priority = self.calculate_priority(category, labels, sender)
            
            self.refresh_tokens_if_needed()

            return {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body,
                'snippet': message.get('snippet', ''),
                'thread_id': message.get('threadId', ''),
                'labels': labels,
                'category': category,
                'priority': priority
            }
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")

    def extract_body(self, payload: Dict) -> str:
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
                        body = self.html_to_text(html_body)
        else:
            if 'body' in payload and 'data' in payload['body']:
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

        return body.strip()

    def html_to_text(self, html: str) -> str:
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
            self.refresh_tokens_if_needed()
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")

    def send_email(self, to: str, subject: str, body: str, reply_to_message_id: str = None):
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
            
            self.refresh_tokens_if_needed()
            return send_message
        except RefreshError as error:
            raise Exception(f"Token refresh failed. User needs to re-authenticate: {error}")
        except HttpError as error:
            raise Exception(f"An error occurred: {error}")

    def list_unread_emails_paginated(
        self, 
        max_results: int = 20, 
        page_token: str = None,
        category_filter: str = None
    ) -> Dict:
        """
        List unread emails with pagination and optional category filter - NO AI processing
        Returns basic info only for fast loading, SORTED BY PRIORITY
        """
        # Build query
        query = "is:unread"
        
        # Add category filter if specified
        if category_filter:
            if category_filter == 'primary':
                query += " category:primary"
            elif category_filter == 'social':
                query += " category:social"
            elif category_filter == 'promotions':
                query += " category:promotions"
            elif category_filter == 'updates':
                query += " category:updates"
            elif category_filter == 'forums':
                query += " category:forums"
        
        result = self.list_messages(max_results=max_results, query=query, page_token=page_token)
        
        emails = []
        for msg in result['messages']:
            try:
                email_info = self.get_message_basic(msg['id'])
                emails.append(email_info)
            except Exception as e:
                print(f"Error fetching email {msg['id']}: {e}")
                continue
        
        # Sort by priority (highest first), then by date
        emails.sort(key=lambda x: x['priority'], reverse=True)
        
        # Group by category for better organization
        categorized_emails = {
            'high_priority': [e for e in emails if e['priority'] >= 6],
            'medium_priority': [e for e in emails if 3 <= e['priority'] < 6],
            'low_priority': [e for e in emails if e['priority'] < 3],
            'all': emails
        }
        
        # Category counts
        category_counts = {}
        for email in emails:
            cat = email['category']
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        return {
            'emails': emails,
            'categorized': categorized_emails,
            'category_counts': category_counts,
            'next_page_token': result.get('next_page_token'),
            'total_estimate': result.get('result_size_estimate', 0),
            'count': len(emails)
        }

    def process_email_with_ai(self, message_id: str) -> Dict:

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

        ai_category = ai_processor.categorize_email(
            email['body'],
            email['subject']
        )

        action_items = ai_processor.extract_action_items(email['body'])

        return {
            **email,
            'summary': summary,
            'drafted_reply': drafted_reply,
            'ai_category': ai_category,
            'action_items': action_items
        }