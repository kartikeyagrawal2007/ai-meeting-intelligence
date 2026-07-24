"""
channel_separator.py
─────────────────────────────────────────────────────
Channel-based diarization for stereo call recordings.

If the audio is stereo, the two channels are split into
separate mono files:
  Left  channel → Speaker A
  Right channel → Speaker B

This gives perfect speaker separation for phone/call recordings
where each party is recorded on its own channel.

Returns a dict:
  {
    "is_stereo":      bool,
    "speaker_a_path": str | None,   # left channel
    "speaker_b_path": str | None,   # right channel
    "original_path":  str,
  }
"""

import os
import subprocess
import tempfile

from utils.logger import get_logger

log = get_logger(__name__)


def check_stereo(audio_path: str) -> bool:
    """Return True if the audio file has 2+ channels (stereo)."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=channels",
            "-of", "csv=p=0",
            audio_path,
        ],
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    if not output:
        log.warning("ffprobe returned no channel info — treating as mono.")
        return False
    try:
        channels = int(output)
        log.info(f"Audio channels detected: {channels}")
        return channels >= 2
    except ValueError:
        log.warning(f"Could not parse channel count '{output}' — treating as mono.")
        return False


def separate_channels(audio_path: str) -> dict:
    """
    Check if audio is stereo and split into per-channel mono files.

    If stereo:
      - Left  channel (c0) → Speaker A   (speaker_a_path)
      - Right channel (c1) → Speaker B   (speaker_b_path)
    If mono:
      - Returns original_path, is_stereo=False, no channel paths.

    The returned temp directory (if created) is stored in
    result["_tmpdir"] and must be cleaned up by the caller.
    """
    is_stereo = check_stereo(audio_path)

    if not is_stereo:
        log.info("Mono audio detected — skipping channel separation.")
        return {
            "is_stereo": False,
            "speaker_a_path": None,
            "speaker_b_path": None,
            "original_path": audio_path,
            "_tmpdir": None,
        }

    log.info("Stereo audio detected — splitting into left/right channel mono files.")
    tmpdir = tempfile.mkdtemp(prefix="channel_sep_")

    base = os.path.splitext(os.path.basename(audio_path))[0]
    speaker_a_path = os.path.join(tmpdir, f"{base}_speaker_a.wav")
    speaker_b_path = os.path.join(tmpdir, f"{base}_speaker_b.wav")

    # Extract left channel  → Speaker A (one output per run)
    result_a = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-filter_complex", "[0:a]pan=mono|c0=c0[left]",
            "-map", "[left]",
            "-ar", "16000",
            speaker_a_path,
        ],
        capture_output=True,
        text=True,
    )

    # Extract right channel → Speaker B (one output per run)
    result_b = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-filter_complex", "[0:a]pan=mono|c0=c1[right]",
            "-map", "[right]",
            "-ar", "16000",
            speaker_b_path,
        ],
        capture_output=True,
        text=True,
    )

    if result_a.returncode != 0:
        log.error(f"ffmpeg left-channel extraction failed:\n{result_a.stderr}")
        raise RuntimeError("Failed to extract Speaker A (left) channel.")

    if result_b.returncode != 0:
        log.error(f"ffmpeg right-channel extraction failed:\n{result_b.stderr}")
        raise RuntimeError("Failed to extract Speaker B (right) channel.")

    log.info(f"  Speaker A (left)  → {speaker_a_path}")
    log.info(f"  Speaker B (right) → {speaker_b_path}")

    return {
        "is_stereo": True,
        "speaker_a_path": speaker_a_path,
        "speaker_b_path": speaker_b_path,
        "original_path": audio_path,
        "_tmpdir": tmpdir,
    }
