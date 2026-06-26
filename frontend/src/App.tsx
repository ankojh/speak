import { useEffect, useState } from 'react'
import './App.css'
import {
  fetchAttempts,
  fetchSentences,
  submitAttempt,
  type AnalysisResult,
  type AttemptSummary,
  type Sentence,
} from './api'
import { DiffView } from './DiffView'
import { History } from './History'
import { useRecorder } from './useRecorder'

export default function App() {
  const [sentences, setSentences] = useState<Sentence[]>([])
  const [index, setIndex] = useState(0)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null)
  const [recordingBlob, setRecordingBlob] = useState<Blob | null>(null)
  const [history, setHistory] = useState<AttemptSummary[]>([])
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const recorder = useRecorder()
  const current = sentences[index]

  useEffect(() => {
    fetchSentences()
      .then(setSentences)
      .catch((e) => setError(e.message))
  }, [])

  // Load attempt history whenever the selected sentence changes.
  useEffect(() => {
    if (!current) return
    fetchAttempts(current.id).then(setHistory).catch(() => setHistory([]))
  }, [current?.id])

  function clearResult() {
    setResult(null)
    setRecordingBlob(null)
    setRecordingUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
  }

  function selectIndex(next: number) {
    setIndex(next)
    clearResult()
    setError(null)
  }

  async function handleRecord() {
    setError(null)
    if (recorder.state === 'idle') {
      clearResult()
      await recorder.start().catch(() => {})
      return
    }
    // Stop -> get audio -> play back + analyze.
    const blob = await recorder.stop()
    if (!current) return
    setRecordingBlob(blob)
    setRecordingUrl(URL.createObjectURL(blob))
    setAnalyzing(true)
    try {
      const res = await submitAttempt(current.id, blob)
      setResult(res)
      fetchAttempts(current.id).then(setHistory).catch(() => {})
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  const recording = recorder.state === 'recording'

  return (
    <div className="app">
      <header>
        <h1>🗣️ Speak</h1>
        <p className="subtitle">
          Read the sentence aloud — get phoneme-level pronunciation feedback.
        </p>
      </header>

      {error && <div className="banner error">{error}</div>}
      {recorder.error && <div className="banner error">{recorder.error}</div>}

      {current ? (
        <>
          <section className="prompt">
            <div className="prompt-nav">
              <button onClick={() => selectIndex(Math.max(0, index - 1))} disabled={index === 0}>
                ‹ Prev
              </button>
              <span className="counter">
                {index + 1} / {sentences.length}
              </span>
              <button
                onClick={() => selectIndex(Math.min(sentences.length - 1, index + 1))}
                disabled={index === sentences.length - 1}
              >
                Next ›
              </button>
            </div>
            <p className="target">{current.text}</p>
          </section>

          <section className="controls">
            <button
              className={`record ${recording ? 'is-recording' : ''}`}
              onClick={handleRecord}
              disabled={analyzing}
            >
              {analyzing ? 'Analyzing…' : recording ? '■ Stop & analyze' : '● Record'}
            </button>
            {recording && <span className="hint">Recording… read the sentence, then stop.</span>}
            {analyzing && <span className="hint">Running Whisper + Allosaurus…</span>}
          </section>

          {result && (
            <DiffView
              result={result}
              targetText={current.text}
              recordingUrl={recordingUrl}
              recordingBlob={recordingBlob}
            />
          )}

          <History attempts={history} />
        </>
      ) : (
        !error && <p>Loading sentences…</p>
      )}
    </div>
  )
}
