import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import ChartFrame, { ACCENT, AXIS } from './ChartFrame'

const DOMESTIC = '#9db8cb'

export default function TrafficMixChart({ data }) {
  const intl = data.international_share_pct
  const rows = [{ name: 'Passengers', international: intl, domestic: 100 - intl }]
  return (
    <ChartFrame
      title={`Traffic mix · ${data.airport}`}
      caption={`${intl}% international over the last ${data.months} months — a `
             + `${data.airport_type}. Average trip ${data.avg_trip_miles} miles `
             + `(${data.trip_length}), which is what drives dwell time and gate size. `
             + 'Source: BTS T-100 (r495-tyji).'}
    >
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={rows} layout="vertical" stackOffset="expand"
                  margin={{ top: 8, right: 8, left: 4, bottom: 8 }}>
          <XAxis type="number" hide domain={[0, 100]} />
          <YAxis type="category" dataKey="name" hide />
          <Tooltip formatter={(v, n) => [`${Number(v).toFixed(1)}%`, n]} />
          <Bar dataKey="international" stackId="mix" fill={ACCENT} name="International" />
          <Bar dataKey="domestic" stackId="mix" fill={DOMESTIC} name="Domestic" />
        </BarChart>
      </ResponsiveContainer>
      <p className="chart-note tabular" style={AXIS}>
        International {intl}% · Domestic {(100 - intl).toFixed(1)}%
      </p>
    </ChartFrame>
  )
}
