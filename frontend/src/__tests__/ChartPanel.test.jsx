import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import ChartPanel from '../components/ChartPanel'

vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }) => (
      <div style={{ width: 600, height: 300 }}>{children}</div>
    ),
  }
})

const charts = [
  { id: 'a', tool: 'get_congestion', args: { airport: 'JFK' },
    data: { airport: 'JFK', found: true, months: 6, avg_load_factor: 84.2,
            verdict: 'elevated', monthly: [{ month: '2025-01', load_factor: 83.1 }] } },
  { id: 'b', tool: 'get_national_rank', args: { airport: 'PWM' },
    data: { airport: 'PWM', found: true, year: 2024, rank: 95, of_airports: 1311,
            tier: 'mid-size airport', rank_10y_ago: 94 } },
]

test('prompts when nothing is selected', () => {
  render(<ChartPanel charts={[]} selectedChartId={null} />)
  expect(screen.getByText(/charts appear here/i)).toBeInTheDocument()
})

test('shows only the selected chart', () => {
  render(<ChartPanel charts={charts} selectedChartId="b" />)
  expect(screen.getByText(/95 of 1311/)).toBeInTheDocument()
  expect(screen.queryByText(/84.2%/)).not.toBeInTheDocument()
})
