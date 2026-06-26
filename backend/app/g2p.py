"""Grapheme-to-phoneme: target sentence -> expected IPA phoneme sequence.

Uses g2p_en, which looks words up in CMUdict and falls back to a neural model
for out-of-vocabulary words. Output ARPABET is mapped to IPA.
"""

from typing import Dict, List

from .phonemes import arpabet_to_ipa, atomize, strip_stress

_g2p = None


def _ensure_nltk_data():
    """g2p_en needs CMUdict + the POS tagger; newer nltk uses lang-suffixed names."""
    import nltk

    for pkg in ("averaged_perceptron_tagger_eng", "averaged_perceptron_tagger", "cmudict"):
        try:
            nltk.download(pkg, quiet=True)
        except Exception:
            pass


def _get_g2p():
    global _g2p
    if _g2p is None:
        _ensure_nltk_data()
        from g2p_en import G2p

        _g2p = G2p()
    return _g2p


def sentence_to_phones(text: str) -> Dict[str, object]:
    """Return expected phones for a sentence.

    {
      "phones": [<atomic IPA tokens, flat>],
      "words":  [{"word": str, "phones": [IPA tokens]}],
    }
    """
    g2p = _get_g2p()
    tokens = g2p(text)  # ARPABET tokens, spaces, and punctuation interleaved

    words: List[Dict[str, object]] = []
    current_word_ipa: List[str] = []
    flat: List[str] = []

    def flush():
        if current_word_ipa:
            words.append({"phones": list(current_word_ipa)})
            current_word_ipa.clear()

    for tok in tokens:
        if tok == " ":
            flush()
            continue
        ipa = arpabet_to_ipa(strip_stress(tok))
        if ipa is None:
            # Punctuation or symbols g2p couldn't map: treat as a word boundary.
            flush()
            continue
        current_word_ipa.append(ipa)
    flush()

    # Atomize per word and rebuild the flat list and the word text.
    src_words = [w for w in _split_words(text)]
    for idx, w in enumerate(words):
        w["phones"] = atomize(w["phones"])  # type: ignore[index]
        w["word"] = src_words[idx] if idx < len(src_words) else ""
        flat.extend(w["phones"])  # type: ignore[arg-type]

    return {"phones": flat, "words": words}


def _split_words(text: str) -> List[str]:
    """Word tokens that line up with g2p's word boundaries (alphabetic runs)."""
    import re

    return re.findall(r"[A-Za-z']+", text)
