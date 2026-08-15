/**
 * The current conversation, kept in the browser so a refresh doesn't lose it.
 *
 * Client-side ON PURPOSE. `/chat` is stateless (see server/app.py) — the
 * browser already owns the history it replays each turn, so restoring a
 * conversation needs no backend at all. Putting it in the server's SQLite
 * would mean every visitor's conversation in one shared table with no user
 * identity to scope reads by, which is exactly the privacy property that
 * statelessness buys. That trade only makes sense once there's a login.
 *
 * Not to be confused with server/trace_store.py: that's ops telemetry, one row
 * per turn, capped and key-gated. Different data, different lifetime, different
 * audience.
 *
 * Every access is wrapped: Safari private mode throws on localStorage, and a
 * lost conversation must never take the chat down with it.
 */

export const KEY = 'airport-agent.session'

// How many turns survive when the whole conversation won't fit the quota.
// Charts and llm history both carry full BTS tool payloads, so a long
// conversation can genuinely reach the ~5MB limit.
export const TURNS_KEPT_ON_OVERFLOW = 10

const isShaped = (value) =>
  Boolean(value) && typeof value === 'object' && Array.isArray(value.messages)

/** The saved conversation, or null if there isn't a usable one. */
export function loadSession() {
  let raw
  try {
    raw = window.localStorage.getItem(KEY)
  } catch {
    return null
  }
  if (!raw) return null
  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    return null
  }
  // A payload from an older release, or a key collision. Restoring a half-shape
  // would crash the chat column on first render, so refuse the whole thing.
  if (!isShaped(parsed)) return null
  return {
    messages: parsed.messages,
    charts: Array.isArray(parsed.charts) ? parsed.charts : [],
    traces: parsed.traces && typeof parsed.traces === 'object' ? parsed.traces : {},
    selectedChartId: parsed.selectedChartId ?? null,
    llmHistory: Array.isArray(parsed.llmHistory) ? parsed.llmHistory : [],
  }
}

/**
 * Persist the conversation. Never throws.
 *
 * On a quota failure the newest turns are worth more than the oldest, so the
 * session is trimmed and retried once. If even that won't fit, the stored copy
 * is CLEARED rather than left behind: a stale snapshot would restore a
 * conversation whose llm history no longer matches the messages on screen.
 */
export function saveSession(state) {
  if (write(state)) return
  if (write(keepRecentTurns(state, TURNS_KEPT_ON_OVERFLOW))) return
  clearSession()
}

export function clearSession() {
  try {
    window.localStorage.removeItem(KEY)
  } catch {
    // Nothing left to do — see the module note on private mode.
  }
}

function write(state) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(state))
    return true
  } catch {
    return false
  }
}

/**
 * The last `turns` turns, with charts, traces and llm history cut to match.
 *
 * Both lists are cut on a `user` boundary rather than at a raw offset: a
 * history that starts mid-turn isn't a conversation, and an llm history
 * beginning with an orphaned tool result is what the API 400s on. (The server
 * also strips those in sanitize.py — this just means it never has to.)
 */
function keepRecentTurns(state, turns) {
  const messages = fromNthLastUser(state.messages, turns, (m) => m.role === 'user')
  const traces = state.traces || {}

  const keptChartIds = new Set(messages.flatMap((m) => m.chartIds || []))
  const keptMessageIds = new Set(messages.map((m) => m.id))

  const charts = (state.charts || []).filter((c) => keptChartIds.has(c.id))
  return {
    messages,
    charts,
    traces: Object.fromEntries(
      Object.entries(traces).filter(([id]) => keptMessageIds.has(id))),
    // A selection pointing at a chart the trim dropped would leave the pane
    // asking for something that no longer exists.
    selectedChartId: keptChartIds.has(state.selectedChartId) ? state.selectedChartId : null,
    llmHistory: fromNthLastUser(state.llmHistory || [], turns, (m) => m.role === 'user'),
  }
}

function fromNthLastUser(list, turns, isUser) {
  const starts = list.reduce((at, item, index) => (isUser(item) ? [...at, index] : at), [])
  if (starts.length <= turns) return list
  return list.slice(starts[starts.length - turns])
}
