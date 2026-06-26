"""End-to-end analysis: audio + target sentence -> dual transcription + diff."""

import os
import re
import tempfile
from difflib import SequenceMatcher
from typing import Dict

from .align import align, attribute_ops_to_words, phoneme_error_rate, to_phones
from .attempt_log import log_attempt
from .audio import to_wav16k, wav_to_mp3_data_url
from .config import settings
from .g2p import sentence_to_phones
from .recognize import recognize_phones
from .transcribe import transcribe_with_words
from .volume import analyze_volume
from .wordaudio import refine_word_times


def _norm_word(w: str) -> str:
    return re.sub(r"[^a-z']", "", w.lower())


def attach_audio_times(words, spoken) -> None:
    """Annotate each target word with the [start, end] seconds it was spoken.

    Aligns the target words against Whisper's timestamped words; mispronounced
    words that Whisper heard differently still get an approximate slice by
    splitting the corresponding spoken span evenly.
    """
    for w in words:
        w["audio_start"] = None
        w["audio_end"] = None
    if not spoken:
        return

    target = [_norm_word(w["word"]) for w in words]
    heard = [_norm_word(s["word"]) for s in spoken]
    matcher = SequenceMatcher(a=target, b=heard, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                words[i1 + k]["audio_start"] = spoken[j1 + k]["start"]
                words[i1 + k]["audio_end"] = spoken[j1 + k]["end"]
        elif j2 > j1:  # target words map to a spoken span -> split it evenly
            span_start = spoken[j1]["start"]
            span_end = spoken[j2 - 1]["end"]
            n = i2 - i1
            step = (span_end - span_start) / n if n else 0
            for k in range(n):
                words[i1 + k]["audio_start"] = span_start + k * step
                words[i1 + k]["audio_end"] = span_start + (k + 1) * step
        # else: deletion (no spoken counterpart) -> leave None


def _word_match_ratio(target: str, transcript: str) -> float:
    """Fraction of target words recovered in the transcript (0..1)."""
    norm = lambda s: re.findall(r"[a-z']+", s.lower())
    target_words, said_words = norm(target), norm(transcript)
    if not target_words:
        return 0.0
    matcher = SequenceMatcher(a=target_words, b=said_words)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(target_words)


def analyze(audio_path: str, target_text: str) -> Dict[str, object]:
    """Run both transcription passes and align produced vs expected phones."""
    wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
    env_fd, env_wav = tempfile.mkstemp(suffix=".wav")
    os.close(wav_fd)
    os.close(env_fd)
    try:
        to_wav16k(audio_path, wav_path)
        # Cleaned audio for playback (so the user hears the denoised version too).
        clean_audio = wav_to_mp3_data_url(wav_path)

        # A denoised-but-not-normalized copy, only for measuring the true volume
        # envelope (speechnorm would otherwise hide an end-of-sentence fade).
        to_wav16k(audio_path, env_wav, audio_filter=settings.envelope_filter)
        volume = analyze_volume(env_wav, target_text)

        # Pass 1: Whisper word transcript + timestamps (right sentence? + where).
        word_transcript, spoken_words = transcribe_with_words(wav_path)
        transcript_match = _word_match_ratio(target_text, word_transcript)

        # Pass 2: Allosaurus produced phones (what sounds did they make?).
        produced_tokens = recognize_phones(wav_path)

        # Expected phones from the target sentence.
        expected = sentence_to_phones(target_text)
        expected_tokens = expected["phones"]  # type: ignore[assignment]

        # Align and score.
        ops = align(to_phones(expected_tokens), to_phones(produced_tokens))
        per = phoneme_error_rate(ops, len(expected_tokens))
        word_breakdown = attribute_ops_to_words(ops, expected["words"])  # type: ignore[arg-type]
        attach_audio_times(word_breakdown, spoken_words)
        # Snap the rough Whisper word spans to energy valleys so each word plays
        # back cleanly (no clipping, no bleed into the next word). Uses the
        # natural-dynamics envelope wav, not the loudness-normalized one.
        refine_word_times(word_breakdown, env_wav)

        result = {
            "word_transcript": word_transcript,
            "transcript_match": transcript_match,
            "expected_phones": expected_tokens,
            "produced_phones": produced_tokens,
            "expected_words": word_breakdown,
            "alignment": ops,
            "phoneme_error_rate": per,
            "errors": [op for op in ops if op["type"] != "match"],
            "clean_audio": clean_audio,
            "volume": volume,
        }
        # Log expected vs. heard phones (console + JSONL) for model diagnosis.
        log_attempt(target_text, result)
        return result
    finally:
        for p in (wav_path, env_wav):
            if os.path.exists(p):
                os.remove(p)
