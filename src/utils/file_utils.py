import os
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

def ensure_dir(path: str):
    """Ensure directory exists, create if not."""
    Path(path).mkdir(parents=True, exist_ok=True)

def get_output_path(input_path: str, suffix: str, output_dir: str = None) -> str:
    """Generate output path based on input path."""
    base = os.path.splitext(os.path.basename(input_path))[0]
    if output_dir:
        ensure_dir(output_dir)
        return os.path.join(output_dir, f"{base}{suffix}")
    return f"{os.path.splitext(input_path)[0]}{suffix}"

def list_audio_files(directory: str, extensions: list = None) -> list:
    """List all audio files in directory."""
    if extensions is None:
        extensions = [".mp3", ".wav", ".m4a", ".aiff", ".flac"]
    files = []
    for ext in extensions:
        files.extend(Path(directory).glob(f"*{ext}"))
    return [str(f) for f in files]
