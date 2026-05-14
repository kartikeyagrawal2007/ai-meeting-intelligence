import os
import time
import subprocess
import tempfile
import requests
from utils.config import SARVAM_API_KEY, SARVAM_BASE_URL
from utils.logger import get_logger

log = get_logger(__name__)

CHUNK_DURATION_SEC = 25  # Stay safely under the 30-second REST API limit
REST_ENDPOINT = "/speech-to-text"


class SarvamProvider:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or SARVAM_API_KEY
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is not set in environment.")
        self.base_url = SARVAM_BASE_URL
        self.headers = {"api-subscription-key": self.api_key}
        self.rest_url = f"{self.base_url}{REST_ENDPOINT}"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def transcribe(self, audio_path: str) -> dict:
        """
        Transcribe an audio file using Sarvam REST API.

        Strategy:
          1. Split the audio into CHUNK_DURATION_SEC-second chunks via ffmpeg.
          2. Transcribe each chunk individually against the REST endpoint.
          3. Merge results in order and return a unified response dict.
        """
        audio_path = os.path.abspath(audio_path)
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        log.info(f"[Sarvam] Starting transcription for: {audio_path}")

        total_duration = self._get_duration_ffprobe(audio_path)
        log.info(f"[Sarvam] Audio duration: {total_duration:.2f}s")

        with tempfile.TemporaryDirectory(prefix="sarvam_chunks_") as tmp_dir:
            chunk_paths = self._split_audio(audio_path, tmp_dir, total_duration)
            log.info(f"[Sarvam] Split into {len(chunk_paths)} chunk(s)")

            all_utterances = []
            all_texts = []
            time_offset_ms = 0

            for idx, (chunk_path, chunk_start_sec, chunk_dur_sec) in enumerate(chunk_paths):
                log.info(f"[Sarvam] Transcribing chunk {idx + 1}/{len(chunk_paths)} "
                         f"(offset {chunk_start_sec:.1f}s, dur {chunk_dur_sec:.1f}s)")
                try:
                    transcript = self._transcribe_chunk(chunk_path)
                except Exception as e:
                    log.error(f"[Sarvam] Chunk {idx + 1} failed: {e}. Skipping.")
                    time_offset_ms += int(chunk_dur_sec * 1000)
                    continue

                if transcript:
                    all_texts.append(transcript)
                    chunk_end_ms = time_offset_ms + int(chunk_dur_sec * 1000)
                    all_utterances.append({
                        "speaker": "A",
                        "text": transcript,
                        "start": time_offset_ms,
                        "end": chunk_end_ms,
                    })

                time_offset_ms += int(chunk_dur_sec * 1000)

        full_text = " ".join(all_texts).strip()
        log.info(f"[Sarvam] Transcription complete. Total chars: {len(full_text)}")

        return {
            "id": f"sarvam_{int(time.time())}",
            "text": full_text,
            "utterances": all_utterances if all_utterances else [{
                "speaker": "A",
                "text": full_text,
                "start": 0,
                "end": int(total_duration * 1000),
            }],
            "status": "completed",
        }

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------

    def _get_duration_ffprobe(self, audio_path: str) -> float:
        """Return audio duration in seconds using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            duration = float(result.stdout.strip())
            return duration
        except Exception as e:
            log.warning(f"[Sarvam] ffprobe failed ({e}), defaulting to 60s duration.")
            return 60.0

    def _split_audio(self, audio_path: str, output_dir: str, total_duration: float) -> list:
        """
        Split audio into chunks of CHUNK_DURATION_SEC seconds using ffmpeg.

        Returns a list of tuples: (chunk_path, start_sec, actual_chunk_duration_sec)
        """
        chunks = []
        start = 0.0

        while start < total_duration:
            end = min(start + CHUNK_DURATION_SEC, total_duration)
            chunk_dur = end - start
            chunk_index = len(chunks)
            chunk_path = os.path.join(output_dir, f"chunk_{chunk_index:04d}.wav")

            cmd = [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(start),
                "-t", str(chunk_dur),
                "-ar", "16000",   # Sarvam works best at 16 kHz
                "-ac", "1",       # Mono
                "-f", "wav",
                chunk_path,
            ]

            log.debug(f"[Sarvam] ffmpeg chunk cmd: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                log.error(f"[Sarvam] ffmpeg failed for chunk {chunk_index}: {result.stderr[-300:]}")
                start = end
                continue

            if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) == 0:
                log.warning(f"[Sarvam] Empty chunk at {start:.1f}s, skipping.")
                start = end
                continue

            chunks.append((chunk_path, start, chunk_dur))
            start = end

        return chunks

    # ------------------------------------------------------------------
    # REST API call
    # ------------------------------------------------------------------

    def _transcribe_chunk(self, chunk_path: str) -> str:
        """
        POST a single audio chunk to Sarvam REST API and return the transcript string.
        """
        with open(chunk_path, "rb") as f:
            files = {
                "file": (os.path.basename(chunk_path), f, "audio/wav"),
            }
            data = {
                "model": "saaras:v3",
                "mode": "codemix",
                "language_code": "hi-IN",
            }
            log.debug(f"[Sarvam] POST {self.rest_url} for {os.path.basename(chunk_path)}")
            response = requests.post(
                self.rest_url,
                headers=self.headers,
                files=files,
                data=data,
                timeout=120,
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Sarvam REST API error {response.status_code}: {response.text[:300]}"
            )

        result = response.json()
        transcript = result.get("transcript", "").strip()
        log.debug(f"[Sarvam] Chunk transcript ({len(transcript)} chars): {transcript[:80]!r}")
        return transcript
