import numpy as np
import torch
from utils.config import VAD_THRESHOLD, VAD_MIN_SPEECH_MS, VAD_MIN_SILENCE_MS, VAD_SPEECH_PAD_MS
from utils.logger import get_logger

log = get_logger(__name__)

def load_vad_model():
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        trust_repo=True
    )
    return model, utils

def get_speech_segments(audio_tensor, sample_rate, model, utils):
    get_speech_ts = utils[0]
    return get_speech_ts(
        audio_tensor, model,
        sampling_rate=sample_rate,
        threshold=VAD_THRESHOLD,
        min_speech_duration_ms=VAD_MIN_SPEECH_MS,
        min_silence_duration_ms=VAD_MIN_SILENCE_MS,
        window_size_samples=512,
        speech_pad_ms=VAD_SPEECH_PAD_MS
    )

def keep_only_speech(data: np.ndarray, segments: list, sample_rate: int) -> np.ndarray:
    if not segments:
        log.warning("VAD: no speech detected, using full audio")
        return data
    output = np.zeros_like(data)
    total_speech_ms = 0
    for seg in segments:
        output[seg['start']:seg['end']] = data[seg['start']:seg['end']]
        total_speech_ms += (seg['end'] - seg['start']) / sample_rate * 1000
    log.info(f"VAD: kept {total_speech_ms/1000:.1f}s of speech out of {len(data)/sample_rate:.1f}s total")
    return output
