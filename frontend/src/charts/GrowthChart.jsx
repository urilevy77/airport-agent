import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer,
         Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame, { ACCENT, AXIS, GRID } from './ChartFrame'

const millions = (v) => `${(v / 1e6).toFixed(1)}M`

export default function GrowthChart({ data }) {
  const years = data.yearly || []
  const prePandemic = years.find((y) => y.year === 2019)
  const rate = data.growth_per_year_pct
  return (
    <ChartFrame
      title={`Passengers by year · ${data.airport}`}
      caption={`Complete years only, through ${data.through_year}. `
             + (rate == null ? '' : `Average growth ${rate >= 0 ? '+' : ''}${rate}% per year. `)
             + (data.vs_prepandemic_pct == null ? ''
                : `${data.vs_prepandemic_pct >= 0 ? 'Above' : 'Below'} its 2019 level by `
                  + `${Math.abs(data.vs_prepandemic_pct)}%. `)
             + 'Source: BTS T-100 (r495-tyji).'}
    >
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={years} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="year" tick={AXIS} />
          <YAxis tickFormatter={millions} tick={AXIS} width={52} />
          <Tooltip formatter={(v) => [millions(v), 'Passengers']} />
          {prePandemic && (
            <ReferenceLine y={prePandemic.passengers} stroke="#5c6672" strokeDasharray="4 3"
                           label={{ value: '2019 level', position: 'right', ...AXIS }} />
          )}
          <Line type="monotone" dataKey="passengers" stroke={ACCENT} strokeWidth={2}
                dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
