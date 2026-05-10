# TODO: Implement speaker diarization
# 
# This will use pyannote.audio for local speaker diarization
# as an alternative to AssemblyAI's built-in diarization
# 
# Usage:
#   from transcription.diarization import diarize_audio
#   segments = diarize_audio(audio_path)

from utils.logger import get_logger

log = get_logger(__name__)

def diarize_audio(audio_path: str) -> list:
    """
    Perform speaker diarization on audio file.
    
    Returns:
        List of segments with speaker labels and timestamps
    """
    log.warning("Local diarization not yet implemented")
    raise NotImplementedError("Diarization module coming soon")
