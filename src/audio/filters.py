import numpy as np
from scipy.signal import butter, filtfilt, medfilt
from scipy.ndimage import binary_dilation
from utils.config import BANDPASS_LOW, BANDPASS_HIGH, SAMPLE_RATE

def bandpass_filter(data: np.ndarray, lowcut=BANDPASS_LOW, highcut=BANDPASS_HIGH, fs=SAMPLE_RATE, order=5) -> np.ndarray:
    nyq = fs / 2
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return filtfilt(b, a, data)

def remove_impulse_noise(data: np.ndarray, sample_rate: int, threshold_multiplier=8.0) -> np.ndarray:
    window = int(0.02 * sample_rate)
    smoothed = np.convolve(np.abs(data), np.ones(window) / window, mode='same')
    avg_energy = np.mean(smoothed)
    spike_mask = smoothed > (avg_energy * threshold_multiplier)
    spike_mask = binary_dilation(spike_mask, iterations=int(0.01 * sample_rate))
    cleaned = data.copy()
    cleaned[spike_mask] = 0.0
    return cleaned

def suppress_mouth_noise(data: np.ndarray, sr: int, burst_ms=80, energy_ratio=6.0) -> np.ndarray:
    burst_samples = int((burst_ms / 1000) * sr)
    hop = burst_samples // 2
    output = data.copy()
    for i in range(0, len(data) - burst_samples, hop):
        frame = data[i:i + burst_samples]
        frame_energy = np.mean(frame ** 2)
        start = max(0, i - burst_samples * 3)
        end = min(len(data), i + burst_samples * 4)
        context = np.concatenate([data[start:i], data[i + burst_samples:end]])
        context_energy = np.mean(context ** 2) if len(context) > 0 else 0
        if context_energy > 0 and frame_energy > energy_ratio * context_energy:
            output[i:i + burst_samples] *= 0.1
    return output

def smooth_and_normalize(data: np.ndarray, target_peak=28000) -> np.ndarray:
    data = medfilt(data, kernel_size=3)
    max_val = np.max(np.abs(data))
    if max_val > 0:
        data = data / max_val * target_peak
    return np.clip(data, -32768, 32767).astype(np.int16)
