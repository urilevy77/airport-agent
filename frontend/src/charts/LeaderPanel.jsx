import { StatTile as Tile } from '../components/StatRow'

/**
 * The detail behind the top bar: what an analyst needs after "which one".
 *
 * Every value comes from the SAME ranked entry the bar chart is drawn from, so
 * the panel and the ranking can never disagree. Nothing is derived, averaged or
 * re-scaled here — this file only formats.
 */

/** 1287476 -> '1.29M'. Two decimals below 10M, where the digit still matters. */
function millions(pax) {
  const m = pax / 1e6
  return `${m.toFixed(m >= 10 ? 1 : 2)}M`
}

/** 88 -> '88th'. 11-13 are the exception every ordinal helper forgets. */
function ordinal(n) {
  const t = n % 100
  const suffix = t >= 11 && t <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th')
  return `${n}${suffix}`
}

const DASH = '—'
const pct = (v) => (v == null ? DASH : `${v.toFixed(1)}%`)
const signed = (v) => (v == null ? DASH : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`)
/** A missing percentile prints nothing, never a confident 0th. */
const percentileNote = (p) => (p == null ? null : `${ordinal(p)} percentile`)

export default function LeaderPanel({ data }) {
  const top = (data.ranked || [])[0]
  if (!top) return null

  // Scored and ranked, but too small for the question to make sense — the model
  // is told to say so, and the panel must not read as an endorsement without it.
  const belowFloor = (data.below_investment_floor || []).includes(top.airport)
  const year = data.as_of_year

  return (
    <section className="leader" aria-label={`${top.airport} detail`}>
      <header className="leader-head">
        <h4>
          {/* "Top-scoring", not "winner": with one airport named there is no
              contest, and the score ranks candidates rather than rating them. */}
          Top-scoring · <strong>{top.airport}</strong>
          {top.verdict ? <span className="leader-verdict">{top.verdict}</span> : null}
        </h4>
        <div className="leader-score tabular">{top.score} / 100</div>
      </header>

      <div className="leader-grid">
        <Tile
          value={top.passengers == null ? DASH : millions(top.passengers)}
          label="Passengers"
          note={top.passengers == null ? null
            : `${top.passengers.toLocaleString('en-US')} passengers${year ? ` in ${year}` : ''}`}
        />
        <Tile
          value={pct(top.annual_load_factor)}
          label="Load factor"
          note={percentileNote(top.load_factor_percentile)}
        />
        <Tile
          value={signed(top.growth_per_year_pct)}
          label="Growth per year"
          note={percentileNote(top.growth_percentile)}
        />
        <Tile
          value={signed(top.vs_2019_pct)}
          label="vs 2019"
          note={top.vs_2019_pct == null ? null
            : `${top.vs_2019_pct >= 0 ? 'above' : 'below'} pre-pandemic`}
        />
      </div>

      {/* A SENTENCE, deliberately: the raw gap is a rate comparison, and read as
          a level it inverts the meaning. It arrives already interpreted. */}
      {top.demand_vs_seats ? (
        <div className="leader-demand">
          <div className="leader-label">
            Demand vs seats
            {top.demand_percentile == null ? null
              : <span className="leader-note"> · {percentileNote(top.demand_percentile)}</span>}
          </div>
          <p>{top.demand_vs_seats}</p>
        </div>
      ) : null}

      {belowFloor ? (
        <p className="leader-caution">
          {top.airport} is scored and ranked here, but it carries too few passengers
          a year — probably too small for a terminal project to be the right question.
        </p>
      ) : null}
    </section>
  )
}
