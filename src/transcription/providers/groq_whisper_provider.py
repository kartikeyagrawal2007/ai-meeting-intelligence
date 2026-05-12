import os
import json
import math
import subprocess
import tempfile
from groq import Groq
from utils.config import GROQ_API_KEY
from utils.logger import get_logger

log = get_logger(__name__)

MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class GroqWhisperProvider:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = "whisper-large-v3"

    def _get_file_size(self, path: str) -> int:
        return os.path.getsize(path)

    def _split_audio(self, audio_path: str, chunk_minutes: int = 10) -> list[str]:
        """Split audio into chunks for large files."""
        log.info(f"Splitting audio into {chunk_minutes} minute chunks...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # get duration
            result = subprocess.run([
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                audio_path
            ], capture_output=True, text=True)

            duration = float(result.stdout.strip())
            chunk_seconds = chunk_minutes * 60
            num_chunks = math.ceil(duration / chunk_seconds)

            log.info(f"Audio duration: {duration:.0f}s → {num_chunks} chunks")

            chunk_paths = []
            for i in range(num_chunks):
                start = i * chunk_seconds
                chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")

                subprocess.run([
                    "ffmpeg", "-y",
                    "-i", audio_path,
                    "-ss", str(start),
                    "-t", str(chunk_seconds),
                    "-acodec", "libmp3lame",
                    "-ar", "16000",
                    "-ac", "1",
                    chunk_path
                ], capture_output=True)

                chunk_paths.append(chunk_path)

            return chunk_paths, duration

    def _transcribe_chunk(self, audio_path: str, offset_seconds: float = 0) -> list[dict]:
        """Transcribe a single audio chunk."""
        with open(audio_path, "rb") as f:
            response = self.client.audio.transcriptions.create(
                model=self.model,
                file=f,
                response_format="verbose_json",
                language="en",
                timestamp_granularities=["segment"]
            )

        segments = []
        for seg in response.segments:
            # handle both dict and object responses
            if isinstance(seg, dict):
                start = seg.get("start", 0)
                end = seg.get("end", 0)
                text = seg.get("text", "").strip()
            else:
                start = seg.start
                end = seg.end
                text = seg.text.strip()

            segments.append({
                "start": int((start + offset_seconds) * 1000),
                "end": int((end + offset_seconds) * 1000),
                "text": text,
                "speaker": "A"
            })

        return segments

    def transcribe(self, audio_path: str) -> dict:
        log.info(f"Transcribing with Groq Whisper large-v3: {audio_path}")

        file_size = self._get_file_size(audio_path)

        if file_size <= MAX_FILE_SIZE_BYTES:
            # small file — transcribe directly
            log.info("File within size limit, transcribing directly...")
            segments = self._transcribe_chunk(audio_path, offset_seconds=0)
        else:
            # large file — split into chunks
            log.info(f"File too large ({file_size / 1024 / 1024:.1f}MB), splitting...")
            chunk_paths, total_duration = self._split_audio(audio_path)

            segments = []
            for i, chunk_path in enumerate(chunk_paths):
                offset = i * 10 * 60  # 10 minutes per chunk
                log.info(f"Transcribing chunk {i+1}/{len(chunk_paths)}...")
                chunk_segments = self._transcribe_chunk(chunk_path, offset)
                segments.extend(chunk_segments)

        # build utterances from segments
        utterances = []
        for seg in segments:
            if seg["text"]:
                utterances.append({
                    "speaker": seg["speaker"],
                    "text": seg["text"],
                    "start": seg["start"],
                    "end": seg["end"]
                })

        full_text = " ".join(s["text"] for s in segments)

        log.info(f"Transcription complete. {len(utterances)} segments.")

        return {
            "id": "groq_whisper",
            "text": full_text,
            "utterances": utterances,
            "status": "completed"
        }