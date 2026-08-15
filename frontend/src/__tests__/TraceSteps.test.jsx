import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import TraceSteps from '../components/TraceSteps'

const STEPS = [
  { kind: 'model', round: 1, ms: 1240, text: '', calls: ['get_congestion'] },
  { kind: 'tool', round: 1, ms: 1810, name: 'get_congestion',
    args: { airport: 'SFO' }, result: { load_factor: 80.9 }, error: null },
  { kind: 'tool', round: 2, ms: 620, name: 'get_growth',
    args: { airport: 'JFK' }, result: null, error: 'RuntimeError: BTS is down' },
]

describe('TraceSteps', () => {
  it('groups steps by round', () => {
    render(<TraceSteps steps={STEPS} />)
    expect(screen.getByText('Round 1')).toBeInTheDocument()
    expect(screen.getByText('Round 2')).toBeInTheDocument()
  })

  it('names each tool with its arguments and duration', () => {
    render(<TraceSteps steps={STEPS} />)
    expect(screen.getByText('get_congestion')).toBeInTheDocument()
    expect(screen.getByText('airport=SFO')).toBeInTheDocument()
    expect(screen.getByText('1.8s')).toBeInTheDocument()
  })

  it('labels the model step by how long the model took', () => {
    render(<TraceSteps steps={STEPS} />)
    expect(screen.getByText('model')).toBeInTheDocument()
    expect(screen.getByText('1.2s')).toBeInTheDocument()
  })

  it('marks a failed step with its error', () => {
    render(<TraceSteps steps={STEPS} />)
    expect(screen.getByText('RuntimeError: BTS is down')).toBeInTheDocument()
  })

  it('hides the raw payload behind a second toggle', async () => {
    render(<TraceSteps steps={STEPS} />)
    // jsdom does not apply the UA stylesheet that hides non-summary <details>
    // children when closed, and testing-library's text queries don't filter
    // by CSS visibility — so check the <details> element's own `open` state
    // rather than DOM presence/absence of the raw text.
    const raw = screen.getByText('raw').closest('details')
    expect(raw.open).toBe(false)

    await userEvent.click(screen.getByText('raw'))
    expect(raw.open).toBe(true)
    expect(screen.getByText(/load_factor/)).toBeInTheDocument()
  })

  it('renders nothing for an empty step list', () => {
    const { container } = render(<TraceSteps steps={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
