from transcription.providers.assemblyai_provider import AssemblyAIProvider
from utils.logger import get_logger

log = get_logger(__name__)

def transcribe_audio(audio_path: str, provider: str = "assemblyai") -> dict:
    """Transcribe audio using specified provider."""
    if provider == "assemblyai":
        transcriber = AssemblyAIProvider()
        return transcriber.transcribe(audio_path)
    else:
        raise ValueError(f"Unknown provider: {provider}")
