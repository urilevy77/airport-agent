import { chipLabel } from '../charts/registry'

export default function ChartChips({ charts, selectedChartId, onSelectChart }) {
  if (!charts.length) return null
  return (
    <div className="chips">
      {charts.map((chart) => (
        <button
          key={chart.id}
          type="button"
          className={`chip ${chart.id === selectedChartId ? 'active' : ''}`}
          onClick={() => onSelectChart(chart.id)}
        >
          {chipLabel(chart)}
        </button>
      ))}
    </div>
  )
}
