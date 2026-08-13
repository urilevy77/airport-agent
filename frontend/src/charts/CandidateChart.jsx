import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer,
         Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame, { ACCENT, AXIS, GRID } from './ChartFrame'

export default function CandidateChart({ data }) {
  const ranked = data.ranked || []
  const missing = data.not_found || []
  const floor = Math.min(...ranked.map((r) => r.score), 100)
  return (
    <ChartFrame
      title="Expansion candidates, ranked"
      caption={`${ranked.length} airports ranked by load factor + 3-year growth + unmet `
             + 'demand. The score has no unit — the ordering is the point, and small gaps '
             + 'are noise. '
             + (missing.length ? `No BTS data for ${missing.join(', ')} — excluded, not `
                                 + 'ranked low. ' : '')
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
