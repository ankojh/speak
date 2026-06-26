# Speak — phoneme-level pronunciation feedback

Read a sentence aloud; the app tells you **which sounds you mispronounced**, down to
the individual phoneme. React + Python (FastAPI) + Postgres.

## How it works

Each recording runs through a two-pass pipeline:

1. **Dual transcription**
   - **Whisper** (`faster-whisper`) → a word-level transcript, used only to confirm
     you read the right sentence.
   - **Wav2Vec2Phoneme** (`facebook/wav2vec2-lv-60-espeak-cv-ft`) → outputs the
     **IPA sounds you actually produced**. Far more robust on real recordings than
     the lighter Allosaurus, which is still available via `RECOGNIZER=allosaurus`.
2. **Expected phonemes** — the target sentence is converted to its expected IPA
   sequence with `g2p_en` (CMUdict + a neural fallback for OOV words), mapped
   ARPABET → IPA.
3. **Alignment & diff** — produced vs. expected phonemes are aligned with
   **Needleman-Wunsch** (edit distance). The substitutions / insertions / deletions
   in the optimal alignment **are the pronunciation errors**:
   - `/θ/ → /t/` shows up as a **substitution**
   - a dropped final consonant shows up as a **deletion**
   - an extra sound shows up as an **insertion**

The result (transcript, both phoneme sequences, the alignment, and a phoneme error
rate) is stored in Postgres and rendered as a color-coded diff in the UI.

On the way in, audio is denoised and loudness-recovered with ffmpeg
(`afftdn` with noise tracking + `speechnorm`), which keeps the quiet tail of a
sentence audible to the recognizer. The UI also charts your **loudness across
the sentence** against a steady reference and flags an end-of-sentence fade.
Every attempt is logged (console + `backend/logs/attempts.jsonl`) with the
expected vs. heard phones, for diagnosing systematic recognition errors.

```
 audio ─┬─ ffmpeg → 16k mono wav ─┬─ Whisper  → words ──► transcript match
        │                         └─ Allosaurus → produced IPA ─┐
 target ─ g2p_en → expected IPA ──────────────────────────────► Needleman-Wunsch → diff
```

## Project layout

```
backend/            FastAPI app
  app/
    g2p.py          target sentence → expected IPA (CMUdict / g2p_en)
    phonemes.py     ARPABET→IPA map + IPA normalization
    recognize.py    Wav2Vec2 (or Allosaurus) → produced IPA
    transcribe.py   faster-whisper → word transcript
    align.py        Needleman-Wunsch alignment + phoneme error rate
    pipeline.py     orchestrates the whole analysis
    models.py       Sentence / Attempt (SQLAlchemy + Postgres)
    main.py         REST endpoints
frontend/           Vite + React + TypeScript
  src/
    useRecorder.ts  MediaRecorder mic capture
    api.ts          backend client + types
    DiffView.tsx    color-coded phoneme diff
    App.tsx         sentence picker + record button
```

## Prerequisites

- Python 3.12, Node 18+, Postgres 14+, **ffmpeg** (`brew install ffmpeg`)
- A running Postgres with a `speak` database: `createdb speak`

## Setup & run

### 1. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # installs torch, whisper, allosaurus, …
cp .env.example .env                      # adjust DATABASE_URL if needed
python -m app.seed                        # create tables + seed sentences
uvicorn app.main:app --reload --port 8000
```

The Whisper and Allosaurus models download automatically on the first request
(~150 MB total), so the first analysis is slower than later ones.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

`vite.config.ts` proxies `/api` to `http://localhost:8000`. If the backend runs on
another port, start the dev server with `VITE_API_TARGET=http://localhost:8008 npm run dev`.

Open http://localhost:5173, pick a sentence, hit **Record**, read it aloud, and
**Stop & analyze**.

## API

| Method | Path             | Description                                            |
|--------|------------------|--------------------------------------------------------|
| GET    | `/api/health`    | health check                                           |
| GET    | `/api/sentences` | list practice sentences                                |
| POST   | `/api/sentences` | add a sentence `{ "text": "..." }`                     |
| POST   | `/api/attempts`  | multipart `sentence_id` + `audio` → full analysis JSON |
| GET    | `/api/attempts?sentence_id=` | attempt history for a sentence             |

## Accuracy — what to tune next

This is a deliberately **basic** implementation. The machinery is correct; the
biggest accuracy levers from here:

- **Feature-weighted substitution cost** — *done.* The Needleman-Wunsch
  substitution cost is weighted by panphon articulatory-feature distance
  ([features.py](backend/app/features.py)), so /θ/→/s/ (close) costs less than
  /θ/→/k/ (far) and each substitution carries a `severity`. Next: expose severity
  in the UI (e.g. darker red for bigger misses).
- **Phoneme-set mismatch.** Allosaurus' universal inventory and CMUdict's IPA don't
  line up perfectly; tune the equivalence/normalization table in `phonemes.py`.
- **Denoise vs. loudness.** `AUDIO_FILTER` denoises and lifts fading speech; if a
  noisy room still trips recognition, raise `afftdn`'s `nr`, or drop in an
  `arnndn` RNN model. The volume chart is computed from `ENVELOPE_FILTER` (denoise
  only) so it shows your real delivery, not the normalized signal.
- **Better produced phonemes.** Now using `Wav2Vec2Phoneme`; fine-tuning on the
  target accent (or a larger XLSR model) is the next step for harder accents.
- **Per-word scoring & history** to track improvement over time (the `attempts`
  table already records every analysis).
