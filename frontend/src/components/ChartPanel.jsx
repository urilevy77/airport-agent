import { InlineChart } from '../charts/registry.jsx'

export default function ChartPanel({ charts, selectedChartId }) {
  const chart = charts.find((c) => c.id === selectedChartId)
  if (!chart) {
    return (
      <p className="chart-empty">
        Charts appear here as the agent measures things. Every one is drawn from the
        numbers behind the answer, never from its wording.
      </p>
    )
  }
  return <InlineChart chart={chart} />
}
