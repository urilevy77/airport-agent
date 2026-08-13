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

test('candidate chart lists every ranked airport', () => {
  render(<InlineChart chart={{
    id: 'c3', tool: 'get_candidate', args: { airports: ['BOS', 'PVD'] },
    data: { ranked: [
      { airport: 'BOS', score: 88.1, verdict: 'STRONG candidate', load_factor: 84.0,
        growth_per_year_pct: 3.1, vs_2019_pct: 1.2 },
      { airport: 'PVD', score: 85.3, verdict: 'weak', load_factor: 85.0,
        growth_per_year_pct: 0.2, vs_2019_pct: -4.0 }] },
  }} />)
  expect(screen.getByText(/2 airports ranked/i)).toBeInTheDocument()
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
