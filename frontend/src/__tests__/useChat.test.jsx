import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import useChat from '../hooks/useChat'

afterEach(() => { vi.restoreAllMocks() })

function mockFetchOnce(body, ok = true, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok, status, json: async () => body,
  })
}

test('sending a question adds the user message then the answer', async () => {
  mockFetchOnce({ answer: 'JFK is busy.', charts: [], history: [{ role: 'user', content: 'q' }] })
  const { result } = renderHook(() => useChat())

  await act(async () => { await result.current.send('Is JFK busy?') })

  await waitFor(() => expect(result.current.status).toBe('idle'))
  expect(result.current.messages.map((m) => [m.role, m.text])).toEqual([
    ['user', 'Is JFK busy?'],
    ['agent', 'JFK is busy.'],
  ])
})

test('charts get stable ids and attach to the answer', async () => {
  mockFetchOnce({
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
  mockFetchOnce({ error: 'RuntimeError: BTS timed out' }, false, 502)
  const { result } = renderHook(() => useChat())

  await act(async () => { await result.current.send('Is JFK busy?') })

  expect(result.current.messages.at(-1).role).toBe('system')
  expect(result.current.messages.at(-1).text).toMatch(/BTS timed out/)
  expect(result.current.status).toBe('idle')
})

test('status is thinking while the request is in flight', async () => {
  let resolve
  global.fetch = vi.fn().mockReturnValue(new Promise((r) => { resolve = r }))
  const { result } = renderHook(() => useChat())

  act(() => { result.current.send('Is JFK busy?') })
  await waitFor(() => expect(result.current.status).toBe('thinking'))

  await act(async () => {
    resolve({ ok: true, status: 200, json: async () => ({ answer: 'done', charts: [], history: [] }) })
  })
  await waitFor(() => expect(result.current.status).toBe('idle'))
})

test('selectChart switches the shown chart', async () => {
  mockFetchOnce({
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
