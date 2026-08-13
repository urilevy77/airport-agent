// The server is stateless: we send the history we hold and get the new one back.

const COLD_START_MS = 8000   // past this, the free host is probably waking up

export class ChatError extends Error {}

export async function sendChat({ history, question }) {
  let response
  try {
    response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ history, question }),
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
