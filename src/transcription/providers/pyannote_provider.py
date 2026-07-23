"""
PyAnnote provider — local speaker diarization via HuggingFace models
pyannote/speaker-diarization-3.1  (uses pyannote/segmentation-3.0 internally)

Pipeline:
  1. Run pyannote.audio on-device to get speaker segments with timestamps.
  2. Run Groq Whisper to get the raw word-level transcript with timestamps.
  3. Align each Whisper word to the pyannote speaker segment that covers it.
  4. Merge consecutive words from the same speaker into utterances.

This gives you:
  - Accurate, multi-speaker diarization (real speaker-A / speaker-B labels)
  - High-quality transcription text from Whisper
  - Proper ms-level timestamps on each utterance

Requirements:
  pip install "pyannote.audio>=4.0" groq torch
  ffmpeg must be on the system PATH

HuggingFace setup:
  1. Create an account at https://huggingface.co
  2. Accept terms for ALL of these models (click "Agree" on each page):
     - https://huggingface.co/pyannote/speaker-diarization-3.1
     - https://huggingface.co/pyannote/segmentation-3.0
     - https://huggingface.co/pyannote/speaker-diarization-community-1
  3. Create a fine-grained token at https://huggingface.co/settings/tokens
     with "Read access to contents of all public gated repos you can access"
  4. Set HF_TOKEN=hf_... in your .env file
"""

from __future__ import annotations

import math
import os
import subprocess
import tempfile
import time
from typing import Any

from groq import Groq  # type: ignore[import-untyped]
from utils.config import GROQ_API_KEY, HF_TOKEN  # type: ignore[import-not-found]
from utils.logger import get_logger  # type: ignore[import-not-found]

log = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
GROQ_RETRY_ATTEMPTS = 4
GROQ_RETRY_DELAY_S = 5
SPEAKER_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Diarization model to load from HuggingFace
# pyannote/speaker-diarization-3.1 is the best open-weight model
DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"


# ── Audio conversion ──────────────────────────────────────────────────────────


def _ensure_wav(audio_path: str, tmp_dir: str) -> str:
    """Convert audio to 16 kHz mono WAV (required by pyannote)."""
    wav_path = os.path.join(tmp_dir, "input_16k.wav")
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", audio_path,
            "-ar", "16000", "-ac", "1", "-f", "wav",
            wav_path,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg conversion failed:\n{result.stderr.decode()}"
        )
    return wav_path


# ── Diarization pipeline ──────────────────────────────────────────────────────


def _load_diarization_pipeline() -> Any:
    """Lazy-load the pyannote diarization pipeline.

    Compatible with pyannote.audio >= 4.0 (uses torchcodec, not torchaudio).
    """
    try:
        import torch  # type: ignore[import-untyped]
        from pyannote.audio import Pipeline  # type: ignore[import-untyped]
    except ImportError:
        raise ImportError(
            "pyannote.audio is not installed. Run:\n"
            '  pip install "pyannote.audio>=4.0"'
        )

    if not HF_TOKEN:
        raise ValueError(
            "HF_TOKEN is not set. Please add your HuggingFace token "
            "to .env as HF_TOKEN=hf_... and make sure you have accepted "
            "the model conditions at:\n"
            "  https://huggingface.co/pyannote/speaker-diarization-3.1\n"
            "  https://huggingface.co/pyannote/segmentation-3.0\n"
            "  https://huggingface.co/pyannote/speaker-diarization-community-1"
        )

    log.info(f"Loading {DIARIZATION_MODEL} (first run downloads ~200 MB)...")

    try:
        pipeline = Pipeline.from_pretrained(
            DIARIZATION_MODEL,
            token=HF_TOKEN,
        )
    except Exception as exc:
        err_msg = str(exc)
        if "403" in err_msg or "GatedRepoError" in err_msg:
            raise RuntimeError(
                "HuggingFace returned 403 (access denied). You need to:\n"
                "  1. Go to EACH of these pages and click 'Agree':\n"
                "     - https://huggingface.co/pyannote/speaker-diarization-3.1\n"
                "     - https://huggingface.co/pyannote/segmentation-3.0\n"
                "     - https://huggingface.co/pyannote/speaker-diarization-community-1\n"
                "  2. Create a fine-grained token at:\n"
                "     https://huggingface.co/settings/tokens\n"
                "     with 'Read access to contents of all public gated repos'\n"
                f"\nOriginal error: {err_msg}"
            ) from exc
        raise

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline.to(device)
    log.info(f"Pyannote pipeline loaded on {device}.")
    return pipeline


