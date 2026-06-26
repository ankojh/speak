"""Articulatory feature distance between IPA segments, via panphon.

Used to weight the Needleman-Wunsch substitution cost so the alignment pairs
phonetically similar sounds (e.g. /θ/~/s/) rather than aligning a vowel to a
far-off consonant. The value is normalized to roughly [0, 1] where 0 means the
two segments share all features and 1 means they share none.
"""

from functools import lru_cache

_dist = None


def _get_distance():
    global _dist
    if _dist is None:
        from panphon.distance import Distance

        _dist = Distance()
    return _dist


@lru_cache(maxsize=8192)
def feature_distance(a: str, b: str) -> float:
    if a == b:
        return 0.0
    try:
        d = _get_distance().feature_edit_distance(a, b)
    except Exception:
        # Unknown symbol for panphon: treat as a maximally distinct substitution.
        return 1.0
    return max(0.0, min(1.0, float(d)))
