import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { InlineChart } from '../charts/registry.jsx'

// Recharts needs real layout maths; jsdom reports zero size, so charts render
// nothing measurable. Stubbing the container gives them a fixed box.
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }) => (
      <div style={{ width: 600, height: 300 }}>{children}</div>
    ),
  }
})

test('congestion chart captions the airport, window and average', () => {
  render(<InlineChart chart={{
    id: 'c1', tool: 'get_congestion', args: { airport: 'JFK' },
    data: { airport: 'JFK', found: true, months: 6, avg_load_factor: 84.2,
            verdict: 'elevated',
            monthly: [{ month: '2025-01', load_factor: 83.1 },
                      { month: '2025-02', load_factor: 85.4 }] },
  }} />)
  expect(screen.getByText(/JFK/)).toBeInTheDocument()
  expect(screen.getByText(/Average 84\.2% — elevated/)).toBeInTheDocument()
})

test('growth chart captions the latest year and the growth rate', () => {
  render(<InlineChart chart={{
    id: 'c2', tool: 'get_growth', args: { airport: 'BOS' },
    data: { airport: 'BOS', found: true, through_year: 2024,
            growth_per_year_pct: 4.3, vs_prepandemic_pct: -2.1,
            yearly: [{ year: 2019, passengers: 21000000 },
                     { year: 2024, passengers: 20500000 }] },
  }} />)
  expect(screen.getByText(/BOS/)).toBeInTheDocument()
  expect(screen.getByText(/\+4.3%/)).toBeInTheDocument()
})

const RANKED = [
  { airport: 'BOS', score: 88.1, verdict: 'STRONG candidate', annual_load_factor: 84.0,
    load_factor_percentile: 92, growth_per_year_pct: 3.1, vs_2019_pct: 1.2 },
  { airport: 'PVD', score: 61.0, verdict: 'moderate', annual_load_factor: 80.0,
    load_factor_percentile: 55, growth_per_year_pct: 0.2, vs_2019_pct: -4.0 },
]

test('candidate chart lists every ranked airport', () => {
  render(<InlineChart chart={{
    id: 'c3', tool: 'get_candidate', args: { airports: ['BOS', 'PVD'] },
    data: { as_of_year: 2025, ranked: RANKED },
  }} />)
  expect(screen.getByText(/2 airports scored 0–100/i)).toBeInTheDocument()
})

test('candidate chart names the population the percentiles are against', () => {
  render(<InlineChart chart={{
    id: 'c3b', tool: 'get_candidate', args: { airports: ['BOS', 'PVD'] },
    data: { as_of_year: 2025, ranked: RANKED,
            population: { airports: 144, min_annual_passengers: 500000 } },
  }} />)
  expect(screen.getByText(/144 US airports carrying at least 0\.5M/i)).toBeInTheDocument()
})

test('find_candidates draws the same ranking chart', () => {
  render(<InlineChart chart={{
    id: 'c3c', tool: 'find_candidates', args: { limit: 10 },
    data: { as_of_year: 2025, ranked: RANKED },
  }} />)
  expect(screen.getByText(/2 airports scored 0–100/i)).toBeInTheDocument()
})

test('a below-floor airport is called small, not missing', () => {
  render(<InlineChart chart={{
    id: 'c3d', tool: 'get_candidate', args: { airports: ['BOS', 'PVD'] },
    data: { as_of_year: 2025, ranked: RANKED, below_investment_floor: ['HII'] },
  }} />)
  expect(screen.getByText(/HII carry too few passengers to suggest/i)).toBeInTheDocument()
})

test('an empty ranking explains itself instead of drawing nothing', () => {
  render(<InlineChart chart={{
    id: 'c3e', tool: 'find_candidates', args: {},
    data: { ranked: [], note: 'No airports could be ranked.' },
  }} />)
  expect(screen.getByText(/No airports could be ranked/i)).toBeInTheDocument()
})

test('traffic mix chart shows the international share', () => {
  render(<InlineChart chart={{
    id: 'c4', tool: 'get_traffic_mix', args: { airport: 'JFK' },
    data: { airport: 'JFK', found: true, months: 6, international_share_pct: 53.2,
            airport_type: 'global gateway', avg_trip_miles: 2653,
            trip_length: 'long-haul' },
  }} />)
  expect(screen.getByText(/53\.2% international over the last 6 months/)).toBeInTheDocument()
  expect(screen.getByText(/global gateway/i)).toBeInTheDocument()
})

test('national rank chart shows the rank out of the field', () => {
  render(<InlineChart chart={{
    id: 'c5', tool: 'get_national_rank', args: { airport: 'PWM' },
    data: { airport: 'PWM', found: true, year: 2024, rank: 95, of_airports: 1311,
            tier: 'mid-size airport', rank_10y_ago: 94 },
  }} />)
  expect(screen.getByText(/95 of 1311/)).toBeInTheDocument()
})

test('a tool error renders as an error box, never an empty chart', () => {
  render(<InlineChart chart={{
    id: 'c6', tool: 'get_congestion', args: { airport: 'NYC' },
    data: { airport: 'NYC', found: false, error: "No BTS data for 'NYC'." },
  }} />)
  expect(screen.getByText(/No BTS data for 'NYC'/)).toBeInTheDocument()
})

test('an unknown tool renders nothing rather than crashing', () => {
  const { container } = render(
    <InlineChart chart={{ id: 'c7', tool: 'get_future_thing', args: {}, data: {} }} />)
  expect(container).toBeEmptyDOMElement()
})
