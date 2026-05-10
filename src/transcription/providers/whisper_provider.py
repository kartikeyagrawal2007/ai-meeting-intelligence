# TODO: Implement Whisper transcription provider
# 
# This will use OpenAI's Whisper model for local transcription
# 
# Usage:
#   from transcription.providers.whisper_provider import WhisperProvider
#   provider = WhisperProvider(model_size="large-v3")
#   result = provider.transcribe(audio_path)

from utils.logger import get_logger

log = get_logger(__name__)

class WhisperProvider:
    def __init__(self, model_size: str = "large-v3"):
        self.model_size = model_size
        log.warning("WhisperProvider not yet implemented")
    
    def transcribe(self, audio_path: str) -> dict:
        raise NotImplementedError("Whisper provider coming soon")
