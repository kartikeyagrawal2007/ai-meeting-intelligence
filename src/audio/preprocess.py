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

def preprocess_audio(input_path: str) -> str:
    log.info(f"Preprocessing audio: {input_path}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name

    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-af", "volume=2.0",
        tmp_wav
    ], capture_output=True)

    sample_rate, data = wavfile.read(tmp_wav)
    data = data.astype(np.float32)

    log.info("Loading VAD model...")
    vad_model, vad_utils = load_vad_model()
    audio_tensor = torch.FloatTensor(data / 32768.0)
    segments = get_speech_segments(audio_tensor, sample_rate, vad_model, vad_utils)

    data = keep_only_speech(data, segments, sample_rate)
    data = remove_impulse_noise(data, sample_rate)

    noise_sample = data[:int(sample_rate * 0.5)]
    data = nr.reduce_noise(
        y=data, sr=sample_rate, y_noise=noise_sample,
        prop_decrease=NOISE_PROP_DECREASE, stationary=False,
        n_fft=1024, hop_length=256,
    )

    data = bandpass_filter(data)
    data = suppress_mouth_noise(data, sample_rate)
    data = smooth_and_normalize(data)

    clean_wav = tmp_wav.replace(".wav", "_clean.wav")
    wavfile.write(clean_wav, sample_rate, data)

    output_path = input_path.rsplit(".", 1)[0] + "_clean.mp3"
    subprocess.run(["ffmpeg", "-y", "-i", clean_wav, output_path], capture_output=True)

    os.unlink(tmp_wav)
    os.unlink(clean_wav)

    log.info(f"Clean audio saved to: {output_path}")
    return output_path
