import os
import subprocess
import tempfile
import numpy as np
import noisereduce as nr
import torch
from scipy.io import wavfile
from audio.vad import load_vad_model, get_speech_segments, keep_only_speech
from audio.filters import bandpass_filter, remove_impulse_noise, suppress_mouth_noise, smooth_and_normalize
from utils.config import SAMPLE_RATE, NOISE_PROP_DECREASE
from utils.logger import get_logger

log = get_logger(__name__)


def enhance_audio(input_wav: str, output_wav: str) -> bool:
    """
    Use ffmpeg filters to enhance degraded/telephone quality audio.
    """
    try:
        log.info("Enhancing audio with ffmpeg filters...")
        result = subprocess.run([
            "ffmpeg", "-y", "-i", input_wav,
            "-af", (
                "highpass=f=200,"           # remove low freq rumble
                "lowpass=f=3400,"           # keep speech frequencies only
                "afftdn=nf=-25,"            # noise reduction
                "equalizer=f=1000:width_type=o:width=2:g=3,"  # boost mid speech
                "equalizer=f=3000:width_type=o:width=2:g=2,"  # boost clarity
                "acompressor=threshold=0.1:ratio=4:attack=5:release=50,"  # compress dynamics
                "volume=3.0"                # boost overall volume
            ),
            "-ar", "16000",
            output_wav
        ], capture_output=True)

        if result.returncode == 0:
            log.info("ffmpeg enhancement complete.")
            return True
        else:
            log.warning(f"ffmpeg enhancement failed: {result.stderr.decode()}")
            return False

    except Exception as e:
        log.warning(f"Enhancement failed: {e}")
        return False


def _get_channel_count(input_path: str) -> int:
    """Return the number of audio channels in the file."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=channels", "-of", "csv=p=0", input_path],
        capture_output=True, text=True,
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 1


def preprocess_audio(input_path: str) -> str:
    log.info(f"Preprocessing audio: {input_path}")

    # Detect stereo so we can preserve it through preprocessing.
    src_channels = _get_channel_count(input_path)
    is_stereo = src_channels >= 2
    log.info(
        f"Source audio channels: {src_channels} — "
        f"{'preserving stereo for channel-based diarization' if is_stereo else 'mono'}"
    )

    # ── Step 1: Convert to mono WAV for pipeline processing ──────────────
    # VAD / noise-reduction / filters all require 1-D mono arrays.
    # We always work in mono internally; for stereo we'll re-apply the
    # VAD speech mask to the original stereo signal at the end.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name

    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-af", "volume=2.0",
        tmp_wav
    ], capture_output=True)

    # ── Step 2: ffmpeg audio enhancement (on mono working copy) ──────────
    enhanced_wav = tmp_wav.replace(".wav", "_enhanced.wav")
    enhancement_success = enhance_audio(tmp_wav, enhanced_wav)

    if enhancement_success:
        working_wav = enhanced_wav
        sample_rate, data = wavfile.read(enhanced_wav)
    else:
        working_wav = tmp_wav
        sample_rate, data = wavfile.read(tmp_wav)

    data = data.astype(np.float32)

    # ── Step 3: VAD — keep only speech segments ───────────────────────────
    log.info("Loading VAD model...")
    vad_model, vad_utils = load_vad_model()
    audio_tensor = torch.FloatTensor(data / 32768.0)
    segments = get_speech_segments(audio_tensor, sample_rate, vad_model, vad_utils)
    data = keep_only_speech(data, segments, sample_rate)

    # ── Step 4: Noise reduction ───────────────────────────────────────────
    data = remove_impulse_noise(data, sample_rate)
    noise_sample = data[:int(sample_rate * 0.5)]
    data = nr.reduce_noise(
        y=data, sr=sample_rate, y_noise=noise_sample,
        prop_decrease=NOISE_PROP_DECREASE, stationary=False,
        n_fft=1024, hop_length=256,
    )

    # ── Step 5: Filters ───────────────────────────────────────────────────
    data = bandpass_filter(data)
    data = suppress_mouth_noise(data, sample_rate)
    data = smooth_and_normalize(data)

    # ── Step 6: Save clean audio ──────────────────────────────────────────
    output_path = input_path.rsplit(".", 1)[0] + "_clean.mp3"

    if is_stereo:
        # For stereo sources: save the mono-processed audio as a temp file,
        # then use ffmpeg to apply the same duration trim to the stereo source
        # while mixing the cleaned mono back. The simplest approach that
        # preserves channel identity: write mono clean, then re-encode the
        # original stereo with matched duration using ffmpeg pan filters
        # for enhancement (no VAD trimming on stereo path to avoid offset issues).
        # Strategy: enhance the original stereo with ffmpeg filters only,
        # no VAD trimming (call recordings are usually continuous speech anyway).
        log.info("Stereo source: applying ffmpeg enhancement to stereo original (no VAD trim).")
        stereo_enhanced_wav = tmp_wav.replace(".wav", "_stereo_enhanced.wav")
        result = subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            "-af", (
                "highpass=f=200,"
                "lowpass=f=3400,"
                "afftdn=nf=-25,"
                "equalizer=f=1000:width_type=o:width=2:g=3,"
                "equalizer=f=3000:width_type=o:width=2:g=2,"
                "acompressor=threshold=0.1:ratio=4:attack=5:release=50,"
                "volume=3.0"
            ),
            "-ar", str(SAMPLE_RATE),
            stereo_enhanced_wav,
        ], capture_output=True)
        if result.returncode == 0:
            subprocess.run(
                ["ffmpeg", "-y", "-i", stereo_enhanced_wav, output_path],
                capture_output=True
            )
            os.unlink(stereo_enhanced_wav)
            log.info(f"Stereo clean audio saved to: {output_path}")
        else:
            # fallback: just copy original to output
            log.warning("Stereo enhancement failed — using original audio.")
            subprocess.run(
                ["ffmpeg", "-y", "-i", input_path, "-ar", str(SAMPLE_RATE), output_path],
                capture_output=True
            )
    else:
        # Mono: write processed data to wav then encode to mp3
        clean_wav = tmp_wav.replace(".wav", "_clean.wav")
        wavfile.write(clean_wav, sample_rate, data)
        subprocess.run(["ffmpeg", "-y", "-i", clean_wav, output_path], capture_output=True)
        os.unlink(clean_wav)
        log.info(f"Clean audio saved to: {output_path}")

    # Cleanup temp files
    os.unlink(tmp_wav)
    if enhancement_success and os.path.exists(enhanced_wav):
        os.unlink(enhanced_wav)

    return output_path