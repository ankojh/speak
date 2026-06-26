import { useEffect, useState } from 'react'
import { pronounceUrl, type AlignmentOp, type AnalysisResult, type ExpectedWord } from './api'
import { decodeBlob, decodeUrl, playRange, playUrl } from './audioClip'
import { speak, ttsSupported } from './speech'
import { VolumeChart } from './VolumeChart'

const OP_LABEL: Record<string, string> = {
  sub: 'substituted',
  del: 'dropped',
  ins: 'extra sound',
}

interface Props {
  result: AnalysisResult
  targetText: string
  recordingUrl: string | null
  recordingBlob: Blob | null
}

/** Actionable feedback: hear yourself, hear the reference, see which words were off. */
export function DiffView({ result, targetText, recordingUrl, recordingBlob }: Props) {
  const accuracy = Math.round((1 - result.phoneme_error_rate) * 100)
  const transcriptPct = Math.round(result.transcript_match * 100)

  // Prefer the server's noise-reduced audio for playback; fall back to the raw
  // recording if cleaning failed.
  const playbackSrc = result.clean_audio ?? recordingUrl

  // Decode it once so we can play back individual word slices.
  const [buffer, setBuffer] = useState<AudioBuffer | null>(null)
  useEffect(() => {
    let alive = true
    const decode = result.clean_audio
      ? decodeUrl(result.clean_audio)
      : recordingBlob
        ? decodeBlob(recordingBlob)
        : null
    if (!decode) {
      setBuffer(null)
      return
    }
    decode.then((b) => alive && setBuffer(b)).catch(() => alive && setBuffer(null))
    return () => {
      alive = false
    }
  }, [result.clean_audio, recordingBlob])

  return (
    <div className="diff">
      <div className="scores">
        <Score label="Pronunciation accuracy" value={`${accuracy}%`} hint="1 − phoneme error rate" />
        <Score label="Read correctly" value={`${transcriptPct}%`} hint="words matched by Whisper" />
      </div>

      {/* Listen & compare */}
      <section className="listen">
        <div className="listen-row">
          <span className="listen-label">
            🎙️ What you said{result.clean_audio ? ' (noise-reduced)' : ''}
          </span>
          {playbackSrc ? (
            <audio className="player" controls src={playbackSrc} />
          ) : (
            <span className="hint">recording unavailable</span>
          )}
        </div>
        <div className="listen-row">
          <span className="listen-label">✅ How it should sound</span>
          <button
            className="speak-btn"
            disabled={!ttsSupported}
            onClick={() => speak(targetText)}
            title={ttsSupported ? 'Play the correct pronunciation' : 'TTS not supported in this browser'}
          >
            🔊 Play correct
          </button>
          <span className="hint">Whisper heard you say: <em>"{result.word_transcript || '—'}"</em></span>
        </div>
      </section>

      {/* Loudness over the sentence — surfaces an end-of-sentence fade */}
      {result.volume && <VolumeChart volume={result.volume} />}

      {/* Word-by-word: tap to hear the correct word, then your own version */}
      <h3>Tap a word to hear it · red words add 🔊 target vs. what we heard</h3>
      <div className="word-row">
        {result.expected_words.map((w, i) => (
          <WordChip key={i} word={w} buffer={buffer} />
        ))}
      </div>

      {/* Phoneme-level detail, collapsed by default */}
      <details className="details">
        <summary>Pronunciation differences ({result.errors.length})</summary>

        <div className="alignment">
          {result.alignment.map((op, i) => (
            <Cell key={i} op={op} />
          ))}
        </div>
        <Legend />

        {result.errors.length === 0 ? (
          <p className="perfect">No phoneme errors detected. Nicely done!</p>
        ) : (
          <ul className="errors">
            {result.errors.map((op, i) => (
              <li key={i} className={`err err-${op.type}`}>
                <span className="tag">{OP_LABEL[op.type]}</span>{' '}
                {op.type === 'sub' && (
                  <span>
                    expected <b>/{op.expected}/</b> &rarr; you said <b>/{op.produced}/</b>
                  </span>
                )}
                {op.type === 'del' && (
                  <span>
                    missing <b>/{op.expected}/</b>
                  </span>
                )}
                {op.type === 'ins' && (
                  <span>
                    added <b>/{op.produced}/</b>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </details>
    </div>
  )
}

function WordChip({ word, buffer }: { word: ExpectedWord; buffer: AudioBuffer | null }) {
  const hasError = word.error_count > 0
  const expected = word.phones.join(' ')
  const said = word.produced.join(' ')
  const pct = Math.round(word.score * 100)
  const hasClip = buffer != null && word.audio_start != null && word.audio_end != null

  function handleClick() {
    // First play the correct word, then play back what the user actually said.
    speak(word.word, () => {
      if (hasClip) playRange(buffer!, word.audio_start!, word.audio_end!)
    })
  }

  return (
    <div className={`word-wrap ${hasError ? 'is-error' : ''}`}>
      <button
        className={`word ${hasError ? 'word-error' : 'word-ok'}`}
        onClick={handleClick}
        title={hasError ? `expected /${expected}/  —  you said /${said}/` : `/${expected}/`}
      >
        <span className="word-head">
          <span className="word-text">{word.word}</span>
          <span className="word-score">{pct}%</span>
        </span>
        {hasError && (
          <span className="word-detail">
            /{expected}/ → <span className="word-said">/{said || '—'}/</span>
          </span>
        )}
        <span className="word-play">▶ word{hasClip ? ' · yours' : ''}</span>
      </button>

      {hasError && (
        <div className="word-sounds">
          <button className="sound-btn target" onClick={() => playUrl(pronounceUrl(word.phones))}>
            🔊 target sounds
          </button>
          <button
            className="sound-btn heard"
            disabled={word.produced.length === 0}
            onClick={() => playUrl(pronounceUrl(word.produced))}
          >
            🔊 what we heard
          </button>
        </div>
      )}
    </div>
  )
}

function Cell({ op }: { op: AlignmentOp }) {
  const top = op.expected ?? '·'
  const bottom = op.produced ?? '·'
  return (
    <div className={`cell cell-${op.type}`} title={op.type}>
      <span className="expected">{top}</span>
      <span className="produced">{bottom}</span>
    </div>
  )
}

function Legend() {
  return (
    <div className="legend">
      <span className="chip cell-match">match</span>
      <span className="chip cell-sub">substitution</span>
      <span className="chip cell-del">deletion</span>
      <span className="chip cell-ins">insertion</span>
      <span className="legend-note">top = expected, bottom = produced</span>
    </div>
  )
}

function Score({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="score">
      <div className="score-value">{value}</div>
      <div className="score-label">{label}</div>
      <div className="score-hint">{hint}</div>
    </div>
  )
}
