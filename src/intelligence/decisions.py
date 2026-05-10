# TODO: Implement dedicated decision extraction
# 
# This will extract decisions with higher precision than the general extractor
# 
# Usage:
#   from intelligence.decisions import extract_decisions
#   decisions = extract_decisions(transcript)

from utils.logger import get_logger

log = get_logger(__name__)

def extract_decisions(transcript: dict) -> list:
    """
    Extract decisions from transcript with high precision.
    
    Returns:
        List of decisions with participants and source quote
    """
    log.warning("Dedicated decision extraction not yet implemented")
    raise NotImplementedError("Decisions module coming soon")
