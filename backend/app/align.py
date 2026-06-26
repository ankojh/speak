"""Sequence alignment of expected vs produced phonemes (Needleman-Wunsch).

The substitutions, insertions, and deletions in the optimal alignment ARE the
pronunciation errors:
  - substitution: a sound was replaced (e.g. /θ/ -> /t/)
  - deletion:     an expected sound was dropped (e.g. a missing final consonant)
  - insertion:    an extra sound was produced
"""

from dataclasses import dataclass
from typing import List

from .features import feature_distance
from .phonemes import normalize

# Insertions/deletions cost a full unit; substitutions are weighted by how far
# apart the two sounds are (panphon feature distance), with a small floor so a
# genuine substitution is never free. This makes the alignment phonetically
# faithful while still pairing similar segments.
INDEL = 1.0
MIN_SUB = 0.05


def _sub_cost(expected: "Phone", produced: "Phone") -> float:
    if expected.key == produced.key:
        return 0.0
    return max(MIN_SUB, feature_distance(expected.ipa, produced.ipa))


@dataclass
class Phone:
    ipa: str   # original symbol shown to the user
    key: str   # normalized symbol used for comparison


def to_phones(tokens: List[str]) -> List[Phone]:
    return [Phone(ipa=t, key=normalize(t)) for t in tokens]


def align(expected: List[Phone], produced: List[Phone]) -> List[dict]:
    """Return the alignment as an ordered list of ops.

    Each op is {"type": match|sub|del|ins, "expected": str|None, "produced": str|None}.
    """
    n, m = len(expected), len(produced)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i * INDEL
    for j in range(1, m + 1):
        dp[0][j] = j * INDEL

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = dp[i - 1][j - 1] + _sub_cost(expected[i - 1], produced[j - 1])
            up = dp[i - 1][j] + INDEL      # expected phone unmatched -> deletion
            left = dp[i][j - 1] + INDEL    # produced phone unmatched -> insertion
            dp[i][j] = min(diag, up, left)

    # Backtrack from (n, m) to (0, 0).
    ops: List[dict] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            cost = _sub_cost(expected[i - 1], produced[j - 1])
            if abs(dp[i][j] - (dp[i - 1][j - 1] + cost)) < 1e-9:
                same = expected[i - 1].key == produced[j - 1].key
                ops.append({
                    "type": "match" if same else "sub",
                    "expected": expected[i - 1].ipa,
                    "produced": produced[j - 1].ipa,
                    "severity": 0.0 if same else round(cost, 3),
                })
                i, j = i - 1, j - 1
                continue
        if i > 0 and abs(dp[i][j] - (dp[i - 1][j] + INDEL)) < 1e-9:
            ops.append({"type": "del", "expected": expected[i - 1].ipa, "produced": None, "severity": 1.0})
            i -= 1
            continue
        ops.append({"type": "ins", "expected": None, "produced": produced[j - 1].ipa, "severity": 1.0})
        j -= 1

    ops.reverse()
    return ops


def phoneme_error_rate(ops: List[dict], expected_len: int) -> float:
    """PER = (substitutions + deletions + insertions) / expected length."""
    if expected_len == 0:
        return 0.0
    errors = sum(1 for op in ops if op["type"] != "match")
    return errors / expected_len


def attribute_ops_to_words(ops: List[dict], words: List[dict]) -> List[dict]:
    """Map alignment ops back onto the words they belong to.

    The expected phone sequence is the concatenation of each word's phones, so
    we walk the ops tracking our position in the expected sequence to learn
    which word each substitution/deletion/insertion falls in. Returns a new
    list of words, each enriched with `ops`, `produced` (what was actually
    said for that word), and `error_count`.
    """
    # Cumulative end index of each word in the expected phone sequence.
    ends: List[int] = []
    running = 0
    for w in words:
        running += len(w["phones"])
        ends.append(running)
    total = running

    def word_for(idx: int) -> int:
        capped = min(idx, total - 1) if total else 0
        for wi, end in enumerate(ends):
            if capped < end:
                return wi
        return max(len(words) - 1, 0)

    enriched = [
        {"word": w["word"], "phones": w["phones"], "ops": [], "produced": [], "error_count": 0}
        for w in words
    ]
    if not enriched:
        return enriched

    exp_idx = 0
    for op in ops:
        wi = word_for(exp_idx)
        enriched[wi]["ops"].append(op)
        if op["produced"] is not None:
            enriched[wi]["produced"].append(op["produced"])
        if op["type"] != "match":
            enriched[wi]["error_count"] += 1
        if op["type"] in ("match", "sub", "del"):  # consumes an expected phone
            exp_idx += 1

    # Per-word score: 1 - (errors / expected phones in the word), clamped to [0, 1].
    for w in enriched:
        denom = len(w["phones"]) or 1
        w["score"] = round(max(0.0, 1.0 - w["error_count"] / denom), 2)

    return enriched
