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

def preprocess_audio(input_path: str) -> str:
    log.info(f"Preprocessing audio: {input_path}")

    # Step 1 — convert to wav (mono, 16kHz)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name

    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-af", "volume=2.0",
        tmp_wav
    ], capture_output=True)

    # Step 2 — resemble-enhance (neural audio enhancement)
    # this handles 8kHz upsampling, noise removal, and clarity
    enhanced_wav = tmp_wav.replace(".wav", "_enhanced.wav")
    enhancement_success = enhance_audio(tmp_wav, enhanced_wav)

    if enhancement_success:
        # use enhanced audio for further processing
        working_wav = enhanced_wav
        sample_rate, data = wavfile.read(enhanced_wav)
    else:
        # fallback to original converted wav
        working_wav = tmp_wav
        sample_rate, data = wavfile.read(tmp_wav)

    data = data.astype(np.float32)

    # Step 3 — VAD (keep only speech segments)
    log.info("Loading VAD model...")
    vad_model, vad_utils = load_vad_model()
    audio_tensor = torch.FloatTensor(data / 32768.0)
    segments = get_speech_segments(audio_tensor, sample_rate, vad_model, vad_utils)
    data = keep_only_speech(data, segments, sample_rate)

    # Step 4 — traditional noise reduction on top
    data = remove_impulse_noise(data, sample_rate)
    noise_sample = data[:int(sample_rate * 0.5)]
    data = nr.reduce_noise(
        y=data, sr=sample_rate, y_noise=noise_sample,
        prop_decrease=NOISE_PROP_DECREASE, stationary=False,
        n_fft=1024, hop_length=256,
    )

    # Step 5 — filters
    data = bandpass_filter(data)
    data = suppress_mouth_noise(data, sample_rate)
    data = smooth_and_normalize(data)

    # Step 6 — save clean audio
    clean_wav = tmp_wav.replace(".wav", "_clean.wav")
    wavfile.write(clean_wav, sample_rate, data)

    output_path = input_path.rsplit(".", 1)[0] + "_clean.mp3"
    subprocess.run(["ffmpeg", "-y", "-i", clean_wav, output_path], capture_output=True)

    # cleanup temp files
    os.unlink(tmp_wav)
    if enhancement_success and os.path.exists(enhanced_wav):
        os.unlink(enhanced_wav)
    os.unlink(clean_wav)

    log.info(f"Clean audio saved to: {output_path}")
    return output_path