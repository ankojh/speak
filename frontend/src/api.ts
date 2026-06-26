export interface Sentence {
  id: number
  text: string
}

export type OpType = 'match' | 'sub' | 'del' | 'ins'

export interface AlignmentOp {
  type: OpType
  expected: string | null
  produced: string | null
  severity: number
}

export interface ExpectedWord {
  word: string
  phones: string[]
  produced: string[]
  ops: AlignmentOp[]
  error_count: number
  score: number
  audio_start: number | null
  audio_end: number | null
}

export interface AttemptSummary {
  id: number
  sentence_id: number
  word_transcript: string
  transcript_match: number
  phoneme_error_rate: number
  created_at: string
}

export interface Volume {
  user: number[]
  reference: number[]
  fades: boolean
  drop: number
  start_level: number
  end_level: number
}

export interface AnalysisResult {
  id: number
  sentence_id: number
  word_transcript: string
  transcript_match: number
  expected_phones: string[]
  produced_phones: string[]
  alignment: AlignmentOp[]
  phoneme_error_rate: number
  expected_words: ExpectedWord[]
  errors: AlignmentOp[]
  clean_audio: string | null
  volume: Volume | null
}

export async function fetchSentences(): Promise<Sentence[]> {
  const res = await fetch('/api/sentences')
  if (!res.ok) throw new Error('Failed to load sentences')
  return res.json()
}

/** URL that returns synthesized speech for a sequence of IPA phones. */
export function pronounceUrl(phones: string[]): string {
  return `/api/pronounce?phones=${encodeURIComponent(phones.join(' '))}`
}

export async function fetchAttempts(sentenceId: number): Promise<AttemptSummary[]> {
  const res = await fetch(`/api/attempts?sentence_id=${sentenceId}`)
  if (!res.ok) throw new Error('Failed to load history')
  return res.json()
}

export async function submitAttempt(
  sentenceId: number,
  audio: Blob,
): Promise<AnalysisResult> {
  const form = new FormData()
  form.append('sentence_id', String(sentenceId))
  form.append('audio', audio, 'recording.webm')

  const res = await fetch('/api/attempts', { method: 'POST', body: form })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `Request failed (${res.status})`)
  }
  return res.json()
}
