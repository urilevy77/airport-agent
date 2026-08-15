import { useEffect, useState } from 'react'
import { fetchTrace, fetchTraces } from '../api/chat'
import TraceSteps from './TraceSteps'

// Past turns, across sessions. Reached at /#traces?key=... — see App.jsx for why
// this is a hash route rather than a real one.

export default function TracesPage({ traceKey }) {
  const [rows, setRows] = useState([])
  const [openId, setOpenId] = useState(null)
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!traceKey) return
    let live = true
    fetchTraces(traceKey, { limit: 50, offset: 0 })
      .then((body) => { if (live) setRows(body.traces || []) })
      .catch((e) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [traceKey])

  const show = (id) => {
    if (openId === id) { setOpenId(null); setOpen(null); return }
    setOpenId(id)
    setOpen(null)
    fetchTrace(traceKey, id).then(setOpen).catch((e) => setError(e.message))
  }

  if (!traceKey) {
    return (
      <div className="traces-page">
        <h1>Traces</h1>
        <p className="trace-empty">
          Add ?key=… to the address (after the #) to read stored traces.
        </p>
      </div>
    )
  }

  return (
    <div className="traces-page">
      <h1>Traces</h1>
      {error && <p className="trace-step-error">{error}</p>}
      {!error && !rows.length && <p className="trace-empty">No turns recorded yet.</p>}
      <ol className="traces-list">
        {rows.map((row) => (
          <li key={row.id} className={row.error ? 'traces-row failed' : 'traces-row'}>
            <button type="button" className="traces-row-head" onClick={() => show(row.id)}>
              <span className="traces-question">{row.question}</span>
              <span className="traces-meta">
                {row.step_count} steps · {((row.latency_ms || 0) / 1000).toFixed(1)}s
                {' · '}{row.ts.slice(0, 19).replace('T', ' ')}
              </span>
            </button>
            {row.error && <div className="trace-step-error">{row.error}</div>}
            {openId === row.id && open && (
              <div className="traces-detail">
                <p className="traces-answer">{open.answer}</p>
                <TraceSteps steps={open.steps} />
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
