# TODO: Implement interruption detection
# 
# Detect when speakers interrupt each other
# 
# Usage:
#   from analytics.interruptions import detect_interruptions
#   interruptions = detect_interruptions(transcript)

from utils.logger import get_logger

log = get_logger(__name__)

def detect_interruptions(transcript: dict) -> list:
    """Detect speaker interruptions."""
    log.warning("Interruption detection not yet implemented")
    raise NotImplementedError("Interruptions module coming soon")
