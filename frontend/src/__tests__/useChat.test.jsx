import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import useChat from '../hooks/useChat'
import { sendChat } from '../api/chat'

vi.mock('../api/chat', () => ({
  sendChat: vi.fn(),
  ChatError: class ChatError extends Error {},
}))

afterEach(() => { vi.restoreAllMocks() })

test('sending a question adds the user message then the answer', async () => {
  sendChat.mockResolvedValue({ answer: 'JFK is busy.', charts: [], history: [{ role: 'user', content: 'q' }] })
  const { result } = renderHook(() => useChat())

  await act(async () => { await result.current.send('Is JFK busy?') })

  await waitFor(() => expect(result.current.status).toBe('idle'))
  expect(result.current.messages.map((m) => [m.role, m.text])).toEqual([
    ['user', 'Is JFK busy?'],
    ['agent', 'JFK is busy.'],
  ])
})

test('charts get stable ids and attach to the answer', async () => {
  sendChat.mockResolvedValue({
    answer: 'JFK is busy.',
    charts: [{ tool: 'get_congestion', args: { airport: 'JFK' }, data: { found: true } }],
    history: [],
  })
  const { result } = renderHook(() => useChat())

  await act(async () => { await result.current.send('Is JFK busy?') })

  const answer = result.current.messages.at(-1)
  expect(answer.chartIds).toHaveLength(1)
  expect(result.current.charts[0].id).toBe(answer.chartIds[0])
  // The newest answer's chart is selected automatically.
  expect(result.current.selectedChartId).toBe(answer.chartIds[0])
})

test('a server error becomes a system message and keeps the conversation', async () => {
  const { ChatError } = await import('../api/chat')
  sendChat.mockRejectedValue(new ChatError('RuntimeError: BTS timed out'))
  const { result } = renderHook(() => useChat())

  await act(async () => { await result.current.send('Is JFK busy?') })

  expect(result.current.messages.at(-1).role).toBe('system')
  expect(result.current.messages.at(-1).text).toMatch(/BTS timed out/)
  expect(result.current.status).toBe('idle')
})

test('status is thinking while the request is in flight', async () => {
  let resolve
  sendChat.mockReturnValue(new Promise((r) => { resolve = r }))
  const { result } = renderHook(() => useChat())

  act(() => { result.current.send('Is JFK busy?') })
  await waitFor(() => expect(result.current.status).toBe('thinking'))

  await act(async () => {
    resolve({ answer: 'done', charts: [], history: [] })
  })
  await waitFor(() => expect(result.current.status).toBe('idle'))
})

test('selectChart switches the shown chart', async () => {
  sendChat.mockResolvedValue({
    answer: 'Compared.',
    charts: [
      { tool: 'get_congestion', args: { airport: 'BOS' }, data: {} },
      { tool: 'get_growth', args: { airport: 'JFK' }, data: {} },
    ],
    history: [],
  })
  const { result } = renderHook(() => useChat())
  await act(async () => { await result.current.send('Compare BOS and JFK') })

  const [first, second] = result.current.charts
  expect(result.current.selectedChartId).toBe(first.id)
  act(() => { result.current.selectChart(second.id) })
  expect(result.current.selectedChartId).toBe(second.id)
})

test('keeps the trace keyed by the answer message id', async () => {
  sendChat.mockResolvedValue({
    answer: 'About 81% full.',
    charts: [],
    history: [{ role: 'user', content: 'How congested is SFO?' }],
    trace: { id: 't1', steps: [{ kind: 'tool', name: 'get_congestion' }] },
  })

  const { result } = renderHook(() => useChat())
  await act(async () => { await result.current.send('How congested is SFO?') })

  const answer = result.current.messages.find((m) => m.role === 'agent')
  expect(result.current.traces[answer.id].id).toBe('t1')
})

test('never puts the trace into the history it replays', async () => {
  // llmHistory is re-uploaded every turn and becomes model input. A trace in
  // there would grow quadratically AND let the agent read its own timings.
  sendChat.mockResolvedValue({
    answer: 'About 81% full.',
    charts: [],
    history: [{ role: 'user', content: 'How congested is SFO?' }],
    trace: { id: 't1', steps: [{ kind: 'tool', name: 'get_congestion' }] },
  })

  const { result } = renderHook(() => useChat())
  await act(async () => { await result.current.send('How congested is SFO?') })
  await act(async () => { await result.current.send('and Boston?') })

  const [{ history }] = sendChat.mock.calls[1]
  expect(JSON.stringify(history)).not.toContain('get_congestion')
  expect(history.every((m) => !('trace' in m))).toBe(true)
})
