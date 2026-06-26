"""Loudness-envelope analysis for the "your volume vs. a steady reference" chart.

We compute a short-time RMS envelope of the recording, resample it to a fixed
number of points over the whole utterance, smooth it, and peak-normalize it to
[0, 1] (so the chart is about *relative* shape, not absolute mic gain). The same
is done for an espeak reference of the sentence to give a steady baseline to
overlay against — which makes an end-of-sentence fade obvious.
"""

import os
import subprocess
import tempfile
from functools import lru_cache
from typing import Dict, List

import numpy as np
from scipy.io import wavfile

POINTS = 40            # samples in the plotted envelope
_SMOOTH = 5            # moving-average window (odd) to suppress word-gap jitter


def _read_wav(wav_path: str) -> "tuple[int, np.ndarray]":
    sr, data = wavfile.read(wav_path)
    if data.dtype == np.int16:
        x = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        x = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        x = (data.astype(np.float32) - 128) / 128.0
    else:
        x = data.astype(np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    return sr, x


def _smooth(env: np.ndarray, window: int = _SMOOTH) -> np.ndarray:
    if window <= 1 or env.size < window:
        return env
    kernel = np.ones(window) / window
    return np.convolve(env, kernel, mode="same")


def _trim_silence(x: np.ndarray, sr: int, thresh_ratio: float = 0.06,
                  pad: float = 0.05) -> np.ndarray:
    """Drop leading/trailing silence so the envelope starts at speech onset.

    Without this, a delayed start shifts the whole line right and it no longer
    lines up with the reference. The threshold is low (6% of peak) so genuinely
    quiet — but still present — speech at the tail is kept (we only cut silence),
    which means a real end-of-sentence fade still shows up.
    """
    if x.size == 0:
        return x
    hop = max(1, int(sr * 0.02))
    n = len(x) // hop
    if n < 2:
        return x
    e = np.sqrt(np.array([np.mean(x[i * hop : (i + 1) * hop] ** 2) for i in range(n)]) + 1e-9)
    peak = float(e.max())
    if peak <= 0:
        return x
    above = np.where(e > peak * thresh_ratio)[0]
    if above.size == 0:
        return x
    p = int(pad * sr)
    lo = max(0, above[0] * hop - p)
    hi = min(len(x), (above[-1] + 1) * hop + p)
    return x[lo:hi]


def envelope(wav_path: str, points: int = POINTS) -> List[float]:
    """Peak-normalized, smoothed loudness envelope as `points` floats in [0, 1].

    Leading/trailing silence is trimmed first so the line spans only the spoken
    region — that's what lets the user and reference envelopes overlap even when
    the speaker pauses before starting.
    """
    sr, x = _read_wav(wav_path)
    if x.size == 0 or sr <= 0:
        return []
    x = _trim_silence(x, sr)
    if x.size == 0:
        return []

    hop = max(1, int(sr * 0.02))           # 20 ms hop
    win = max(hop, int(sr * 0.04))         # 40 ms window
    n_frames = max(1, (len(x) - win) // hop + 1)
    rms = np.empty(n_frames, dtype=np.float32)
    for i in range(n_frames):
        frame = x[i * hop : i * hop + win]
        rms[i] = np.sqrt(np.mean(frame * frame) + 1e-12)

    # Resample to a fixed number of points across the whole utterance, smooth,
    # then peak-normalize so the line is about shape, not absolute level.
    src = np.linspace(0.0, 1.0, num=len(rms))
    dst = np.linspace(0.0, 1.0, num=points)
    env = np.interp(dst, src, rms)
    env = _smooth(env)
    peak = float(env.max())
    if peak > 0:
        env = env / peak
    return [round(float(v), 3) for v in env]


@lru_cache(maxsize=256)
def reference_envelope(text: str) -> "tuple[float, ...]":
    """Envelope of an espeak rendering of `text` — a steady-delivery baseline.

    Cached per sentence (the reference doesn't change between attempts). Returns
    an empty tuple if espeak/synthesis isn't available.
    """
    wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(wav_fd)
    try:
        proc = subprocess.run(
            ["espeak-ng", "-v", "en", "-s", "150", text, "-w", wav_path],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return tuple()
        return tuple(envelope(wav_path))
    except Exception:
        return tuple()
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


def fade_metrics(env: List[float]) -> Dict[str, object]:
    """Flag whether loudness drops off toward the end of the utterance.

    Compares how loud the speaker *gets* early (peak of the first 60%) against
    how loud they get late (a near-peak of the last quarter). Using peaks rather
    than means makes this robust to the dips between words and to a single loud
    sentence-final stress. `drop` is the relative loss (0 = none, 1 = silent end).
    """
    if len(env) < 8:
        return {"fades": False, "drop": 0.0, "start_level": 0.0, "end_level": 0.0}
    arr = np.asarray(env, dtype=np.float32)
    n = len(arr)
    head = float(np.max(arr[: max(1, int(n * 0.6))]))
    tail = float(np.percentile(arr[int(n * 0.75):], 90))
    drop = 0.0 if head <= 0 else max(0.0, 1.0 - tail / head)
    return {
        "fades": drop >= 0.40,           # late peak is <60% of the early peak
        "drop": round(drop, 3),
        "start_level": round(head, 3),
        "end_level": round(tail, 3),
    }


def analyze_volume(user_wav: str, target_text: str) -> Dict[str, object]:
    """Bundle the user envelope, reference envelope, and the fade verdict."""
    user_env = envelope(user_wav)
    ref_env = list(reference_envelope(target_text))
    return {"user": user_env, "reference": ref_env, **fade_metrics(user_env)}
