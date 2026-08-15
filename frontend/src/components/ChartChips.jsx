import { chipLabel } from '../charts/registry'

/**
 * The signals one answer measured. Clicking a chip switches the pane to that
 * turn and jumps to the card — the pane shows every chart of the turn, so the
 * chip is a way IN rather than a filter.
 */
export default function ChartChips({ charts, selectedChartId, onSelectChart }) {
  if (!charts.length) return null

  function pick(id) {
    onSelectChart(id)
    // After the pane has re-rendered for the newly selected turn. On narrow
    // screens the pane is display:none and this is a harmless no-op.
    requestAnimationFrame(() => {
      document.getElementById(`chart-${id}`)?.scrollIntoView({
        behavior: 'smooth', block: 'nearest',
      })
    })
  }

  return (
    <div className="chips">
      {charts.map((chart) => (
        <button
          key={chart.id}
          type="button"
          className={`chip ${chart.id === selectedChartId ? 'active' : ''}`}
          onClick={() => pick(chart.id)}
        >
          {chipLabel(chart)}
        </button>
      ))}
    </div>
  )
}
