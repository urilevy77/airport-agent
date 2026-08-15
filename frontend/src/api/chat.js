// The server is stateless: we send the history we hold and get the new one back.

const COLD_START_MS = 8000   // past this, the free host is probably waking up

export class ChatError extends Error {}

export async function sendChat({ history, question, model, effort }) {
  let response
  try {
    response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // Omit rather than send "": the server treats a present-but-empty
      // string as an unknown model/effort (400), where undefined means "use
      // the default" — the two are not the same thing on the wire.
      body: JSON.stringify({
        history, question,
        ...(model ? { model } : {}),
        ...(effort ? { effort } : {}),
      }),
    })
  } catch {
    throw new ChatError("Couldn't reach the server. Check your connection and try again.")
  }

  let body = {}
  try {
    body = await response.json()
  } catch {
    throw new ChatError('The server sent a response we could not read. Try again.')
  }

  if (!response.ok) {
    throw new ChatError(body.error || `The server returned an error (${response.status}).`)
  }
  return body
}

export { COLD_START_MS }

// { models: [{id, label}, ...], efforts: [str, ...] } — the allowlist /chat
// validates model/effort against. Fetched once at startup rather than
// hardcoded, so the picker can never drift from what the server accepts.
export async function fetchConfig() {
  const response = await fetch('/config')
  if (!response.ok) throw new ChatError(`The server returned an error (${response.status}).`)
  return response.json()
}

// The debug page reads past turns back. The key travels in a header, never in
// the query string: the page takes it from the URL fragment, which browsers do
// not transmit, so it stays out of the server's access logs.
async function readTraces(path, key) {
  const response = await fetch(path, { headers: { 'X-Trace-Key': key } })
  if (!response.ok) {
    throw new ChatError(
      response.status === 404
        ? 'No traces here — check the key in the URL.'
        : `The server returned an error (${response.status}).`)
  }
  return response.json()
}

export function fetchTraces(key, { limit = 50, offset = 0 } = {}) {
  return readTraces(`/api/traces?limit=${limit}&offset=${offset}`, key)
}

export function fetchTrace(key, id) {
  return readTraces(`/api/traces/${encodeURIComponent(id)}`, key)
}
