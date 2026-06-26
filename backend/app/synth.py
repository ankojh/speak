"""Synthesize a phoneme sequence into audible speech with espeak-ng.

Lets the user *hear* a raw IPA phone string — both the target sounds and the
sounds the recognizer thinks they produced — which the browser's text-to-speech
can't do from IPA directly."""

import os
import subprocess
import tempfile
from typing import List, Optional

from .phonemes import ipa_to_espeak


def synth_phones(tokens: List[str], speed: int = 120) -> Optional[bytes]:
    """Return MP3 bytes of espeak-ng speaking the given IPA tokens, or None."""
    kirshenbaum = ipa_to_espeak(tokens)
    if not kirshenbaum.strip():
        return None

    wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
    mp3_fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
    os.close(wav_fd)
    os.close(mp3_fd)
    try:
        espeak = subprocess.run(
            ["espeak-ng", "-v", "en", "-s", str(speed), f"[[{kirshenbaum}]]", "-w", wav_path],
            capture_output=True, text=True,
        )
        if espeak.returncode != 0:
            return None
        ff = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", wav_path, "-c:a", "libmp3lame", "-b:a", "48k", mp3_path],
            capture_output=True, text=True,
        )
        if ff.returncode != 0:
            return None
        with open(mp3_path, "rb") as f:
            return f.read()
    finally:
        for p in (wav_path, mp3_path):
            if os.path.exists(p):
                os.remove(p)
