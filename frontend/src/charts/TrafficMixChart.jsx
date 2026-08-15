import ChartFrame from './ChartFrame'

/**
 * Part-to-whole for exactly two shares, drawn as a CSS proportion bar rather
 * than a Recharts stack.
 *
 * Why not Recharts: this is a one-row, two-segment, no-axis figure — the whole
 * plot is two rectangles. A BarChart brings a ResponsiveContainer, a hidden
 * numeric axis and a stack offset to configure, every one of which is a way for
 * the bar to come out the wrong width (it did: `stackOffset="expand"` rescales
 * the stack to 0..1 while the axis stayed on [0, 100], so the whole bar drew at
 * 1% of the track). Plain elements can't disagree with the numbers, and they
 * read the theme tokens directly, so light/dark needs no parallel hex table.
 *
 * The hues are still the two validated categorical slots from palette.js — see
 * --series-1/--series-2 in theme.css, which mirror them for the CSS layer.
 */
export default function TrafficMixChart({ data }) {
  const intl = data.international_share_pct
  const domestic = 100 - intl

  // A share under ~1.5% is thinner than the 2px surface gap beside it, so at
  // true width it would vanish and read as missing data rather than as "almost
  // none". The floor is a visible hairline, and the direct label below always
  // carries the real number — the label is what's read, the bar is the shape.
  const intlWidth = intl > 0 ? Math.max(intl, 1.5) : 0

  // "a ${airport_type}" doesn't survive both values — "a domestic" and "a
  // international gateway" are each wrong — so the type is named, not articled.
  const caption = `${intl}% of ${data.airport}'s passengers over the last `
    + `${data.months} months flew international routes, which classes it `
    + `${data.airport_type}. Average trip ${data.avg_trip_miles} miles `
    + `(${data.trip_length}), which is what drives dwell time and gate size.`

  return (
    <ChartFrame title={`Traffic mix · ${data.airport}`} caption={caption}>
      <p className="mix-lede">
        Share of passengers, international vs domestic
      </p>
      <div className="mix-bar" role="img"
           aria-label={`International ${intl}% of passengers, `
                     + `domestic ${domestic.toFixed(1)}%`}>
        {intlWidth > 0 && (
          <span className="mix-seg intl" style={{ width: `${intlWidth}%` }} />
        )}
        <span className="mix-seg dom" style={{ width: `${100 - intlWidth}%` }} />
      </div>
      {/* Legend and direct labels in one row: two series always get a legend,
          and the swatch beside ink-colored text carries the identity. */}
      <div className="chart-legend tabular">
        <span className="legend-key">
          <i className="swatch-1" aria-hidden="true" />
          International {intl}%
        </span>
        <span className="legend-key">
          <i className="swatch-2" aria-hidden="true" />
          Domestic {domestic.toFixed(1)}%
        </span>
      </div>
    </ChartFrame>
  )
}
