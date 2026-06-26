"""Refine per-word audio boundaries so single words play back cleanly.

Whisper's word timestamps are DTW-derived and only approximate — slices tend to
clip the end of a word or bleed into the next one. We keep Whisper's word *order*
and rough position, but re-place every boundary at the quietest point (energy
valley) between adjacent word centers, and push the first/last boundary out to
the actual speech onset/offset. Cutting at valleys means we neither chop a word
mid-phoneme nor carry its neighbor along.
"""

from typing import Dict, List

import numpy as np
from scipy.io import wavfile

_FRAME = 0.01        # 10 ms energy frames
_SIL_RATIO = 0.15    # "silence" = below 15% of peak energy (for outer edges)
_EDGE_PAD = 0.04     # keep a little air around the first/last word (seconds)
_SNAP_WIN = 0.06     # how far the cut may slide to find a valley (seconds)


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


def refine_word_times(words: List[Dict[str, object]], wav_path: str) -> None:
    """Snap each word's [audio_start, audio_end] to energy valleys, in place.

    Words without timestamps (e.g. dropped sounds) are left untouched.
    """
    try:
        sr, x = _read_wav(wav_path)
    except Exception:
        return
    if x.size == 0 or sr <= 0:
        return

    hop = max(1, int(sr * _FRAME))
    n = len(x) // hop
    if n < 3:
        return
    e = np.sqrt(np.array([np.mean(x[i * hop : (i + 1) * hop] ** 2) for i in range(n)]) + 1e-9)
    peak = float(e.max())
    if peak <= 0:
        return
    thr = peak * _SIL_RATIO
    dur = len(x) / sr
    frame_t = hop / sr

    def to_frame(t: float) -> int:
        return int(min(max(round(t / frame_t), 0), n - 1))

    timed = [w for w in words if w.get("audio_start") is not None and w.get("audio_end") is not None]
    if not timed:
        return

    starts_f = [to_frame(float(w["audio_start"])) for w in timed]
    ends_f = [to_frame(float(w["audio_end"])) for w in timed]
    # Each word's center is a hard limit the cuts may not cross — that guarantees
    # every word keeps its core (no collapse) and boundaries can't overlap.
    centers = [min(s + (en - s) // 2, n - 1) for s, en in zip(starts_f, ends_f)]
    for i in range(1, len(centers)):           # keep centers strictly increasing
        centers[i] = max(centers[i], centers[i - 1] + 2)
    centers = [min(c, n - 1) for c in centers]

    win = max(1, int(_SNAP_WIN / frame_t))

    def valley(approx: int, lo: int, hi: int) -> int:
        lo = max(lo, approx - win)
        hi = min(hi, approx + win)
        if hi <= lo:
            return int(min(max(approx, 0), n - 1))
        return lo + int(np.argmin(e[lo : hi + 1]))

    # Inter-word boundary: a valley near the gap between the two words, but never
    # past either word's center.
    boundaries: List[int] = []
    for i in range(len(timed) - 1):
        gap = (ends_f[i] + starts_f[i + 1]) // 2
        boundaries.append(valley(gap, centers[i] + 1, centers[i + 1] - 1))

    # Outer edges: walk out from the first/last center to where speech dies down.
    start_f = centers[0]
    while start_f > 0 and e[start_f] > thr:
        start_f -= 1
    end_f = centers[-1]
    while end_f < n - 1 and e[end_f] > thr:
        end_f += 1

    cuts = [start_f] + boundaries + [end_f]
    pad = _EDGE_PAD
    for i, w in enumerate(timed):
        ts = cuts[i] * frame_t
        te = cuts[i + 1] * frame_t
        if i == 0:
            ts = max(0.0, ts - pad)
        if i == len(timed) - 1:
            te = min(dur, te + pad)
        w["audio_start"] = round(ts, 3)
        w["audio_end"] = round(te, 3)
