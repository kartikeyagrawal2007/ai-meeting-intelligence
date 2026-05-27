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
"""

import os
import time
import subprocess
import tempfile
import math

from groq import Groq
from utils.config import GROQ_API_KEY, HF_TOKEN
from utils.logger import get_logger

log = get_logger(__name__)

MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def _ensure_wav(audio_path: str, tmp_dir: str) -> str:
    """Convert audio to 16kHz mono WAV (required by pyannote)."""
    wav_path = os.path.join(tmp_dir, "input_16k.wav")
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", audio_path,
            "-ar", "16000", "-ac", "1", "-f", "wav",
            wav_path
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr.decode()}")
    return wav_path


def _load_diarization_pipeline():
    """Lazy-load the pyannote diarization pipeline."""
    try:
        import torch
        from pyannote.audio import Pipeline

        if not HF_TOKEN:
            raise ValueError(
                "HF_TOKEN is not set. Please add your HuggingFace token "
                "to .env as HF_TOKEN=hf_... and make sure you have accepted "
                "the model conditions at:\n"
                "  https://huggingface.co/pyannote/speaker-diarization-3.1\n"
                "  https://huggingface.co/pyannote/segmentation-3.0"
            )

        log.info("Loading pyannote/speaker-diarization-3.1 (first run downloads weights)...")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=HF_TOKEN,
        )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        pipeline.to(device)
        log.info(f"Pyannote pipeline loaded on {device}.")
        return pipeline

    except ImportError:
        raise ImportError(
            "pyannote.audio is not installed. Run:\n"
            "  pip install pyannote.audio"
        )


def _run_diarization(pipeline, wav_path: str) -> list[dict]:
    """
    Run the diarization pipeline and return a list of speaker segments:
      [{"speaker": "A", "start_ms": int, "end_ms": int}, ...]
    Speaker IDs are remapped from pyannote's SPEAKER_00/01 → A/B/C/D.
    """
    log.info("Running speaker diarization (this may take a minute)...")
    diarization = pipeline(wav_path)

    speaker_map: dict[str, str] = {}
    label_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    segments = []

    for turn, _, raw_speaker in diarization.itertracks(yield_label=True):
        if raw_speaker not in speaker_map:
            idx = len(speaker_map)
            speaker_map[raw_speaker] = label_chars[idx] if idx < len(label_chars) else raw_speaker
        speaker_label = speaker_map[raw_speaker]
        segments.append({
            "speaker": speaker_label,
            "start_ms": int(turn.start * 1000),
            "end_ms": int(turn.end * 1000),
        })

    log.info(f"Diarization complete: {len(segments)} segments, {len(speaker_map)} speakers.")
    return segments


def _speaker_at(diarization_segments: list[dict], time_ms: float) -> str:
    """Return the speaker label at a given timestamp (ms). Falls back to 'A'."""
    for seg in diarization_segments:
        if seg["start_ms"] <= time_ms <= seg["end_ms"]:
            return seg["speaker"]
    # fallback: find nearest
    best = min(diarization_segments, key=lambda s: min(abs(s["start_ms"] - time_ms), abs(s["end_ms"] - time_ms)), default=None)
    return best["speaker"] if best else "A"


def _transcribe_with_groq_whisper(audio_path: str) -> list[dict]:
    """
    Use Groq Whisper to get word-level (segment-level) timestamps.
    Returns a list of dicts:
      [{"text": str, "start_ms": int, "end_ms": int}, ...]
    """
    client = Groq(api_key=GROQ_API_KEY)
    model = "whisper-large-v3"
    file_size = os.path.getsize(audio_path)

    if file_size <= MAX_FILE_SIZE_BYTES:
        return _transcribe_chunk_groq(client, model, audio_path, offset_ms=0)
    else:
        # Split into 10-min chunks
        log.info("Audio too large for direct Groq upload, splitting into chunks...")
        return _transcribe_chunked_groq(client, model, audio_path)


def _transcribe_chunk_groq(client, model: str, audio_path: str, offset_ms: int = 0) -> list[dict]:
    """Transcribe a single file with Groq Whisper; apply ms offset."""
    for attempt in range(4):
        try:
            with open(audio_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    model=model,
                    file=f,
                    response_format="verbose_json",
                    language="en",
                    timestamp_granularities=["segment"],
                )
            break
        except Exception as e:
            err = str(e)
            if ("403" in err or "429" in err) and attempt < 3:
                log.warning(f"Groq API error ({err}), waiting 5 s then retrying ({attempt+1}/3)...")
                time.sleep(5)
            elif "403" in err:
                raise Exception(f"Groq API 403 — check VPN / network settings. {err}")
            else:
                raise

    words = []
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


def _transcribe_chunked_groq(client, model: str, audio_path: str) -> list[dict]:
    """Split audio and transcribe with offset correction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
            capture_output=True, text=True,
        )
        duration = float(result.stdout.strip())
        chunk_seconds = 10 * 60
        num_chunks = math.ceil(duration / chunk_seconds)

        all_words = []
        for i in range(num_chunks):
            start_sec = i * chunk_seconds
            chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
            subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path,
                 "-ss", str(start_sec), "-t", str(chunk_seconds),
                 "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1", chunk_path],
                capture_output=True,
            )
            log.info(f"Transcribing chunk {i+1}/{num_chunks}...")
            words = _transcribe_chunk_groq(client, model, chunk_path, offset_ms=int(start_sec * 1000))
            all_words.extend(words)

    return all_words


def _merge_into_utterances(
    whisper_words: list[dict],
    diarization_segments: list[dict],
    pause_threshold_ms: int = 800,
) -> list[dict]:
    """
    Assign each Whisper segment a speaker label from pyannote,
    then merge consecutive same-speaker segments into utterances.
    Starts a new utterance on speaker change or a pause > pause_threshold_ms.
    """
    if not whisper_words:
        return []

    labeled = []
    for w in whisper_words:
        mid_ms = (w["start_ms"] + w["end_ms"]) / 2
        speaker = _speaker_at(diarization_segments, mid_ms)
        labeled.append({**w, "speaker": speaker})

    utterances = []
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


class PyAnnoteProvider:
    """
    Speaker diarization via pyannote/speaker-diarization-3.1 (segmentation-3.0)
    + transcription via Groq Whisper large-v3.
    Produces per-speaker utterances with ms-precise timestamps.
    """

    def __init__(self):
        self._pipeline = None  # loaded lazily on first use

    def transcribe(self, audio_path: str) -> dict:
        log.info(f"PyAnnote provider: {audio_path}")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Convert to 16kHz mono WAV for pyannote
            wav_path = _ensure_wav(audio_path, tmpdir)

            # Step 2: Load & run diarization
            if self._pipeline is None:
                self._pipeline = _load_diarization_pipeline()
            diarization_segments = _run_diarization(self._pipeline, wav_path)

            # Step 3: Transcribe with Groq Whisper
            log.info("Transcribing with Groq Whisper large-v3...")
            whisper_words = _transcribe_with_groq_whisper(audio_path)

            # Step 4: Merge diarization + transcription
            log.info("Aligning transcription with speaker labels...")
            utterances = _merge_into_utterances(whisper_words, diarization_segments)

        full_text = " ".join(u["text"] for u in utterances)
        log.info(
            f"PyAnnote pipeline complete. "
            f"{len(utterances)} utterances, "
            f"{len(set(u['speaker'] for u in utterances))} speakers."
        )

        return {
            "id": "pyannote_whisper",
            "text": full_text,
            "utterances": utterances,
            "status": "completed",
        }
