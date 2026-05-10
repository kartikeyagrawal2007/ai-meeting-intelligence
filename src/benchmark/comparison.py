# TODO: Implement model comparison
# 
# This will compare different transcription providers
# 
# Usage:
#   from benchmark.comparison import compare_providers
#   results = compare_providers(audio_files, providers=["assemblyai", "whisper"])

from utils.logger import get_logger

log = get_logger(__name__)

def compare_providers(audio_files: list, providers: list) -> dict:
    """Compare transcription quality across providers."""
    log.warning("Provider comparison not yet implemented")
    raise NotImplementedError("Comparison module coming soon")
