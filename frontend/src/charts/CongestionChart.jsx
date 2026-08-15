import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer,
         Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame from './ChartFrame'
import { useChartPalette } from './palette'

// Bands from backend/kpis.py: >=85 HIGH, >=80 elevated. The two lines are
// THRESHOLDS, not grid — dashed on purpose, and each carries its own written
// label so the color never has to mean the band on its own.
export default function CongestionChart({ data }) {
  const p = useChartPalette()
  const months = data.monthly || []
  return (
    <ChartFrame
      title={`Load factor by month · ${data.airport}`}
      caption={`How full departing flights were over the last ${data.months} months. `
             + `Average ${data.avg_load_factor}% — ${data.verdict}.`}
    >
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={months} margin={{ top: 8, right: 76, left: 0, bottom: 4 }}>
          <CartesianGrid stroke={p.grid} vertical={false} />
          <XAxis dataKey="month" tick={p.tick} tickLine={false}
                 axisLine={{ stroke: p.axisLine }} />
          <YAxis domain={[60, 100]} unit="%" tick={p.tick} width={46}
                 tickLine={false} axisLine={false} />
          <Tooltip formatter={(v) => [`${v}%`, 'Load factor']} {...p.tooltip} />
          <ReferenceLine y={85} stroke={p.critical} strokeDasharray="4 3"
                         label={{ value: 'HIGH 85%', position: 'right', ...p.tick }} />
          <ReferenceLine y={80} stroke={p.warning} strokeDasharray="4 3"
                         label={{ value: 'elevated 80%', position: 'right', ...p.tick }} />
          <Bar dataKey="load_factor" fill={p.accent} radius={[4, 4, 0, 0]} maxBarSize={24} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
