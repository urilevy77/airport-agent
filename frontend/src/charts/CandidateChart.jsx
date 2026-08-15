import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer,
         Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame from './ChartFrame'
import LeaderPanel from './LeaderPanel'
import { useChartPalette } from './palette'

export default function CandidateChart({ data }) {
  const p = useChartPalette()
  const ranked = data.ranked || []
  const missing = data.not_found || []
  const small = data.below_investment_floor || []
  const pop = data.population || {}
  const floor = Math.min(...ranked.map((r) => r.score), 100)
  return (
    <ChartFrame
      title="Expansion candidates, ranked"
      caption={`${ranked.length} airports scored 0–100 on how full they are (40%), how `
             + 'fast they are growing (30%) and whether demand is outrunning the seats '
             + 'airlines add (30%). Each is a percentile'
             + (pop.airports ? ` against the ${pop.airports} US airports carrying at `
                               + `least ${(pop.min_annual_passengers / 1e6).toFixed(1)}M `
                               + `passengers in ${data.as_of_year}` : ' against US airports')
             + ', so the score ranks candidates — it is not a rating or a forecast, and '
             + 'small gaps are noise. '
             + (missing.length ? `No BTS data for ${missing.join(', ')} — excluded, not `
                                 + 'ranked low. ' : '')
             + (small.length ? `${small.join(', ')} carry too few passengers to suggest, `
                               + 'but are scored here.' : '')}
    >
      <ResponsiveContainer width="100%" height={Math.max(160, ranked.length * 44)}>
        <BarChart data={ranked} layout="vertical"
                  margin={{ top: 4, right: 128, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={p.grid} horizontal={false} />
          <XAxis type="number" domain={[Math.floor(floor) - 4, 'dataMax + 2']}
                 tick={p.tick} tickLine={false} axisLine={{ stroke: p.axisLine }} />
          <YAxis type="category" dataKey="airport" tick={p.tick} width={48}
                 tickLine={false} axisLine={false} />
          <Tooltip formatter={(v, _n, item) => [`${v} — ${item.payload.verdict}`, 'Score']}
                   {...p.tooltip} />
          {/* One series, so one color for every bar: shading by rank would
              double-encode the length the bar already shows. The verdict rides
              the tip as a text label, in ink rather than the bar's color. */}
          <Bar dataKey="score" fill={p.accent} radius={[0, 4, 4, 0]} maxBarSize={24}>
            <LabelList dataKey="verdict" position="right" style={p.tick} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <LeaderPanel data={data} />
    </ChartFrame>
  )
}