def _run_diarization(pipeline: Any, wav_path: str) -> list[dict]:
    """Run the diarization pipeline and return speaker segments.

    Returns:
        [{\"speaker\": \"A\", \"start_ms\": int, \"end_ms\": int}, ...]
        Speaker IDs are remapped from pyannote's SPEAKER_00/01 → A/B/C/D.
    """
    log.info("Running speaker diarization (this may take a minute)...")
    result = pipeline(wav_path)

    # pyannote.audio >= 4.0 returns a DiarizeOutput dataclass;
    # extract the Annotation object from it.
    # Use exclusive_speaker_diarization (no overlapping speech)
    # which is ideal for alignment with Whisper segments.
    if hasattr(result, "exclusive_speaker_diarization"):
        diarization = result.exclusive_speaker_diarization
    elif hasattr(result, "speaker_diarization"):
        diarization = result.speaker_diarization
    else:
        # pyannote.audio < 4.0 returned Annotation directly
        diarization = result

    speaker_map: dict[str, str] = {}
    segments: list[dict] = []

    for turn, _, raw_speaker in diarization.itertracks(yield_label=True):
        if raw_speaker not in speaker_map:
            idx = len(speaker_map)
            speaker_map[raw_speaker] = (
                SPEAKER_LABELS[idx] if idx < len(SPEAKER_LABELS) else raw_speaker
            )
        segments.append({
            "speaker": speaker_map[raw_speaker],
            "start_ms": int(turn.start * 1000),
            "end_ms": int(turn.end * 1000),
        })

    log.info(
        f"Diarization complete: {len(segments)} segments, "
        f"{len(speaker_map)} speakers."
    )
    return segments


# ── Speaker alignment ─────────────────────────────────────────────────────────


def _build_speaker_index(segments: list[dict]) -> tuple[list[int], list[dict]]:
    """Pre-sort segments and build a starts index for binary search."""
    sorted_segs = sorted(segments, key=lambda s: s["start_ms"])
    starts = [s["start_ms"] for s in sorted_segs]
    return starts, sorted_segs


def _speaker_at_fast(
    starts: list[int], segments: list[dict], time_ms: float
) -> str:
    """O(log n) speaker lookup via binary search.

    Falls back to the nearest segment boundary if the timestamp
    falls in a gap between segments.
    """
    import bisect

    idx = bisect.bisect_right(starts, time_ms) - 1
    if idx >= 0 and segments[idx]["end_ms"] >= time_ms:
        return segments[idx]["speaker"]

    # Timestamp is in a gap — return nearest segment by boundary distance
    best_idx = 0
    best_dist = float("inf")
    for i, seg in enumerate(segments):
        dist = min(abs(seg["start_ms"] - time_ms), abs(seg["end_ms"] - time_ms))
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return segments[best_idx]["speaker"] if segments else "A"


# ── Groq Whisper transcription ────────────────────────────────────────────────


def _transcribe_chunk_groq(
    client: Any,
    model: str,
    audio_path: str,
    offset_ms: int = 0,
    language: str | None = None,
) -> list[dict]:
    """Transcribe a single file with Groq Whisper; apply ms offset."""
    response = None
    for attempt in range(GROQ_RETRY_ATTEMPTS):
        try:
            with open(audio_path, "rb") as f:
                create_kwargs: dict = dict(
                    model=model,
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"],
                )
                if language:
                    create_kwargs["language"] = language
                response = client.audio.transcriptions.create(**create_kwargs)
            break
        except Exception as e:
            err = str(e)
            if ("403" in err or "429" in err) and attempt < GROQ_RETRY_ATTEMPTS - 1:
                log.warning(
                    f"Groq API error ({err}), "
                    f"waiting {GROQ_RETRY_DELAY_S}s then retrying "
                    f"({attempt + 1}/{GROQ_RETRY_ATTEMPTS - 1})..."
                )
                time.sleep(GROQ_RETRY_DELAY_S)
            elif "403" in err:
                raise RuntimeError(
                    f"Groq API 403 — check VPN / network settings. {err}"
                ) from e
            else:
                raise

    if response is None:
        raise RuntimeError(f"All Groq retry attempts failed for: {audio_path}")

    words: list[dict] = []

    # Prefer word-level timestamps for finer alignment with pyannote segments;
    # fall back to segment-level if word granularity is not available.
    word_list = getattr(response, "words", None)
    if word_list:
        for w in word_list:
            if isinstance(w, dict):
                start = w.get("start", 0)
                end = w.get("end", 0)
                text = w.get("word", w.get("text", "")).strip()
            else:
                start = getattr(w, "start", 0)
                end = getattr(w, "end", 0)
                text = (getattr(w, "word", None) or getattr(w, "text", "")).strip()
            if text:
                words.append({
                    "text": text,
                    "start_ms": int(start * 1000) + offset_ms,
                    "end_ms": int(end * 1000) + offset_ms,
                })
    else:
        # segment-level fallback
        for seg in response.segments:
            if isinstance(seg, dict):
                start = seg.get("start", 0)
                end = seg.get("end", 0)
                text = seg.get("text", "").strip()
            else:
                start = seg.start
                end = seg.end
                text = seg.text.strip()
            if text:
                words.append({
                    "text": text,
                    "start_ms": int(start * 1000) + offset_ms,
                    "end_ms": int(end * 1000) + offset_ms,
                })

    return words


