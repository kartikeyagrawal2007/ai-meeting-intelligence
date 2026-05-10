from utils.logger import get_logger

log = get_logger(__name__)


def analyze_interruptions(transcript: dict, threshold_ms: int = 500):
    """
    Detect speaker interruptions based on overlapping speech.

    Args:
        transcript: AssemblyAI transcript dict
        threshold_ms: overlap threshold in milliseconds

    Returns:
        List of interruption events
    """

    utterances = transcript.get("utterances", [])
    interruptions = []

    for i in range(1, len(utterances)):
        prev = utterances[i - 1]
        curr = utterances[i]

        prev_end = prev.get("end", 0)
        curr_start = curr.get("start", 0)

        overlap = prev_end - curr_start

        if overlap > threshold_ms:
            interruptions.append({
                "interrupter": curr.get("speaker"),
                "interrupted": prev.get("speaker"),
                "overlap_ms": overlap,
                "text": curr.get("text", "")
            })

    log.info(f"Detected {len(interruptions)} interruptions")

    return interruptions# 
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
