import os
import tempfile

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import Attempt, Sentence
from .pipeline import analyze
from .schemas import AnalysisResult, AttemptSummary, SentenceCreate, SentenceOut
from .synth import synth_phones
from .seed import init_db

app = FastAPI(title="Speak — pronunciation feedback")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/sentences", response_model=list[SentenceOut])
def list_sentences(db: Session = Depends(get_db)):
    return db.query(Sentence).order_by(Sentence.id).all()


@app.post("/api/sentences", response_model=SentenceOut, status_code=201)
def create_sentence(payload: SentenceCreate, db: Session = Depends(get_db)):
    sentence = Sentence(text=payload.text.strip())
    if not sentence.text:
        raise HTTPException(status_code=422, detail="text must not be empty")
    db.add(sentence)
    db.commit()
    db.refresh(sentence)
    return sentence


@app.get("/api/pronounce")
def pronounce(phones: str):
    """Speak a space-separated IPA phone sequence (e.g. ?phones=θ ɔ t).

    If there is nothing pronounceable (e.g. a word was dropped entirely, so the
    "what we heard" phones are empty), return 204 No Content rather than an
    error — the player just no-ops instead of surfacing a failed request.
    """
    tokens = phones.split()
    audio = synth_phones(tokens)
    if audio is None:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/api/attempts", response_model=list[AttemptSummary])
def list_attempts(sentence_id: int, db: Session = Depends(get_db)):
    """Most-recent-first history of attempts for one sentence."""
    return (
        db.query(Attempt)
        .filter(Attempt.sentence_id == sentence_id)
        .order_by(Attempt.created_at.desc(), Attempt.id.desc())
        .limit(20)
        .all()
    )


@app.post("/api/attempts", response_model=AnalysisResult)
async def create_attempt(
    sentence_id: int = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    sentence = db.get(Sentence, sentence_id)
    if sentence is None:
        raise HTTPException(status_code=404, detail="sentence not found")

    # Persist the upload to a temp file for ffmpeg/whisper/allosaurus to read.
    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await audio.read())

        try:
            result = analyze(tmp_path, sentence.text)
        except Exception as exc:  # surface model/ffmpeg failures as a 500 with detail
            raise HTTPException(status_code=500, detail=f"analysis failed: {exc}") from exc

        attempt = Attempt(
            sentence_id=sentence.id,
            word_transcript=result["word_transcript"],
            transcript_match=result["transcript_match"],
            expected_phones=result["expected_phones"],
            produced_phones=result["produced_phones"],
            alignment=result["alignment"],
            phoneme_error_rate=result["phoneme_error_rate"],
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        return AnalysisResult(
            id=attempt.id,
            sentence_id=attempt.sentence_id,
            word_transcript=attempt.word_transcript,
            transcript_match=attempt.transcript_match,
            expected_phones=attempt.expected_phones,
            produced_phones=attempt.produced_phones,
            alignment=attempt.alignment,
            phoneme_error_rate=attempt.phoneme_error_rate,
            expected_words=result["expected_words"],
            errors=result["errors"],
            clean_audio=result["clean_audio"],
            volume=result["volume"],
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
