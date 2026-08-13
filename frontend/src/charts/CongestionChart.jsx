import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer,
         Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame, { ACCENT, AXIS, GRID } from './ChartFrame'

// Bands from backend/kpis.py: >=85 HIGH, >=80 elevated.
export default function CongestionChart({ data }) {
  const months = data.monthly || []
  return (
    <ChartFrame
      title={`Load factor by month · ${data.airport}`}
      caption={`How full departing flights were over the last ${data.months} months. `
             + `Average ${data.avg_load_factor}% — ${data.verdict}. `
             + `Source: BTS T-100 (r495-tyji).`}
    >
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={months} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="month" tick={AXIS} />
          <YAxis domain={[60, 100]} unit="%" tick={AXIS} width={44} />
          <Tooltip formatter={(v) => [`${v}%`, 'Load factor']} />
          <ReferenceLine y={85} stroke="#b3261e" strokeDasharray="4 3"
                         label={{ value: 'HIGH 85%', position: 'right', ...AXIS }} />
          <ReferenceLine y={80} stroke="#c98a00" strokeDasharray="4 3"
                         label={{ value: 'elevated 80%', position: 'right', ...AXIS }} />
          <Bar dataKey="load_factor" fill={ACCENT} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
