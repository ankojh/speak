import type { Volume } from './api'

// Overlapping line chart of relative loudness over the sentence: your recording
// vs. a steady reference. Each line is peak-normalized, so this is about *shape*
// (does your volume hold up, or fade at the end?) not absolute level.

const W = 100 // viewBox units; SVG scales to its container width via CSS
const H = 56

function toLine(values: number[]): string {
  if (values.length < 2) return ''
  const step = W / (values.length - 1)
  return values
    .map((v, i) => `${(i * step).toFixed(2)},${(H - v * H).toFixed(2)}`)
    .join(' ')
}

function toArea(values: number[]): string {
  if (values.length < 2) return ''
  const step = W / (values.length - 1)
  const pts = values.map((v, i) => `L${(i * step).toFixed(2)} ${(H - v * H).toFixed(2)}`)
  return `M0 ${H} ${pts.join(' ')} L${W} ${H} Z`
}

export function VolumeChart({ volume }: { volume: Volume }) {
  const { user, reference, fades, drop } = volume
  if (!user || user.length < 2) return null

  const dropPct = Math.round(drop * 100)
  const userColor = fades ? 'var(--del)' : 'var(--accent)'

  return (
    <section className="volume">
      <div className="volume-head">
        <span className="listen-label">📉 Volume across the sentence</span>
        {fades ? (
          <span className="fade-flag">⚠️ Fades ~{dropPct}% by the end — keep your volume up to the last word</span>
        ) : (
          <span className="fade-ok">✓ Volume holds steady</span>
        )}
      </div>

      <svg className="volume-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
           aria-label="Loudness of your recording versus a steady reference">
        {/* faint mid gridline */}
        <line x1="0" y1={H / 2} x2={W} y2={H / 2} className="vc-grid" vectorEffect="non-scaling-stroke" />
        {/* area under your line */}
        <path d={toArea(user)} fill={userColor} opacity={0.12} />
        {/* reference (steady) line, dashed */}
        {reference.length >= 2 && (
          <polyline points={toLine(reference)} className="vc-ref" fill="none"
                    vectorEffect="non-scaling-stroke" />
        )}
        {/* your line */}
        <polyline points={toLine(user)} fill="none" stroke={userColor} strokeWidth={2}
                  vectorEffect="non-scaling-stroke" />
      </svg>

      <div className="volume-axis">
        <span>start of sentence</span>
        <span className="volume-legend">
          <span className="lg-you" style={{ color: userColor }}>━ you</span>
          <span className="lg-ref">┄ steady reference</span>
        </span>
        <span>end</span>
      </div>
    </section>
  )
}
