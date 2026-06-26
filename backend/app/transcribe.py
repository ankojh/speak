"""Whisper word-level transcription via faster-whisper (CTranslate2, CPU-friendly).

This pass confirms the user actually read the target sentence (vs. measuring how
they pronounced it, which is the phoneme pass's job)."""

from .config import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _model


def transcribe(wav_path: str) -> str:
    """Return the recognized text for a 16 kHz mono WAV file."""
    text, _words = transcribe_with_words(wav_path)
    return text


def transcribe_with_words(wav_path: str):
    """Return (text, words) where words is a list of {word, start, end} seconds.

    Word timestamps let us play back the exact slice of the recording where a
    given word was spoken.
    """
    model = _get_model()
    segments, _info = model.transcribe(
        wav_path, language="en", beam_size=1, word_timestamps=True
    )

    text_parts = []
    words = []
    for seg in segments:
        text_parts.append(seg.text.strip())
        for w in seg.words or []:
            words.append({"word": w.word.strip(), "start": float(w.start), "end": float(w.end)})

    return " ".join(text_parts).strip(), words
