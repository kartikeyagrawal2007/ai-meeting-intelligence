import time
from contextlib import contextmanager
from utils.logger import get_logger

log = get_logger(__name__)

@contextmanager
def timer(name: str):
    """Context manager for timing code blocks."""
    start = time.time()
    log.info(f"Starting: {name}")
    try:
        yield
    finally:
        elapsed = time.time() - start
        log.info(f"Completed: {name} in {elapsed:.2f}s")

class Timer:
    """Simple timer class for tracking execution time."""
    
    def __init__(self):
        self.start_time = None
        self.elapsed = 0
    
    def start(self):
        self.start_time = time.time()
    
    def stop(self):
        if self.start_time:
            self.elapsed = time.time() - self.start_time
            self.start_time = None
        return self.elapsed
    
    def reset(self):
        self.start_time = None
        self.elapsed = 0
