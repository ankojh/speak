from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, overridable via environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres. Local Homebrew Postgres uses trust auth for the OS user by default.
    database_url: str = "postgresql+psycopg2://localhost:5432/speak"

    # faster-whisper (CTranslate2). "base" is a good CPU default; use int8 for speed.
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # Phoneme recognizer: "wav2vec2" (accurate, robust to real audio) or
    # "allosaurus" (lighter, but weaker on noisy recordings).
    recognizer: str = "wav2vec2"
    wav2vec2_model: str = "facebook/wav2vec2-lv-60-espeak-cv-ft"
    allosaurus_lang: str = "eng"  # phone inventory when using allosaurus

    # Noise reduction + loudness recovery during conversion. The chain:
    #   highpass     - kill low rumble / HVAC / desk thumps
    #   afftdn       - FFT denoiser with noise tracking (tn=1), adapts as the
    #                  background changes; nr is the reduction in dB
    #   speechnorm   - lift quiet/fading speech back up so the tail of a sentence
    #                  is still audible to the recognizer
    # wav2vec2 tolerates this far better than Allosaurus did. Set DENOISE=false
    # to disable, or tune AUDIO_FILTER.
    denoise: bool = True
    audio_filter: str = (
        "highpass=f=80,afftdn=nr=20:nf=-30:tn=1,speechnorm=e=12.5:r=0.0005:l=1"
    )
    # Denoise WITHOUT the loudness normalization — used only to measure the true
    # volume envelope (so the end-of-sentence fade is still visible instead of
    # being flattened out by speechnorm).
    envelope_filter: str = "highpass=f=80,afftdn=nr=20:nf=-30:tn=1"

    # Comma-separated list of allowed CORS origins (the Vite dev server).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Where to append per-attempt analysis logs (expected vs. heard phones) as
    # JSONL — a growing dataset for diagnosing/improving recognition. Relative
    # paths are resolved against the backend working directory.
    log_dir: str = "logs"


settings = Settings()
