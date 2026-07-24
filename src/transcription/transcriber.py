"""
transcriber.py
──────────────────────────────────────────────────────────────────────
Main transcription entry point.

Supported providers: assemblyai, groq, pyannote

Channel-aware diarization:
  1. Call channel_separator to detect stereo vs mono.
  2. If STEREO:
       - Transcribe Speaker A channel (left) with chosen provider.
       - Transcribe Speaker B channel (right) with chosen provider.
       - Merge utterances, sorted by timestamp, with speaker labels
         forced to "A" and "B" respectively.
  3. If MONO:
       - Use normal single-file transcription flow.

Root cause note (fixed 2026-06-02):
  Previously, preprocess_audio() forced -ac 1 (mono) on every input,
  destroying stereo channel information before channel_separator ran.
  preprocess.py now preserves stereo for stereo inputs, so
  channel_separator correctly sees 2 channels on the clean file.
"""

import shutil
import concurrent.futures
from utils.logger import get_logger
from audio.channel_separator import separate_channels

log = get_logger(__name__)


def _force_speaker(transcript: dict, label: str) -> dict:
    """Override every utterance's speaker field with `label`."""
    result = transcript.copy()
    result["utterances"] = [
        {**utt, "speaker": label}
        for utt in transcript.get("utterances", [])
    ]
    return result


def _merge_channel_transcripts(transcript_a: dict, transcript_b: dict) -> dict:
    """
    Merge two per-channel transcripts into one.

    Utterances from both channels are interleaved in chronological
    order by their `start` timestamp.  Speaker labels are preserved
    as-set by _force_speaker (A / B).
    """
    utts_a = transcript_a.get("utterances", [])
    utts_b = transcript_b.get("utterances", [])

    merged = sorted(
        utts_a + utts_b,
        key=lambda u: u.get("start", 0),
    )

    full_text = " ".join(u["text"] for u in merged if u.get("text"))

    return {
        "id": "channel_diarized",
        "text": full_text,
        "utterances": merged,
        "status": "completed",
        "diarization_method": "channel_separation",
    }


def _transcribe_single(audio_path: str, provider: str, speakers_expected: int | None = None) -> dict:
    """Transcribe a single (mono) audio file with the chosen provider."""
    if provider == "assemblyai":
        from transcription.providers.assemblyai_provider import AssemblyAIProvider
        return AssemblyAIProvider().transcribe(audio_path, speakers_expected=speakers_expected)

    elif provider == "groq":
        from transcription.providers.groq_whisper_provider import GroqWhisperProvider
        return GroqWhisperProvider().transcribe(audio_path)

    elif provider == "pyannote":
        from transcription.providers.pyannote_provider import PyAnnoteProvider
        return PyAnnoteProvider().transcribe(audio_path)

    else:
        raise ValueError(
            f"Unknown provider: '{provider}'. "
            "Supported: 'assemblyai', 'groq', 'pyannote'."
        )


def transcribe_audio(
    audio_path: str,
    provider: str = "assemblyai",
    speakers_expected: int | None = None,
) -> dict:
    """
    Transcribe audio using specified provider with channel-aware diarization.

    Args:
        audio_path:        Path to the audio file (may be stereo or mono).
        provider:          One of 'assemblyai', 'groq', 'pyannote'.
        speakers_expected: Hint the number of distinct speakers (improves diarization).

    Returns:
        Standard transcript dict:
          { "id", "text", "utterances": [...], "status" }
    """
    # ── Step 1: Channel detection ─────────────────────────────────────────
    log.info(f"Checking audio channels for: {audio_path}")
    channel_info = separate_channels(audio_path)

    if not channel_info["is_stereo"]:
        # ── MONO path: normal single transcription ────────────────────────
        log.info("Mono audio — using standard transcription pipeline.")
        return _transcribe_single(audio_path, provider, speakers_expected=speakers_expected)

    # ── STEREO path: per-channel transcription ────────────────────────────
    log.info("Stereo audio — transcribing each channel separately.")
    speaker_a_path = channel_info["speaker_a_path"]
    speaker_b_path = channel_info["speaker_b_path"]
    tmpdir = channel_info.get("_tmpdir")

    try:
        # Step 2: transcribe channels concurrently
        log.info("  Transcribing Speaker A & B concurrently...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(_transcribe_single, speaker_a_path, provider)
            future_b = executor.submit(_transcribe_single, speaker_b_path, provider)
            
            raw_a = future_a.result()
            raw_b = future_b.result()

        transcript_a = _force_speaker(raw_a, "A")
        transcript_b = _force_speaker(raw_b, "B")

        # Step 3: merge and sort by timestamp
        log.info("  Merging channel transcripts by timestamp...")
        merged = _merge_channel_transcripts(transcript_a, transcript_b)

        log.info(
            f"Channel diarization complete. "
            f"A: {len(transcript_a['utterances'])} utts, "
            f"B: {len(transcript_b['utterances'])} utts → "
            f"{len(merged['utterances'])} merged."
        )
        return merged

    finally:
        # Clean up temp channel files
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
            log.info(f"  Cleaned up temp channel files: {tmpdir}")