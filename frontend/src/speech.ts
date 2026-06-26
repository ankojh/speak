// Text-to-speech for the reference ("what you should have spoken"), using the
// browser's built-in SpeechSynthesis. Slightly slowed down so sounds are clear.

function pickVoice(): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis?.getVoices() ?? []
  return (
    voices.find((v) => /en[-_]US/i.test(v.lang) && /Samantha|Google US|Natural/i.test(v.name)) ||
    voices.find((v) => /en[-_]US/i.test(v.lang)) ||
    voices.find((v) => /^en/i.test(v.lang))
  )
}

export function speak(text: string, onEnd?: () => void, rate = 0.85) {
  if (!('speechSynthesis' in window)) {
    onEnd?.()
    return
  }
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'en-US'
  utterance.rate = rate
  const voice = pickVoice()
  if (voice) utterance.voice = voice
  if (onEnd) {
    utterance.onend = onEnd
    utterance.onerror = onEnd
  }
  window.speechSynthesis.speak(utterance)
}

export const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
