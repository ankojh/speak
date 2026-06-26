import type { AttemptSummary } from './api'

/** Per-sentence attempt history so you can watch your accuracy improve. */
export function History({ attempts }: { attempts: AttemptSummary[] }) {
  if (attempts.length === 0) return null

  const accuracies = attempts.map((a) => Math.round((1 - a.phoneme_error_rate) * 100))
  const best = Math.max(...accuracies)

  return (
    <section className="history">
      <h3>
        Your attempts ({attempts.length}) · best {best}%
      </h3>
      <ul className="history-list">
        {attempts.map((a, i) => {
          const acc = accuracies[i]
          return (
            <li key={a.id} className="history-row">
              <span className="history-bar">
                <span className="history-fill" style={{ width: `${acc}%` }} />
              </span>
              <span className="history-acc">{acc}%</span>
              <span className="history-when">
                {new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              <span className="history-said" title={a.word_transcript}>
                "{a.word_transcript || '—'}"
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
