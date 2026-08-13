import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import ChatColumn from '../components/ChatColumn'

const messages = [
  { id: 'm1', role: 'user', text: 'Is JFK busy?', chartIds: [] },
  { id: 'm2', role: 'agent', text: 'JFK averaged 84%.', chartIds: ['m2-0'] },
]
const charts = [{ id: 'm2-0', tool: 'get_congestion', args: { airport: 'JFK' }, data: {} }]

test('renders user and agent messages', () => {
  render(<ChatColumn messages={messages} charts={charts} selectedChartId="m2-0"
                     onSelectChart={() => {}} status="idle" />)
  expect(screen.getByText('Is JFK busy?')).toBeInTheDocument()
  expect(screen.getByText('JFK averaged 84%.')).toBeInTheDocument()
})

test('a chart chip names the signal and the airport, and is clickable', async () => {
  const onSelectChart = vi.fn()
  render(<ChatColumn messages={messages} charts={charts} selectedChartId={null}
                     onSelectChart={onSelectChart} status="idle" />)

  const chip = screen.getByRole('button', { name: /Congestion · JFK/i })
  await userEvent.click(chip)
  expect(onSelectChart).toHaveBeenCalledWith('m2-0')
})

test('shows what is running while thinking', () => {
  render(<ChatColumn messages={messages} charts={charts} selectedChartId={null}
                     onSelectChart={() => {}} status="thinking" />)
  expect(screen.getByText(/working/i)).toBeInTheDocument()
})

test('an empty conversation offers starter questions', () => {
  render(<ChatColumn messages={[]} charts={[]} selectedChartId={null}
                     onSelectChart={() => {}} status="idle" />)
  expect(screen.getByRole('button', { name: /Is PWM a major airport/i })).toBeInTheDocument()
})
