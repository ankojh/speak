from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SentenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str


class SentenceCreate(BaseModel):
    text: str


class AlignmentOp(BaseModel):
    type: str  # match | sub | del | ins
    expected: Optional[str] = None
    produced: Optional[str] = None
    severity: float = 0.0  # 0 = identical, ~1 = maximally different (panphon)


class ExpectedWord(BaseModel):
    word: str
    phones: List[str]            # expected phones for this word
    produced: List[str] = []     # phones actually produced for this word
    ops: List[AlignmentOp] = []  # alignment ops attributed to this word
    error_count: int = 0
    score: float = 1.0           # per-word accuracy in [0, 1]
    audio_start: Optional[float] = None  # seconds into the recording
    audio_end: Optional[float] = None


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sentence_id: int
    word_transcript: str
    transcript_match: float
    expected_phones: List[str]
    produced_phones: List[str]
    alignment: List[AlignmentOp]
    phoneme_error_rate: float


class Volume(BaseModel):
    """Relative loudness envelopes for the volume chart (each peak-normalized)."""

    user: List[float] = []        # your recording's loudness over the utterance
    reference: List[float] = []   # a steady espeak baseline of the same sentence
    fades: bool = False           # True if loudness drops off toward the end
    drop: float = 0.0             # relative loudness lost by the final quarter
    start_level: float = 0.0
    end_level: float = 0.0


class AnalysisResult(AttemptOut):
    """Returned from POST /api/attempts. Adds fields not persisted on the row."""

    expected_words: List[ExpectedWord] = []
    errors: List[AlignmentOp] = []
    clean_audio: Optional[str] = None  # data URL of the noise-reduced recording
    volume: Optional[Volume] = None


class AttemptSummary(BaseModel):
    """Lightweight row for the per-sentence attempt history."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sentence_id: int
    word_transcript: str
    transcript_match: float
    phoneme_error_rate: float
    created_at: datetime
