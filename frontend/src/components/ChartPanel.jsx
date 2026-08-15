import { InlineChart } from '../charts/registry.jsx'
import { statsFor } from '../charts/stats'
import StatRow from './StatRow'

/** Chart ids are `${answerId}-${index}`, so the prefix IS the turn. */
const turnOf = (id) => String(id || '').split('-')[0]

/**
 * The dashboard for one turn: every signal the agent measured, each card
 * leading with its headline numbers and closing with the chart they came from.
 *
 * Scoped to a single turn on purpose. Stacking every chart of the whole
 * conversation would put a January measurement of BOS beside a July one of JFK
 * with nothing marking them apart.
 */
export default function ChartPanel({ charts, selectedChartId, question }) {
  const turn = turnOf(selectedChartId)
  const shown = charts.filter((chart) => turnOf(chart.id) === turn)

  if (!shown.length) {
    return (
      <p className="chart-empty">
        Charts appear here as the agent measures things. Every one is drawn from the
        numbers behind the answer, never from its wording.
      </p>
    )
  }

  return (
    <>
      <div className="pane-head">
        <span className="eyebrow">Measured this turn</span>
        {question ? <p className="pane-question">{question}</p> : null}
      </div>
      <div className="pane-body">
        {shown.map((chart, index) => (
          <section
            key={chart.id}
            id={`chart-${chart.id}`}
            className={`chart-card${chart.id === selectedChartId ? ' selected' : ''}`}
            style={{ animationDelay: `${index * 60}ms` }}
          >
            <StatRow stats={statsFor(chart.tool, chart.data)} />
            <InlineChart chart={chart} />
          </section>
        ))}
      </div>
    </>
  )
}
