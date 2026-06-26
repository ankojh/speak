import { useCallback, useRef, useState } from 'react'

type RecorderState = 'idle' | 'recording'

/** Minimal mic recorder built on MediaRecorder; returns a webm/opus Blob. */
export function useRecorder() {
  const [state, setState] = useState<RecorderState>('idle')
  const [error, setError] = useState<string | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const start = useCallback(async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.start()
      recorderRef.current = recorder
      setState('recording')
    } catch (e) {
      setError('Microphone access denied or unavailable.')
      throw e
    }
  }, [])

  const stop = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current
      if (!recorder) return
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        recorder.stream.getTracks().forEach((t) => t.stop())
        setState('idle')
        resolve(blob)
      }
      recorder.stop()
    })
  }, [])

  return { state, error, start, stop }
}
