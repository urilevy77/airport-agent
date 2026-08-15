import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import TraceDisclosure from '../components/TraceDisclosure'

const TRACE = {
  id: 't1',
  latency_ms: 4210,
  error: null,
  steps: [
    { kind: 'model', round: 1, ms: 1240, text: '', calls: ['get_congestion'] },
    { kind: 'tool', round: 1, ms: 1810, name: 'get_congestion',
      args: { airport: 'LAX' }, result: { score: 0.81 }, error: null },
    { kind: 'tool', round: 2, ms: 620, name: 'get_growth',
      args: { airport: 'LAX' }, result: { cagr: 3.9 }, error: null },
  ],
}

describe('TraceDisclosure', () => {
  it('summarises signals, rounds and total time', () => {
    render(<TraceDisclosure trace={TRACE} />)
    expect(screen.getByText('2 signals · 2 rounds · 4.2s')).toBeInTheDocument()
  })

  it('is collapsed by default so it never competes with the answer', () => {
    render(<TraceDisclosure trace={TRACE} />)
    const details = screen.getByText('2 signals · 2 rounds · 4.2s').closest('details')
    expect(details.open).toBe(false)
  })

  it('expands to the step list', async () => {
    render(<TraceDisclosure trace={TRACE} />)
    await userEvent.click(screen.getByText('2 signals · 2 rounds · 4.2s'))
    expect(screen.getByText('Round 1')).toBeInTheDocument()
    expect(screen.getByText('get_growth')).toBeInTheDocument()
  })

  it('says so when no tool ran — the finding worth watching for', () => {
    render(<TraceDisclosure trace={{ ...TRACE, steps: [TRACE.steps[0]] }} />)
    expect(screen.getByText(/no signal was measured/i)).toBeInTheDocument()
  })

  it('renders nothing without a trace', () => {
    const { container } = render(<TraceDisclosure trace={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
