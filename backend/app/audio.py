"""Audio conversion + noise reduction.

Browsers record webm/ogg/opus; both Whisper and Allosaurus want 16 kHz mono PCM
WAV, so we normalize everything through ffmpeg and (optionally) denoise on the
way so the models — and the playback — get clean speech instead of hiss."""

import base64
import os
import subprocess
import tempfile

from .config import settings


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")


def to_wav16k(src_path: str, dst_path: str, audio_filter: str | None = None) -> None:
    """Convert any ffmpeg-readable audio to 16 kHz mono 16-bit WAV.

    By default applies the configured denoise+normalize chain. Pass an explicit
    `audio_filter` (e.g. the denoise-only chain) to override it, or "" for none.
    """
    af = audio_filter if audio_filter is not None else (
        settings.audio_filter if settings.denoise else ""
    )
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src_path,
           "-ac", "1", "-ar", "16000"]
    if af:
        cmd += ["-af", af]
    cmd += ["-c:a", "pcm_s16le", "-f", "wav", dst_path]
    _run(cmd)


def wav_to_mp3_data_url(wav_path: str) -> str | None:
    """Encode a WAV to a small MP3 and return it as a data URL for playback.

    Best-effort: returns None if encoding fails so analysis still succeeds.
    """
    fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", wav_path,
              "-c:a", "libmp3lame", "-b:a", "48k", mp3_path])
        with open(mp3_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f"data:audio/mpeg;base64,{encoded}"
    except Exception:
        return None
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