def _transcribe_with_groq_whisper(
    audio_path: str, language: str | None = None
) -> list[dict]:
    """Use Groq Whisper to get segment-level timestamps.

    Returns:
        [{\"text\": str, \"start_ms\": int, \"end_ms\": int}, ...]
    """
    client = Groq(api_key=GROQ_API_KEY)
    model = "whisper-large-v3"
    file_size = os.path.getsize(audio_path)

    if file_size <= MAX_FILE_SIZE_BYTES:
        return _transcribe_chunk_groq(
            client, model, audio_path, offset_ms=0, language=language
        )
    else:
        # Split into 10-min chunks
        log.info("Audio too large for direct Groq upload, splitting into chunks...")
        return _transcribe_chunked_groq(client, model, audio_path, language=language)


def _transcribe_chunked_groq(
    client: Any,
    model: str,
    audio_path: str,
    language: str | None = None,
) -> list[dict]:
    """Split audio and transcribe with offset correction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                audio_path,
            ],
            capture_output=True,
            text=True,
        )
        duration = float(result.stdout.strip())
        chunk_seconds = 10 * 60
        num_chunks = math.ceil(duration / chunk_seconds)

        all_words: list[dict] = []
        for i in range(num_chunks):
            start_sec = i * chunk_seconds
            chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", audio_path,
                    "-ss", str(start_sec), "-t", str(chunk_seconds),
                    "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1",
                    chunk_path,
                ],
                capture_output=True,
            )
            log.info(f"Transcribing chunk {i + 1}/{num_chunks}...")
            words = _transcribe_chunk_groq(
                client, model, chunk_path,
                offset_ms=int(start_sec * 1000),
                language=language,
            )
            all_words.extend(words)

    return all_words


# ── Merging diarization + transcription ────────────────────────────────────────


def _merge_into_utterances(
    whisper_words: list[dict],
    diarization_segments: list[dict],
    pause_threshold_ms: int = 400,
) -> list[dict]:
    """Assign each Whisper word a speaker label from pyannote,
    then merge consecutive same-speaker words into utterances.

    Starts a new utterance on speaker change or a pause > pause_threshold_ms.
    Uses binary-search speaker lookup for O(n log n) overall complexity.
    """
    if not whisper_words:
        return []

    # Build index once for O(log n) per-word lookup
    starts, sorted_segs = _build_speaker_index(diarization_segments)

    labeled: list[dict] = []
    for w in whisper_words:
        mid_ms = (w["start_ms"] + w["end_ms"]) / 2
        speaker = _speaker_at_fast(starts, sorted_segs, mid_ms)
        labeled.append({**w, "speaker": speaker})

    utterances: list[dict] = []
    current = labeled[0].copy()

    for word in labeled[1:]:
        gap_ms = word["start_ms"] - current["end_ms"]
        same_speaker = word["speaker"] == current["speaker"]
        if same_speaker and gap_ms < pause_threshold_ms:
            # Extend current utterance
            current["text"] += " " + word["text"]
            current["end_ms"] = word["end_ms"]
        else:
            utterances.append({
                "speaker": current["speaker"],
                "text": current["text"].strip(),
                "start": current["start_ms"],
                "end": current["end_ms"],
            })
            current = word.copy()

    utterances.append({
        "speaker": current["speaker"],
        "text": current["text"].strip(),
        "start": current["start_ms"],
        "end": current["end_ms"],
    })

    return utterances


# ── Provider class ─────────────────────────────────────────────────────────────


class PyAnnoteProvider:
    """Speaker diarization via pyannote/speaker-diarization-3.1
    + transcription via Groq Whisper large-v3.

    Produces per-speaker utterances with ms-precise timestamps.
    """

    def __init__(self) -> None:
        self._pipeline: Any = None  # loaded lazily on first use

    def transcribe(self, audio_path: str, language: str | None = None) -> dict:
        log.info(f"PyAnnote provider: {audio_path} [lang={language or 'auto'}]")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Convert to 16 kHz mono WAV for pyannote
            wav_path = _ensure_wav(audio_path, tmpdir)

            # Step 2: Load & run diarization
            if self._pipeline is None:
                self._pipeline = _load_diarization_pipeline()
            diarization_segments = _run_diarization(self._pipeline, wav_path)

            # Step 3: Transcribe with Groq Whisper (respects language hint)
            log.info("Transcribing with Groq Whisper large-v3...")
            whisper_words = _transcribe_with_groq_whisper(
                audio_path, language=language
            )

            # Step 4: Merge diarization + transcription
            log.info("Aligning transcription with speaker labels...")
            utterances = _merge_into_utterances(
                whisper_words, diarization_segments
            )

        full_text = " ".join(u["text"] for u in utterances)
        num_speakers = len(set(u["speaker"] for u in utterances))
        log.info(
            f"PyAnnote pipeline complete. "
            f"{len(utterances)} utterances, {num_speakers} speakers."
        )

        return {
            "id": "pyannote_whisper",
            "text": full_text,
            "utterances": utterances,
            "status": "completed",
        }
