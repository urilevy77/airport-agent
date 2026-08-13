import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart,
         Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame, { ACCENT, AXIS, GRID } from './ChartFrame'

// Log scale: rank 95 and rank 1,100 are both "not top 30", and a linear axis
// would squash the entire interesting range into the left edge.
export default function NationalRankChart({ data }) {
  const points = [{ rank: data.rank, y: 1, when: `${data.year} (now)` }]
  if (data.rank_10y_ago) {
    points.push({ rank: data.rank_10y_ago, y: 1, when: `${data.year - 10}` })
  }
  const movement = data.rank_10y_ago
    ? `Was rank ${data.rank_10y_ago} ten years ago.`
    : 'No comparable rank from ten years ago.'
  return (
    <ChartFrame
      title={`National position · ${data.airport}`}
      caption={`Rank ${data.rank} of ${data.of_airports} US airports by passengers in `
             + `${data.year} — a ${data.tier}. ${movement} Log scale. Ranked by total `
             + 'passengers, not BTS enplanements, so treat it as close but unofficial.'}
    >
      <ResponsiveContainer width="100%" height={140}>
        <ScatterChart margin={{ top: 20, right: 20, left: 8, bottom: 12 }}>
          <CartesianGrid stroke={GRID} vertical horizontal={false} />
          <XAxis type="number" dataKey="rank" scale="log"
                 domain={[1, data.of_airports]} allowDataOverflow
                 ticks={[1, 10, 30, 100, 300, 1000]} tick={AXIS}
                 label={{ value: 'National rank (1 = busiest)', position: 'bottom',
                          ...AXIS }} />
          <YAxis type="number" dataKey="y" hide domain={[0, 2]} />
          <Tooltip formatter={(v, n, item) => [`rank ${item.payload.rank}`,
                                               item.payload.when]} />
          <Scatter data={points} fill={ACCENT} shape="circle" />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
