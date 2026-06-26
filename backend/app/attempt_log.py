"""Per-attempt logging of expected vs. heard phonemes.

Two sinks, both written from `log_attempt`:
  1. A human-readable summary to the console (the `speak.attempts` logger), so
     you can eyeball recognition quality while testing.
  2. One JSON object per line appended to `<log_dir>/attempts.jsonl` — a growing
     dataset of (target, expected phones, produced phones, per-word scores) for
     diagnosing systematic recognizer errors and, later, fine-tuning.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List

from .config import settings

logger = logging.getLogger("speak.attempts")


def _ensure_console_handler() -> None:
    """Make sure our summary lines show up even if uvicorn didn't add a handler."""
    if logger.handlers or logger.propagate is False:
        return
    # If the root logger already has handlers (uvicorn), let it propagate there.
    if logging.getLogger().handlers:
        logger.setLevel(logging.INFO)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _word_rows(expected_words: List[Dict[str, object]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for w in expected_words:
        rows.append(
            {
                "word": w.get("word", ""),
                "expected": " ".join(w.get("phones", [])),       # type: ignore[arg-type]
                "produced": " ".join(w.get("produced", [])),     # type: ignore[arg-type]
                "score": w.get("score"),
                "errors": w.get("error_count"),
            }
        )
    return rows


def log_attempt(target_text: str, result: Dict[str, object]) -> None:
    """Log one analysis: console summary + a JSONL line. Never raises."""
    try:
        _ensure_console_handler()

        expected = " ".join(result.get("expected_phones", []))       # type: ignore[arg-type]
        produced = " ".join(result.get("produced_phones", []))       # type: ignore[arg-type]
        words = _word_rows(result.get("expected_words", []))         # type: ignore[arg-type]
        per = result.get("phoneme_error_rate")
        per_str = f"{per:.3f}" if isinstance(per, (int, float)) else str(per)

        # Console summary: target, both phone strings, and the words that missed.
        missed = [f"{w['word']}({w['score']})" for w in words if (w.get("errors") or 0) > 0]
        logger.info(
            "attempt | PER=%s match=%s | target=%r\n"
            "         expected: %s\n"
            "         heard:    %s\n"
            "         whisper:  %r | misses: %s",
            per_str,
            result.get("transcript_match"),
            target_text,
            expected,
            produced,
            result.get("word_transcript"),
            ", ".join(missed) or "none",
        )

        vol = result.get("volume") or {}
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "recognizer": settings.recognizer,
            "target": target_text,
            "word_transcript": result.get("word_transcript"),
            "transcript_match": result.get("transcript_match"),
            "phoneme_error_rate": per,
            "expected_phones": expected,
            "produced_phones": produced,
            "volume_fades": vol.get("fades"),
            "volume_drop": vol.get("drop"),
            "words": words,
        }
        os.makedirs(settings.log_dir, exist_ok=True)
        path = os.path.join(settings.log_dir, "attempts.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # logging must never break an analysis
        logger.exception("failed to log attempt")
