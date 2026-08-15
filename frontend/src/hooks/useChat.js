import { useCallback, useEffect, useRef, useState } from 'react'
import { sendChat } from '../api/chat'
import { clearSession, loadSession, saveSession } from '../session'

let counter = 0
const nextId = () => `m${++counter}`

// A restored conversation carries ids the counter knows nothing about — it
// restarts at 0 on every page load — so without this the first new message
// after a refresh would be handed an id an existing one already owns, and the
// two would collide in React keys, chart lookups and the trace map alike.
function advanceCounterPast(messages) {
  for (const message of messages) {
    const n = Number(String(message?.id || '').slice(1))
    if (Number.isFinite(n) && n > counter) counter = n
  }
}

// Read once per mount, not per render: this is what the lazy useState
// initializers below restore from, so the conversation is on screen in the
// first paint rather than flashing empty and filling in.
function restored() {
  const session = loadSession()
  if (session) advanceCounterPast(session.messages)
  return session
}

export default function useChat() {
  const initial = useRef(restored()).current
  const [messages, setMessages] = useState(() => initial?.messages ?? [])
  const [charts, setCharts] = useState(() => initial?.charts ?? [])
  const [traces, setTraces] = useState(() => initial?.traces ?? {})
  const [selectedChartId, setSelectedChartId] = useState(() => initial?.selectedChartId ?? null)
  // Never restored: a refresh mid-turn has no request left in flight, so the
  // only honest state to come back in is idle.
  const [status, setStatus] = useState('idle')

  // The model's message list, kept OUT of React state on purpose: it is not
  // rendered, and it must never be confused with the display messages above.
  const llmHistory = useRef(initial?.llmHistory ?? [])
  const lastQuestion = useRef('')
  const lastOptions = useRef({})

  // Write-through, so a refresh keeps whatever was on screen. Fires only at
  // turn boundaries — nothing here changes mid-request — so it needs no
  // debounce. An empty conversation clears rather than stores: New Chat has to
  // survive the refresh too, and it would otherwise be re-saved as {} the
  // instant after reset() wiped it.
  useEffect(() => {
    if (!messages.length) clearSession()
    else saveSession({ messages, charts, traces, selectedChartId, llmHistory: llmHistory.current })
  }, [messages, charts, traces, selectedChartId])

  const send = useCallback(async (question, options = {}) => {
    const text = question.trim()
    if (!text || status === 'thinking') return

    lastQuestion.current = text
    lastOptions.current = options
    setMessages((prior) => [...prior, { id: nextId(), role: 'user', text, chartIds: [] }])
    setStatus('thinking')

    try {
      const body = await sendChat({
        history: llmHistory.current, question: text,
        model: options.model, effort: options.effort,
      })
      llmHistory.current = body.history || []

      const answerId = nextId()
      const fresh = (body.charts || []).map((chart, index) => ({
        ...chart, id: `${answerId}-${index}`,
      }))
      setCharts((prior) => [...prior, ...fresh])
      // Deliberately NOT in llmHistory: that ref is replayed to the server every
      // turn, so a trace in there would be re-uploaded on every message and would
      // become model input — the agent reading its own timings back.
      if (body.trace) setTraces((prior) => ({ ...prior, [answerId]: body.trace }))
      setMessages((prior) => [...prior, {
        id: answerId, role: 'agent', text: body.answer,
        chartIds: fresh.map((c) => c.id),
      }])
      if (fresh.length) setSelectedChartId(fresh[0].id)
    } catch (error) {
      // The history is untouched, so the conversation survives a failed turn.
      setMessages((prior) => [...prior, {
        id: nextId(), role: 'system', text: error.message, chartIds: [],
      }])
    } finally {
      setStatus('idle')
    }
  }, [status])

  const retry = useCallback(() => send(lastQuestion.current, lastOptions.current), [send])
  const selectChart = useCallback((id) => setSelectedChartId(id), [])

  // New Chat. There is nothing to tell the server: /chat is stateless, so an
  // empty llmHistory IS a new conversation. Clearing storage here as well as
  // in the effect above means a reset is durable even if the component
  // unmounts before the effect runs.
  const reset = useCallback(() => {
    llmHistory.current = []
    lastQuestion.current = ''
    setMessages([])
    setCharts([])
    setTraces({})
    setSelectedChartId(null)
    setStatus('idle')
    clearSession()
  }, [])

  return { messages, charts, traces, selectedChartId, status, error: null,
           send, selectChart, retry, reset }
}
