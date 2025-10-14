import os
from openai import OpenAI
from typing import Dict, List
import dotenv

dotenv.load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class AIProcessor:
    """AI processor for email summarization and reply drafting"""

    def __init__(self):
        self.client = client
        self.model = "gpt-4o-mini"  # or "gpt-3.5-turbo" for cost savings

    def summarize_email(self, email_content: str, sender: str, subject: str) -> str:
        """
        Summarize email content using GPT
        
        Args:
            email_content: The body of the email
            sender: Email sender
            subject: Email subject
            
        Returns:
            A concise summary of the email
        """
        try:
            prompt = f"""
            Summarize the following email in 2-3 sentences. Focus on the main points and action items.
            
            From: {sender}
            Subject: {subject}
            
            Email Content:
            {email_content}
            
            Provide a clear, concise summary that captures the essence of the email.
            """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes emails concisely."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error summarizing email: {e}")
            return f"Unable to summarize: {str(e)}"

    def draft_reply(self, email_content: str, sender: str, subject: str, context: str = None) -> str:
        """
        Draft a professional email reply using GPT
        
        Args:
            email_content: Original email content
            sender: Email sender
            subject: Email subject
            context: Additional context or instructions for the reply
            
        Returns:
            A drafted email reply
        """
        try:
            context_instruction = f"\n\nAdditional context: {context}" if context else ""

            prompt = f"""
            Draft a professional and courteous reply to the following email. 
            The reply should:
            - Be polite and professional
            - Address the main points raised
            - Be concise (2-4 paragraphs)
            - Include appropriate greeting and closing
            {context_instruction}
            
            From: {sender}
            Subject: {subject}
            
            Email Content:
            {email_content}
            
            Draft Reply:
            """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional email assistant that drafts clear, courteous replies."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=500
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error drafting reply: {e}")
            return f"Unable to draft reply: {str(e)}"

    def categorize_email(self, email_content: str, subject: str) -> str:
        """
        Categorize email into categories: urgent, work, personal, promotional, etc.
        
        Returns:
            Category string
        """
        try:
            prompt = f"""
            Categorize this email into ONE of these categories:
            - urgent
            - work
            - personal
            - promotional
            - spam
            - newsletter
            
            Subject: {subject}
            Content: {email_content[:300]}...
            
            Respond with only the category name, nothing else.
            """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You categorize emails efficiently."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=10
            )

            return response.choices[0].message.content.strip().lower()

        except Exception as e:
            print(f"Error categorizing email: {e}")
            return "uncategorized"

    def extract_action_items(self, email_content: str) -> List[str]:
        """
        Extract action items or tasks from email content
        
        Returns:
            List of action items
        """
        try:
            prompt = f"""
            Extract any action items, tasks, or requests from this email.
            List them as bullet points. If there are no action items, respond with "None".
            
            Email Content:
            {email_content}
            """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You extract action items from emails."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=200
            )

            result = response.choices[0].message.content.strip()
            
            if result.lower() == "none":
                return []
            
            # Parse bullet points
            items = [line.strip('- ').strip() for line in result.split('\n') if line.strip()]
            return items

        except Exception as e:
            print(f"Error extracting action items: {e}")
            return []


# Initialize singleton instance
ai_processor = AIProcessor()