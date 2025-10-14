from gtts import gTTS
import os
from pathlib import Path
from typing import Optional
import uuid


class TTSService:
    """Text-to-Speech service using gTTS"""
    
    def __init__(self):
        self.output_dir = Path("audio_files")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_audio(self, text: str, lang: str = 'en', slow: bool = False) -> str:
        """
        Generate audio file from text
        
        Args:
            text: Text to convert to speech
            lang: Language code (default: 'en')
            slow: Slower speech rate
            
        Returns:
            Path to generated audio file
        """
        try:
            # Generate unique filename
            filename = f"tts_{uuid.uuid4()}.mp3"
            filepath = self.output_dir / filename
            
            # Create TTS object
            tts = gTTS(text=text, lang=lang, slow=slow)
            
            # Save audio file
            tts.save(str(filepath))
            
            return str(filepath)
            
        except Exception as e:
            raise Exception(f"Error generating audio: {e}")
    
    def generate_email_summary_audio(self, summary: str, subject: str, sender: str) -> str:
        """
        Generate audio for email summary with context
        
        Returns:
            Path to generated audio file
        """
        intro = f"Email from {sender}. Subject: {subject}. Summary: "
        full_text = intro + summary
        
        return self.generate_audio(full_text)
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Remove audio files older than specified hours"""
        import time
        current_time = time.time()
        
        for file in self.output_dir.glob("*.mp3"):
            file_age = current_time - file.stat().st_mtime
            if file_age > max_age_hours * 3600:
                file.unlink()


# Singleton instance
tts_service = TTSService()