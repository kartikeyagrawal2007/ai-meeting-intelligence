from utils.logger import get_logger

log = get_logger(__name__)


def transcribe_audio(audio_path: str, provider: str = "assemblyai") -> dict:
    """Transcribe audio using specified provider.

    Args:
        audio_path: Path to the audio file.
        provider: One of 'assemblyai', 'groq', 'pyannote'.
                  'pyannote' → local speaker diarization (pyannote/speaker-diarization-3.1
                  + pyannote/segmentation-3.0) combined with Groq Whisper transcription.
    """

    if provider == "assemblyai":
        from transcription.providers.assemblyai_provider import AssemblyAIProvider
        transcriber = AssemblyAIProvider()
        return transcriber.transcribe(audio_path)

    elif provider == "groq":
        from transcription.providers.groq_whisper_provider import GroqWhisperProvider
        transcriber = GroqWhisperProvider()
        return transcriber.transcribe(audio_path)

    elif provider == "pyannote":
        from transcription.providers.pyannote_provider import PyAnnoteProvider
        transcriber = PyAnnoteProvider()
        return transcriber.transcribe(audio_path)

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'assemblyai', 'groq', or 'pyannote'")