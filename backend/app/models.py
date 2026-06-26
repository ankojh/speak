from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .database import Base


class Sentence(Base):
    __tablename__ = "sentences"

    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attempts = relationship("Attempt", back_populates="sentence", cascade="all, delete-orphan")


class Attempt(Base):
    """One recording of a user reading a target sentence, plus its analysis."""

    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True)
    sentence_id = Column(Integer, ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False)

    # Whisper word-level transcript (confirms the right sentence was read).
    word_transcript = Column(Text, nullable=False, default="")
    # Fraction of target words matched in the transcript (0..1).
    transcript_match = Column(Float, nullable=False, default=0.0)

    # Phoneme sequences (lists of IPA tokens) stored as JSON.
    expected_phones = Column(JSONB, nullable=False, default=list)
    produced_phones = Column(JSONB, nullable=False, default=list)

    # The alignment: a list of ops {type, expected, produced}.
    alignment = Column(JSONB, nullable=False, default=list)
    # Phoneme error rate = (subs + dels + ins) / len(expected).
    phoneme_error_rate = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sentence = relationship("Sentence", back_populates="attempts")
