"""Phoneme recognition: produced audio -> IPA phone sequence.

Default backend is a Wav2Vec2 phoneme model (facebook/wav2vec2-lv-60-espeak-cv-ft),
which is far more robust on real-world recordings than the lightweight Allosaurus
universal recognizer. Both emit IPA, which is what we diff against the target."""

from typing import List

import numpy as np
from scipy.io import wavfile

from .config import settings
from .phonemes import atomize

_w2v = None      # (processor, model)
_allosaurus = None


def _read_wav(wav_path: str) -> np.ndarray:
    """Read a 16 kHz mono WAV into a float32 array in [-1, 1]."""
    _sr, data = wavfile.read(wav_path)
    if data.dtype == np.int16:
        audio = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        audio = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        audio = (data.astype(np.float32) - 128) / 128.0
    else:
        audio = data.astype(np.float32)
    if audio.ndim > 1:  # collapse to mono just in case
        audio = audio.mean(axis=1)
    return audio


def _recognize_wav2vec2(wav_path: str) -> List[str]:
    global _w2v
    if _w2v is None:
        import torch  # noqa: F401
        from transformers import AutoModelForCTC, AutoProcessor

        processor = AutoProcessor.from_pretrained(settings.wav2vec2_model)
        model = AutoModelForCTC.from_pretrained(settings.wav2vec2_model)
        model.eval()
        _w2v = (processor, model)

    import torch

    processor, model = _w2v
    audio = _read_wav(wav_path)
    inputs = processor(audio, sampling_rate=16000, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values).logits
    predicted_ids = torch.argmax(logits, dim=-1)
    text = processor.batch_decode(predicted_ids)[0]
    return text.split()


def _recognize_allosaurus(wav_path: str) -> List[str]:
    global _allosaurus
    if _allosaurus is None:
        from allosaurus.app import read_recognizer

        _allosaurus = read_recognizer()
    raw = _allosaurus.recognize(wav_path, settings.allosaurus_lang)
    return raw.split()


def recognize_phones(wav_path: str) -> List[str]:
    """Return the produced phones as a flat list of atomic IPA tokens."""
    if settings.recognizer == "allosaurus":
        tokens = _recognize_allosaurus(wav_path)
    else:
        tokens = _recognize_wav2vec2(wav_path)
    return atomize(tokens)
