import os
from openai import OpenAI
from typing import Dict, List, AsyncGenerator
import dotenv

dotenv.load_dotenv()

client = OpenAI(api_key="anything", base_url="http://localhost:12434/engines/v1")


class AIProcessor:

    def __init__(self):
        self.client = client
        self.model = "ai/llama3.2:1B-Q4_0"

    def summarize_email(self, email_content: str, sender: str, subject: str) -> str:
        try:
            prompt = f"""
            Summarize the following email in 2-3 concise sentences.
            
            From: {sender}
            Subject: {subject}
            
            Email Content:
            {email_content}
            
            Provide ONLY the summary without any introduction or extra formatting.
            """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You summarize emails concisely in plain text without extra formatting or introductions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error summarizing email: {e}")
            return f"Unable to summarize: {str(e)}"
    
    async def stream_summarize(self, email_content: str, sender: str, subject: str) -> AsyncGenerator[str, None]:
        try:
            prompt = f"""
            Summarize the following email in 2-3 concise sentences.
            
            From: {sender}
            Subject: {subject}
            
            Email Content:
            {email_content}
            
            Provide ONLY the summary without any introduction or extra formatting.
            """

            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You summarize emails concisely in plain text without extra formatting or introductions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            print(f"Error streaming summary: {e}")
            yield f"Unable to summarize: {str(e)}"

    def draft_reply(self, email_content: str, sender: str, subject: str, context: str = None) -> str:
        try:
            context_instruction = f"Additional context: {context}" if context else ""

            prompt = f"""
            Draft a professional and courteous reply to the following email. 
            The reply should:
            - Be polite and professional
            - Address the main points raised
            - Be concise (2-4 paragraphs)
            - Include appropriate greeting and closing
            - Sound like a human wrote it
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
    
    async def stream_reply(self, email_content: str, sender: str, subject: str, context: str = None) -> AsyncGenerator[str, None]:
        try:
            context_instruction = f"Additional context: {context}" if context else ""

            prompt = f"""
            Draft a professional and courteous reply to the following email. 
            The reply should:
            - Be polite and professional
            - Address the main points raised
            - Be concise (2-4 paragraphs)
            - Include appropriate greeting and closing
            - Sound like a human wrote it
            {context_instruction}
            
            From: {sender}
            Subject: {subject}
            
            Email Content:
            {email_content}
            
            Draft Reply:
            """

            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional email assistant that drafts clear, courteous replies."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=500,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            print(f"Error streaming reply: {e}")
            yield f"Unable to draft reply: {str(e)}"

    def categorize_email(self, email_content: str, subject: str) -> str:

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


ai_processor = AIProcessor()