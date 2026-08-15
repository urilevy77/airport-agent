/**
 * The headline numbers a tool result leads with, as stat tiles.
 *
 * Pure: a tool name and its result in, an array of tiles out. Every value is
 * READ from the tool's own output — nothing is derived, re-scaled or averaged
 * here, so a tile can never disagree with the chart drawn beside it. Same rule
 * as server/charts.py: the answer text is never an input.
 *
 * A tile is { label, value, note?, tone? }. A metric the tool could not compute
 * drops its tile entirely rather than printing a confident zero.
 */

const pct = (v) => `${v.toFixed(1)}%`
const signedPct = (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
const signed = (v) => `${v >= 0 ? '+' : ''}${v}`
const commas = (v) => v.toLocaleString('en-US')

/** Drops any tile whose value came back null/undefined. */
const kept = (tiles) => tiles.filter((t) => t !== null)
const tile = (value, rest) => (value == null ? null : { value, ...rest })

// Bands from backend/kpis.py: >=85 HIGH, >=80 elevated. The verdict is the
// tool's own word, so the tone follows it rather than re-deriving the band.
function congestionTone(verdict) {
  if (!verdict) return undefined
  if (verdict.includes('HIGH')) return 'critical'
  if (verdict.includes('elevated')) return 'warning'
  return undefined
}

const BUILDERS = {
  get_congestion: (d) => kept([
    tile(d.avg_load_factor == null ? null : pct(d.avg_load_factor), {
      label: 'Average load factor', note: d.verdict, tone: congestionTone(d.verdict),
    }),
    tile(d.peak_load_factor == null ? null : pct(d.peak_load_factor), {
      label: 'Peak', note: d.peak_month,
    }),
    tile(d.months == null ? null : `${d.months} mo`, { label: 'Window', note: 'of data' }),
  ]),

  get_growth: (d) => kept([
    tile(d.growth_per_year_pct == null ? null : signedPct(d.growth_per_year_pct), {
      label: 'Growth per year', note: 'average, recent years',
    }),
    tile(d.vs_prepandemic_pct == null ? null : signedPct(d.vs_prepandemic_pct), {
      label: 'vs 2019',
      note: `${d.vs_prepandemic_pct >= 0 ? 'above' : 'below'} pre-pandemic`,
    }),
    tile(d.passengers_latest_year, {
      label: 'Passengers',
      note: d.through_year == null ? undefined : `in ${d.through_year}`,
    }),
  ]),

  get_national_rank: (d) => kept([
    tile(d.rank == null ? null : `#${d.rank}`, {
      label: 'National rank',
      note: d.of_airports == null ? undefined : `of ${commas(d.of_airports)} US airports`,
    }),
    tile(d.tier, { label: 'Tier' }),
    tile(d.places_moved_10y == null ? null : signed(d.places_moved_10y), {
      label: '10-year move', note: d.direction,
    }),
  ]),

  // The share and the type are two facts, not one: "0.3% / International /
  // domestic" reads as a contradiction when the type is stacked under the share
  // as its note, so the type gets its own tile and the share says what it is a
  // share OF.
  get_traffic_mix: (d) => kept([
    tile(d.international_share_pct == null ? null : pct(d.international_share_pct), {
      label: 'International', note: 'of passengers',
    }),
    tile(d.airport_type, { label: 'Airport type' }),
    tile(d.avg_trip_miles == null ? null : `${commas(d.avg_trip_miles)} mi`, {
      label: 'Average trip', note: d.trip_length,
    }),
  ]),

  // find_candidates / get_candidate deliberately absent: LeaderPanel already
  // reports the same numbers in more depth, directly under the ranking bars.
}

export function statsFor(tool, data) {
  if (typeof data !== 'object' || data === null) return []
  if (data.error || data.found === false) return []
  return (BUILDERS[tool] || (() => []))(data)
}
