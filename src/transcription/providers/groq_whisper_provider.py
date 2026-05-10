# TODO: Implement Groq Whisper transcription provider
# 
# This will use Groq's Whisper API for fast cloud transcription
# 
# Usage:
#   from transcription.providers.groq_whisper_provider import GroqWhisperProvider
#   provider = GroqWhisperProvider()
#   result = provider.transcribe(audio_path)

from utils.logger import get_logger

log = get_logger(__name__)

class GroqWhisperProvider:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        log.warning("GroqWhisperProvider not yet implemented")
    
    def transcribe(self, audio_path: str) -> dict:
        raise NotImplementedError("Groq Whisper provider coming soon")
