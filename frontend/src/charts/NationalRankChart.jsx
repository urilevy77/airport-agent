import { CartesianGrid, LabelList, ResponsiveContainer, Scatter, ScatterChart,
         Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame from './ChartFrame'
import { useChartPalette } from './palette'

// Log scale: rank 95 and rank 1,100 are both "not top 30", and a linear axis
// would squash the entire interesting range into the left edge.
export default function NationalRankChart({ data }) {
  const p = useChartPalette()
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
      <ResponsiveContainer width="100%" height={130}>
        <ScatterChart margin={{ top: 26, right: 24, left: 8, bottom: 16 }}>
          <CartesianGrid stroke={p.grid} vertical horizontal={false} />
          <XAxis type="number" dataKey="rank" scale="log"
                 domain={[1, data.of_airports]} allowDataOverflow
                 ticks={[1, 10, 30, 100, 300, 1000]} tick={p.tick}
                 tickLine={false} axisLine={{ stroke: p.axisLine }}
                 label={{ value: 'National rank (1 = busiest)', position: 'bottom',
                          ...p.tick }} />
          <YAxis type="number" dataKey="y" hide domain={[0, 2]} />
          <Tooltip formatter={(v, n, item) => [`rank ${item.payload.rank}`,
                                               item.payload.when]} {...p.tooltip} />
          {/* Two points only, so both get labelled directly — the reader should
              never have to hover to tell "now" from "ten years ago". */}
          <Scatter data={points} fill={p.accent} shape="circle" r={5}
                   stroke={p.surface} strokeWidth={2}>
            <LabelList dataKey="when" position="top" offset={10} style={p.tick} />
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
