# TODO: Implement live transcription
# 
# This will transcribe audio in real-time as it streams
# 
# Usage:
#   from realtime.live_transcriber import LiveTranscriber
#   transcriber = LiveTranscriber()
#   transcriber.start()

from utils.logger import get_logger

log = get_logger(__name__)

class LiveTranscriber:
    """Transcribe audio in real-time."""
    
    def __init__(self):
        log.warning("LiveTranscriber not yet implemented")
    
    def start(self):
        raise NotImplementedError("Live transcriber coming soon")
