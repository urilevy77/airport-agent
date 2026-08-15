/**
 * The stat tile, shared by the pane's headline row and the leader panel so the
 * two never drift apart. Formatting happens upstream (charts/stats.js, or the
 * leader panel's own formatters) — this file only lays out.
 */

/**
 * Value on top, what it measures under it, then the context that gives it
 * meaning. `tone` tints only the left rule: a status color must never be the
 * sole carrier of the meaning, so the note beside it always names the verdict
 * in words.
 */
export function StatTile({ value, label, note, tone }) {
  return (
    <div className={`stat-tile${tone ? ` ${tone}` : ''}`}>
      {/* Proportional figures on purpose — tabular-nums makes a large standalone
          number look loose. Columns of numbers get .tabular; headlines don't. */}
      <div className="stat-value">{value}</div>
      <span className="stat-label">{label}</span>
      {note ? <div className="stat-note">{note}</div> : null}
    </div>
  )
}

/** The headline numbers for one tool result. Renders nothing when there are none. */
export default function StatRow({ stats }) {
  if (!stats.length) return null
  return (
    <div className="stat-row">
      {stats.map((stat) => <StatTile key={stat.label} {...stat} />)}
    </div>
  )
}
