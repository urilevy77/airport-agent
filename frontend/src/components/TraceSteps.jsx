// The steps of one turn, grouped by round. Shared by the inline disclosure and
// the debug page, which is what keeps those two surfaces from drifting apart.

const seconds = (ms) => `${((ms || 0) / 1000).toFixed(1)}s`

const argsLine = (args) =>
  Object.entries(args || {})
    .map(([key, value]) => `${key}=${Array.isArray(value) ? value.join(',') : value}`)
    .join('  ')

function Step({ step }) {
  const failed = Boolean(step.error)
  return (
    <li className={`trace-step ${step.kind} ${failed ? 'failed' : ''}`}>
      <div className="trace-step-head">
        <span className="trace-step-name">{step.name || step.kind}</span>
        <span className="trace-step-ms">{seconds(step.ms)}</span>
      </div>
      {step.kind === 'tool' && (
        <div className="trace-step-args">{argsLine(step.args)}</div>
      )}
      {failed && <div className="trace-step-error">{step.error}</div>}
      {step.kind === 'tool' && step.result != null && (
        <details className="trace-raw">
          <summary>raw</summary>
          <pre>{JSON.stringify(step.result, null, 2)}</pre>
        </details>
      )}
    </li>
  )
}

export default function TraceSteps({ steps }) {
  if (!steps || !steps.length) return null

  const rounds = []
  steps.forEach((step) => {
    const round = rounds.find((r) => r.round === step.round)
    if (round) round.steps.push(step)
    else rounds.push({ round: step.round, steps: [step] })
  })

  return (
    <div className="trace-steps">
      {rounds.map((round) => (
        <div className="trace-round" key={round.round}>
          <div className="trace-round-label">Round {round.round}</div>
          <ol>
            {round.steps.map((step, index) => (
              <Step step={step} key={`${round.round}-${index}`} />
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}
