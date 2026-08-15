import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TracesPage from '../components/TracesPage'
import { fetchTrace, fetchTraces } from '../api/chat'

vi.mock('../api/chat', () => ({
  fetchTraces: vi.fn(),
  fetchTrace: vi.fn(),
}))

const SUMMARIES = {
  traces: [
    { id: 't2', ts: '2026-08-15T12:00:00.000Z', question: 'Is LAX growing?',
      answer: 'Yes, 3.9% a year.', latency_ms: 4210, error: null, step_count: 2 },
    { id: 't1', ts: '2026-08-15T11:00:00.000Z', question: 'How congested is SFO?',
      answer: 'About 81% full.', latency_ms: 3050, error: null, step_count: 2 },
  ],
}

describe('TracesPage', () => {
  beforeEach(() => {
    fetchTraces.mockReset()
    fetchTrace.mockReset()
  })

  it('lists past turns newest first', async () => {
    fetchTraces.mockResolvedValue(SUMMARIES)
    render(<TracesPage traceKey="s3cret" />)

    await waitFor(() => expect(screen.getByText('Is LAX growing?')).toBeInTheDocument())
    expect(screen.getByText('How congested is SFO?')).toBeInTheDocument()
    expect(fetchTraces).toHaveBeenCalledWith('s3cret', { limit: 50, offset: 0 })
  })

  it('loads one turn in full when a row is opened', async () => {
    fetchTraces.mockResolvedValue(SUMMARIES)
    fetchTrace.mockResolvedValue({
      id: 't2', latency_ms: 4210, error: null,
      steps: [{ kind: 'tool', round: 1, ms: 1810, name: 'get_growth',
                args: { airport: 'LAX' }, result: { cagr: 3.9 }, error: null }],
    })
    render(<TracesPage traceKey="s3cret" />)

    await waitFor(() => expect(screen.getByText('Is LAX growing?')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Is LAX growing?'))

    await waitFor(() => expect(screen.getByText('get_growth')).toBeInTheDocument())
    expect(fetchTrace).toHaveBeenCalledWith('s3cret', 't2')
  })

  it('explains a rejected key instead of showing an empty list', async () => {
    fetchTraces.mockRejectedValue(new Error('No traces here — check the key in the URL.'))
    render(<TracesPage traceKey="wrong" />)

    await waitFor(() =>
      expect(screen.getByText(/check the key in the URL/)).toBeInTheDocument())
  })

  it('asks for a key when the URL has none', async () => {
    render(<TracesPage traceKey="" />)

    expect(screen.getByText(/add \?key=/i)).toBeInTheDocument()
    expect(fetchTraces).not.toHaveBeenCalled()
  })
})
