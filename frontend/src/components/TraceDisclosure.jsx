import TraceSteps from './TraceSteps'

// Collapsed by default: the answer is what the analyst came for, and the work
// behind it should be one click away rather than in the way. Native <details>
// so it needs no state and stays keyboard-accessible.

export default function TraceDisclosure({ trace }) {
  if (!trace) return null

  const tools = (trace.steps || []).filter((s) => s.kind === 'tool')
  const rounds = new Set((trace.steps || []).map((s) => s.round)).size
  const seconds = ((trace.latency_ms || 0) / 1000).toFixed(1)
  const summary =
    `${tools.length} signal${tools.length === 1 ? '' : 's'} · ` +
    `${rounds} round${rounds === 1 ? '' : 's'} · ${seconds}s`

  return (
    <details className="trace">
      <summary>{summary}</summary>
      {tools.length === 0 && (
        // The finding worth watching for: the answer came from training
        // knowledge, not from BTS data.
        <p className="trace-empty">
          No signal was measured — this answer did not come from the data.
        </p>
      )}
      <TraceSteps steps={trace.steps} />
      {trace.error && <p className="trace-step-error">{trace.error}</p>}
    </details>
  )
}
