"""
transcription/providers/sarvam_provider.py
──────────────────────────────────────────
Sarvam REST API with chunking implementation.
"""

from __future__ import annotations

import os
import time
import subprocess
import tempfile
import requests

from utils.config import SARVAM_API_KEY, SARVAM_BASE_URL
from utils.logger import get_logger

log = get_logger(__name__)

CHUNK_DURATION_SEC = 25
REST_ENDPOINT = "/speech-to-text"
DEFAULT_LANGUAGE_MODE = "codemix"
SARVAM_CHUNK_DELAY_SEC = 1.5
SARVAM_RETRY_DELAY_SEC = 10
SARVAM_MAX_RETRIES = 3

class SarvamProvider:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or SARVAM_API_KEY
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is not set in environment.")
        self.base_url = SARVAM_BASE_URL
        self.headers = {"api-subscription-key": self.api_key}
        self.rest_url = f"{self.base_url}{REST_ENDPOINT}"

    def transcribe(self, audio_path: str, language_mode: str = DEFAULT_LANGUAGE_MODE) -> dict:
        audio_path = os.path.abspath(audio_path)
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        log.info(f"[Sarvam] Starting transcription: {audio_path} | mode={language_mode}")

        total_duration = self._get_duration_ffprobe(audio_path)
        log.info(f"[Sarvam] Audio duration: {total_duration:.2f}s")

        with tempfile.TemporaryDirectory(prefix="sarvam_chunks_") as tmp_dir:
            chunk_paths = self._split_audio(audio_path, tmp_dir, total_duration)
            log.info(f"[Sarvam] Split into {len(chunk_paths)} chunk(s)")

            sarvam_chunks: list[dict] = []
            time_offset_ms = 0

            for idx, (chunk_path, chunk_start_sec, chunk_dur_sec) in enumerate(chunk_paths):
                log.info(f"[Sarvam] Chunk {idx + 1}/{len(chunk_paths)} (offset {chunk_start_sec:.1f}s, dur {chunk_dur_sec:.1f}s)")
                chunk_end_ms = time_offset_ms + int(chunk_dur_sec * 1000)

                if idx > 0:
                    time.sleep(SARVAM_CHUNK_DELAY_SEC)

                try:
                    text = self._transcribe_chunk_with_retry(chunk_path, language_mode)
                except Exception as e:
                    log.error(f"[Sarvam] Chunk {idx + 1} failed after retries: {e}. Skipping.")
                    time_offset_ms = chunk_end_ms
                    continue

                if text:
                    sarvam_chunks.append({
                        "start_ms": time_offset_ms,
                        "end_ms": chunk_end_ms,
                        "text": text,
                    })
                time_offset_ms = chunk_end_ms

        full_text = " ".join(c["text"] for c in sarvam_chunks).strip()
        
        if sarvam_chunks:
            start_ms = sarvam_chunks[0]["start_ms"]
            end_ms = sarvam_chunks[-1]["end_ms"]
        else:
            start_ms = 0
            end_ms = int(total_duration * 1000)

        utterances = [{
            "speaker": "A",
            "text": full_text,
            "start": start_ms,
            "end": end_ms
        }]

        return {
            "id": f"sarvam_{int(time.time())}",
            "text": full_text,
            "utterances": utterances,
            "status": "completed",
        }

    def _get_duration_ffprobe(self, audio_path: str) -> float:
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
            return float(result.stdout.strip())
        except Exception as e:
            log.warning(f"[Sarvam] ffprobe failed ({e}), defaulting to 60s duration.")
            return 60.0

    def _split_audio(self, audio_path: str, output_dir: str, total_duration: float) -> list:
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
                "-ar", "16000",
                "-ac", "1",
                "-f", "wav",
                chunk_path,
            ]

            log.debug(f"[Sarvam] ffmpeg: {' '.join(cmd)}")
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

    def _transcribe_chunk_with_retry(self, chunk_path: str, language_mode: str) -> str:
        for attempt in range(1, SARVAM_MAX_RETRIES + 1):
            try:
                return self._transcribe_chunk(chunk_path, language_mode)
            except RuntimeError as exc:
                if "429" in str(exc) and attempt < SARVAM_MAX_RETRIES:
                    wait = SARVAM_RETRY_DELAY_SEC * attempt
                    log.warning(f"[Sarvam] Rate-limited (429). Waiting {wait}s before retry (attempt {attempt}/{SARVAM_MAX_RETRIES}) …")
                    time.sleep(wait)
                else:
                    raise

    def _transcribe_chunk(self, chunk_path: str, language_mode: str) -> str:
        with open(chunk_path, "rb") as f:
            files = {
                "file": (os.path.basename(chunk_path), f, "audio/wav"),
            }
            data = {
                "model": "saaras:v3",
                "mode": language_mode,
                "language_code": "hi-IN",
            }
            response = requests.post(
                self.rest_url,
                headers=self.headers,
                files=files,
                data=data,
                timeout=120,
            )

        if response.status_code != 200:
            raise RuntimeError(f"Sarvam REST API error {response.status_code}: {response.text[:300]}")

        result = response.json()
        return result.get("transcript", "").strip()
