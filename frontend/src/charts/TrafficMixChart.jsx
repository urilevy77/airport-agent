import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame from './ChartFrame'
import { useChartPalette } from './palette'

export default function TrafficMixChart({ data }) {
  const p = useChartPalette()
  const intl = data.international_share_pct
  const domestic = 100 - intl
  const rows = [{ name: 'Passengers', international: intl, domestic }]
  return (
    <ChartFrame
      title={`Traffic mix · ${data.airport}`}
      caption={`${intl}% international over the last ${data.months} months — a `
             + `${data.airport_type}. Average trip ${data.avg_trip_miles} miles `
             + `(${data.trip_length}), which is what drives dwell time and gate size.`}
    >
      <ResponsiveContainer width="100%" height={72}>
        <BarChart data={rows} layout="vertical" stackOffset="expand"
                  margin={{ top: 8, right: 4, left: 4, bottom: 8 }}>
          <XAxis type="number" hide domain={[0, 100]} />
          <YAxis type="category" dataKey="name" hide />
          <Tooltip formatter={(v, n) => [`${Number(v).toFixed(1)}%`, n]} {...p.tooltip} />
          {/* The 2px stroke in the surface color IS the surface gap that keeps
              the two segments apart — white doing the separating, not a rule. */}
          <Bar dataKey="international" stackId="mix" fill={p.series[0]}
               name="International" stroke={p.surface} strokeWidth={2}
               radius={[4, 0, 0, 4]} />
          <Bar dataKey="domestic" stackId="mix" fill={p.series[1]}
               name="Domestic" stroke={p.surface} strokeWidth={2}
               radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
      {/* Legend and direct labels in one row: two series always get a legend,
          and the swatch beside ink-colored text carries the identity. */}
      <div className="chart-legend tabular">
        <span className="legend-key">
          <i style={{ background: p.series[0] }} aria-hidden="true" />
          International {intl}%
        </span>
        <span className="legend-key">
          <i style={{ background: p.series[1] }} aria-hidden="true" />
          Domestic {domestic.toFixed(1)}%
        </span>
      </div>
    </ChartFrame>
  )
}
