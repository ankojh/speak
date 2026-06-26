// Decode the recorded Blob once into an AudioBuffer, then play arbitrary time
// ranges from it. Using the Web Audio API (rather than seeking an <audio>
// element) makes slicing reliable for webm/opus recordings.

let ctx: AudioContext | null = null

function getCtx(): AudioContext {
  if (!ctx) ctx = new AudioContext()
  return ctx
}

export async function decodeBlob(blob: Blob): Promise<AudioBuffer> {
  const data = await blob.arrayBuffer()
  return getCtx().decodeAudioData(data)
}

/** Decode audio from a URL (including a data: URL), e.g. the cleaned mp3. */
export async function decodeUrl(url: string): Promise<AudioBuffer> {
  const res = await fetch(url)
  const data = await res.arrayBuffer()
  return getCtx().decodeAudioData(data)
}

/** Play audio from a URL (e.g. the /api/pronounce endpoint). */
export function playUrl(url: string) {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
  new Audio(url).play().catch(() => {})
}

/**
 * Play buffer[start..end] (seconds) as an isolated word: a short silence lead,
 * then the slice with brief fade-in/out so the edges don't click (clicks make a
 * clean cut sound like it bleeds). Returns a stop() to cut it short.
 */
export function playRange(buffer: AudioBuffer, start: number, end: number): () => void {
  const c = getCtx()
  if (c.state === 'suspended') c.resume()

  const from = Math.max(0, start)
  const duration = Math.max(0.05, end - start)
  const fade = Math.min(0.015, duration / 4) // 15 ms edges, clamped for tiny clips
  const lead = 0.08 // small silence before the word so it stands on its own
  const t0 = c.currentTime + lead

  const gain = c.createGain()
  gain.connect(c.destination)
  gain.gain.setValueAtTime(0, t0)
  gain.gain.linearRampToValueAtTime(1, t0 + fade)
  gain.gain.setValueAtTime(1, t0 + duration - fade)
  gain.gain.linearRampToValueAtTime(0, t0 + duration)

  const src = c.createBufferSource()
  src.buffer = buffer
  src.connect(gain)
  src.start(t0, from, duration)
  return () => {
    try {
      src.stop()
    } catch {
      /* already stopped */
    }
  }
}
