import { CartesianGrid, LabelList, Line, LineChart, ReferenceLine,
         ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame from './ChartFrame'
import { MONO, useChartPalette } from './palette'

const millions = (v) => `${(v / 1e6).toFixed(1)}M`

/** One label, on the last point. A number on every dot goes unread. */
function endLabel(lastIndex, fill) {
  return function EndLabel({ x, y, index, value }) {
    if (index !== lastIndex) return null
    return (
      <text x={x} y={y - 12} textAnchor="middle" fill={fill}
            fontSize={11} fontFamily={MONO}>
        {millions(value)}
      </text>
    )
  }
}

export default function GrowthChart({ data }) {
  const p = useChartPalette()
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
                  + `${Math.abs(data.vs_prepandemic_pct)}%.`)}
    >
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={years} margin={{ top: 22, right: 68, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={p.grid} vertical={false} />
          <XAxis dataKey="year" tick={p.tick} tickLine={false}
                 axisLine={{ stroke: p.axisLine }} />
          <YAxis tickFormatter={millions} tick={p.tick} width={52}
                 tickLine={false} axisLine={false} />
          <Tooltip formatter={(v) => [millions(v), 'Passengers']} {...p.tooltip} />
          {prePandemic && (
            <ReferenceLine y={prePandemic.passengers} stroke={p.reference}
                           strokeDasharray="4 3"
                           label={{ value: '2019 level', position: 'right', ...p.tick }} />
          )}
          {/* The 2px ring in the surface color keeps a dot legible where it
              crosses the line or a neighbour. */}
          <Line type="monotone" dataKey="passengers" stroke={p.accent} strokeWidth={2}
                strokeLinecap="round" strokeLinejoin="round"
                dot={{ r: 4, fill: p.accent, stroke: p.surface, strokeWidth: 2 }}
                activeDot={{ r: 6, fill: p.accent, stroke: p.surface, strokeWidth: 2 }}>
            <LabelList content={endLabel(years.length - 1, p.axisText)} />
          </Line>
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
