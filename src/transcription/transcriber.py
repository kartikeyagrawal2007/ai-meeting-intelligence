from utils.logger import get_logger

log = get_logger(__name__)

# Map language_mode values to Whisper/Groq language codes
_LANGUAGE_MAP = {
    "auto":     None,     # let Whisper auto-detect
    "en":       "en",
    "codemix":  None,     # multilingual — let Whisper auto-detect
    "hi":       "hi",
    "te":       "te",
    "ta":       "ta",
    "kn":       "kn",
    "ml":       "ml",
}


def transcribe_audio(
    audio_path: str,
    provider: str = "assemblyai",
    language_mode: str = "auto",
) -> dict:
    """Transcribe audio using specified provider.

    Args:
        audio_path:     Path to the audio file.
        provider:       One of 'assemblyai', 'groq', 'pyannote'.
                        'pyannote' → local speaker diarization (pyannote/speaker-diarization-3.1
                        + pyannote/segmentation-3.0) combined with Groq Whisper transcription.
        language_mode:  Language hint passed to the transcription backend.
                        'auto' / 'codemix' → let Whisper detect automatically.
    """
    lang = _LANGUAGE_MAP.get(language_mode, None)

    if provider == "assemblyai":
        from transcription.providers.assemblyai_provider import AssemblyAIProvider
        transcriber = AssemblyAIProvider()
        return transcriber.transcribe(audio_path)

    elif provider == "groq":
        from transcription.providers.groq_whisper_provider import GroqWhisperProvider
        transcriber = GroqWhisperProvider()
        return transcriber.transcribe(audio_path, language=lang)

    elif provider == "pyannote":
        from transcription.providers.pyannote_provider import PyAnnoteProvider
        transcriber = PyAnnoteProvider()
        return transcriber.transcribe(audio_path, language=lang)

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'assemblyai', 'groq', or 'pyannote'")