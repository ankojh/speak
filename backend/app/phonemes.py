"""Phoneme utilities: ARPABET->IPA mapping and IPA normalization.

The expected pronunciation comes from CMUdict / g2p_en, which emits ARPABET.
The produced pronunciation comes from Allosaurus, which emits IPA. To diff the
two we map ARPABET to IPA, then normalize both sides into a common atomic
inventory so that trivial notational differences don't show up as accent errors.
"""

import unicodedata
from typing import List

# ARPABET (no stress digits) -> IPA. Diphthongs/affricates are written as
# multi-character tokens here and split into atoms later by `atomize`.
ARPABET_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ",
    "AY": "aɪ", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "F": "f", "G": "ɡ",
    "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k",
    "L": "l", "M": "m", "N": "n", "NG": "ŋ", "OW": "oʊ",
    "OY": "ɔɪ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}


# Diacritics and suprasegmentals to drop before comparing.
_STRIP_CHARS = "ːˑ ˈ ˌ ̃ ̩ ̯ ʰ ̥ ̬ ̪ ̆ ʼ".replace(" ", "")

# Near-equivalent symbols collapsed to one representative. Reduces false
# substitutions caused by the two models using different notation for the
# same sound (e.g. CMU's rhotic vowels vs Allosaurus' schwa+r).
_EQUIVALENCE = {
    "ɡ": "g",        # IPA script g vs ASCII g
    "ɹ": "r", "ɻ": "r", "ɾ": "r",   # rhotics
    "ɝ": "ə", "ɚ": "ə", "ʌ": "ə",   # reduced/rhotic central vowels -> schwa
    "ɫ": "l",        # dark l
    "ɑ": "a", "ɒ": "a",             # back open vowels
    "ɪ": "i",        # (lax/tense merge kept loose for a basic diff)
    "ʊ": "u",
    "ŋ": "n",
}


def strip_stress(arpabet_token: str) -> str:
    """Remove the trailing stress digit (0/1/2) from an ARPABET token."""
    return arpabet_token[:-1] if arpabet_token and arpabet_token[-1].isdigit() else arpabet_token


def arpabet_to_ipa(token: str) -> str | None:
    """Map a single (stressless) ARPABET token to an IPA token, or None."""
    return ARPABET_TO_IPA.get(token.upper())


def atomize(tokens: List[str]) -> List[str]:
    """Break tokens into atomic IPA segments (one base letter each).

    Diphthongs (aɪ), affricates (tʃ), and r-colored vowels (ɔːɹ) are split into
    their base letters; length marks, stress, aspiration, and tie bars are
    dropped. This keeps the expected (ARPABET-derived) and produced (wav2vec2 /
    Allosaurus) sequences in the same atomic alphabet so they align cleanly.
    """
    out: List[str] = []
    for tok in tokens:
        for ch in tok:
            # Keep base letters (IPA vowels/consonants); drop modifier letters
            # (ː ʰ ʲ), combining marks (tie bars, diacritics), and punctuation.
            if unicodedata.category(ch) in ("Ll", "Lo", "Lu"):
                out.append(ch)
    return out


# IPA -> espeak-ng's Kirshenbaum phoneme notation, for synthesizing a phone
# sequence so the user can hear "what we think you said" vs. the target sounds.
IPA_TO_KIRSHENBAUM = {
    # consonants
    "p": "p", "b": "b", "t": "t", "d": "d", "k": "k", "g": "g", "ɡ": "g",
    "m": "m", "n": "n", "ŋ": "N", "ɲ": "n", "ʔ": "?",
    "f": "f", "v": "v", "θ": "T", "ð": "D", "s": "s", "z": "z",
    "ʃ": "S", "ʒ": "Z", "h": "h", "tʃ": "tS", "dʒ": "dZ",
    "ɹ": "r", "r": "r", "ɾ": "r", "ɻ": "r", "ʁ": "r", "l": "l", "ɫ": "l",
    "j": "j", "w": "w", "ʍ": "w", "x": "x", "χ": "x", "ɣ": "x",
    # vowels
    "i": "i:", "ɪ": "I", "e": "e", "ɛ": "E", "æ": "&", "a": "a",
    "ʌ": "V", "ə": "@", "ɐ": "@", "ɵ": "@", "ɑ": "A:", "ɒ": "A:",
    "ɔ": "O:", "o": "o", "ʊ": "U", "u": "u:", "ʉ": "u:", "ɨ": "i:",
    "ɝ": "3:", "ɚ": "3:", "ɜ": "3:", "ɞ": "3:", "y": "i:", "ø": "e",
}

# Letters we treat as vowels for the fallback below (so an unknown vowel still
# makes *some* sound rather than silently vanishing and yielding an empty clip).
_VOWEL_LETTERS = set("aeiouyæɑɒɔəɛɪʊʌɝɚɜɐɵʉɨøœɶɤɯ")


def ipa_to_espeak(tokens: List[str]) -> str:
    """Build a space-separated Kirshenbaum string for espeak-ng's `[[...]]`.

    Unknown symbols fall back to a schwa if they look like a vowel, so a word's
    produced phones always synthesize to *something* audible instead of an empty
    string (which the /api/pronounce endpoint can't speak).
    """
    out: List[str] = []
    for tok in tokens:
        base = "".join(ch for ch in tok if ch not in _STRIP_CHARS) or tok
        kirsh = IPA_TO_KIRSHENBAUM.get(base) or IPA_TO_KIRSHENBAUM.get(base[:1])
        if kirsh is None and base[:1] in _VOWEL_LETTERS:
            kirsh = "@"
        if kirsh:
            out.append(kirsh)
    return " ".join(out)


def normalize(token: str) -> str:
    """Strip diacritics and apply equivalence folding for comparison.

    The returned key is what alignment compares on; the original IPA token is
    still kept for display so the user sees the real sounds.
    """
    cleaned = "".join(ch for ch in token if ch not in _STRIP_CHARS)
    if not cleaned:
        return token
    return _EQUIVALENCE.get(cleaned, cleaned)
