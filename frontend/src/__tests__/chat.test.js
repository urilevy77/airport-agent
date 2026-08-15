import { afterEach, expect, test, vi } from 'vitest'
import { ChatError, sendChat } from '../api/chat'

// This file exercises the REAL sendChat() against a mocked fetch — it must
// NOT mock '../api/chat'. useChat.test.jsx mocks sendChat itself, so this is
// the only place the actual non-ok-response -> ChatError translation runs.

afterEach(() => { vi.restoreAllMocks() })

function mockFetchOnce(body, ok = true, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok, status, json: async () => body,
  })
}

test('a non-ok response with a body.error surfaces that message', async () => {
  mockFetchOnce({ error: 'RuntimeError: BTS timed out' }, false, 502)

  await expect(sendChat({ history: [], question: 'Is JFK busy?' }))
    .rejects.toEqual(new ChatError('RuntimeError: BTS timed out'))
})

test('a non-ok response with no body.error falls back to a generic status message', async () => {
  mockFetchOnce({}, false, 500)

  await expect(sendChat({ history: [], question: 'Is JFK busy?' }))
    .rejects.toEqual(new ChatError('The server returned an error (500).'))
})
