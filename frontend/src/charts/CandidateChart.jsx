import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer,
         Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame, { ACCENT, AXIS, GRID } from './ChartFrame'

export default function CandidateChart({ data }) {
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
                               + 'but are scored here. ' : '')
             + 'Source: BTS T-100 (r495-tyji).'}
    >
      <ResponsiveContainer width="100%" height={Math.max(160, ranked.length * 46)}>
        <BarChart data={ranked} layout="vertical"
                  margin={{ top: 4, right: 56, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRID} horizontal={false} />
          <XAxis type="number" domain={[Math.floor(floor) - 4, 'dataMax + 2']} tick={AXIS} />
          <YAxis type="category" dataKey="airport" tick={AXIS} width={48} />
          <Tooltip formatter={(v, _n, item) => [`${v} — ${item.payload.verdict}`, 'Score']} />
          <Bar dataKey="score" fill={ACCENT} radius={[0, 3, 3, 0]}>
            <LabelList dataKey="verdict" position="right" style={AXIS} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
