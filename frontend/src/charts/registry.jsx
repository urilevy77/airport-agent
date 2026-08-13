// One entry per tool. `label` names the signal for the chip.
export const CHART_LABELS = {
  get_congestion: 'Congestion',
  get_growth: 'Growth',
  get_candidate: 'Candidates',
  get_traffic_mix: 'Traffic mix',
  get_national_rank: 'National rank',
}

/** "Congestion · JFK" — the chip text. */
export function chipLabel(chart) {
  const signal = CHART_LABELS[chart.tool] || chart.tool || 'Result'
  const subject = chart.args?.airport
    || (Array.isArray(chart.args?.airports) ? chart.args.airports.join(', ') : '')
  return subject ? `${signal} · ${subject}` : signal
}

// Task 10 replaces this placeholder with real chart components.
export function InlineChart({ chart }) {
  return <div className="chart-placeholder">{chipLabel(chart)}</div>
}
