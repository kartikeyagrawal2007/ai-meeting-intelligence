import os
import math
import shutil
import subprocess
import tempfile
from groq import Groq  # type: ignore[import-untyped]
from utils.config import GROQ_API_KEY  # type: ignore[import-not-found]
from utils.logger import get_logger  # type: ignore[import-not-found]

log = get_logger(__name__)

MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class GroqWhisperProvider:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = "whisper-large-v3"

    def _get_file_size(self, path: str) -> int:
        return os.path.getsize(path)

    def _split_audio(self, audio_path: str, chunk_minutes: int = 10) -> tuple[list[str], str]:
        """Split audio into chunks for large files.

        Returns (chunk_paths, tmpdir) — the caller is responsible for
        calling shutil.rmtree(tmpdir) once the chunks are no longer needed.
        """
        log.info(f"Splitting audio into {chunk_minutes} minute chunks...")

        # Use mkdtemp so the directory (and chunk files) survive past this method.
        tmpdir = tempfile.mkdtemp(prefix="groq_chunks_")

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

        return chunk_paths, tmpdir

    def _transcribe_chunk(
        self, audio_path: str, offset_seconds: float = 0, language: str | None = None
    ) -> list[dict]:
        """Transcribe a single audio chunk."""
        import time
        response = None
        for attempt in range(4):
            try:
                with open(audio_path, "rb") as f:
                    create_kwargs: dict = dict(
                        model=self.model,
                        file=f,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"],
                        prompt="Technical meeting discussion with action items, decisions, project updates, and team names.",
                    )
                    if language:
                        create_kwargs["language"] = language
                    response = self.client.audio.transcriptions.create(**create_kwargs)
                break
            except Exception as e:
                error_str = str(e)
                if attempt < 3:
                    log.warning(f"Groq API / network error ({error_str}). Retrying in 5s ({attempt+1}/4)...")
                    time.sleep(5)
                elif "403" in error_str:
                    raise Exception(f"Groq API Error 403: Please check your VPN or network settings. {error_str}")
                else:
                    raise

        if response is None:
            raise RuntimeError(f"All Groq retry attempts failed for chunk: {audio_path}")

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

    def transcribe(self, audio_path: str, language: str | None = None) -> dict:
        log.info(f"Transcribing with Groq Whisper large-v3: {audio_path} [lang={language or 'auto'}]")

        file_size = self._get_file_size(audio_path)

        if file_size <= MAX_FILE_SIZE_BYTES:
            # small file — transcribe directly
            log.info("File within size limit, transcribing directly...")
            segments = self._transcribe_chunk(audio_path, offset_seconds=0, language=language)
        else:
            # large file — split into chunks
            log.info(f"File too large ({file_size / 1024 / 1024:.1f}MB), splitting...")
            chunk_paths, chunks_tmpdir = self._split_audio(audio_path)
            try:
                segments = []
                for i, chunk_path in enumerate(chunk_paths):
                    offset = i * 10 * 60  # 10 minutes per chunk
                    log.info(f"Transcribing chunk {i+1}/{len(chunk_paths)}...")
                    chunk_segments = self._transcribe_chunk(chunk_path, offset, language=language)
                    segments.extend(chunk_segments)
            finally:
                shutil.rmtree(chunks_tmpdir, ignore_errors=True)

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