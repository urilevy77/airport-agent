import CandidateChart from './CandidateChart'
import CongestionChart from './CongestionChart'
import GrowthChart from './GrowthChart'
import NationalRankChart from './NationalRankChart'
import TrafficMixChart from './TrafficMixChart'

// One entry per tool. Adding a signal means adding one entry here and one file.
export const CHART_REGISTRY = {
  get_congestion: { label: 'Congestion', Component: CongestionChart },
  get_growth: { label: 'Growth', Component: GrowthChart },
  get_candidate: { label: 'Candidates', Component: CandidateChart },
  get_traffic_mix: { label: 'Traffic mix', Component: TrafficMixChart },
  get_national_rank: { label: 'National rank', Component: NationalRankChart },
}

export const CHART_LABELS = Object.fromEntries(
  Object.entries(CHART_REGISTRY).map(([tool, { label }]) => [tool, label]))

/** "Congestion · JFK" — the chip text. */
export function chipLabel(chart) {
  const signal = CHART_LABELS[chart.tool] || chart.tool || 'Result'
  const subject = chart.args?.airport
    || (Array.isArray(chart.args?.airports) ? chart.args.airports.join(', ') : '')
  return subject ? `${signal} · ${subject}` : signal
}

/** A tool entry -> its chart, or the tool's own error. Never a partial chart. */
export function InlineChart({ chart }) {
  const entry = CHART_REGISTRY[chart.tool]
  if (!entry) return null

  const { data } = chart
  if (typeof data !== 'object' || data === null) {
    return <div className="chart-error">{String(data)}</div>
  }
  if (data.error || data.found === false) {
    return <div className="chart-error">{data.error || 'No data for this airport.'}</div>
  }
  // A ranking has no `found` flag; an empty one has nothing to draw.
  if (chart.tool === 'get_candidate' && !(data.ranked || []).length) {
    return <div className="chart-error">{data.note || 'No airports could be ranked.'}</div>
  }

  const { Component } = entry
  return <Component data={data} args={chart.args} />
}
