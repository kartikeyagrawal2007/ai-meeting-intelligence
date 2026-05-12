from utils.logger import get_logger

log = get_logger(__name__)

def transcribe_audio(audio_path: str, provider: str = "assemblyai") -> dict:
    """Transcribe audio using specified provider."""

    if provider == "assemblyai":
        from transcription.providers.assemblyai_provider import AssemblyAIProvider
        transcriber = AssemblyAIProvider()
        return transcriber.transcribe(audio_path)

    elif provider == "groq":
        from transcription.providers.groq_whisper_provider import GroqWhisperProvider
        transcriber = GroqWhisperProvider()
        return transcriber.transcribe(audio_path)

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'assemblyai' or 'groq'")