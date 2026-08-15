import { useCallback, useRef, useState } from 'react'
import { sendChat } from '../api/chat'

let counter = 0
const nextId = () => `m${++counter}`

export default function useChat() {
  const [messages, setMessages] = useState([])
  const [charts, setCharts] = useState([])
  const [traces, setTraces] = useState({})
  const [selectedChartId, setSelectedChartId] = useState(null)
  const [status, setStatus] = useState('idle')

  // The model's message list, kept OUT of React state on purpose: it is not
  // rendered, and it must never be confused with the display messages above.
  const llmHistory = useRef([])
  const lastQuestion = useRef('')

  const send = useCallback(async (question) => {
    const text = question.trim()
    if (!text || status === 'thinking') return

    lastQuestion.current = text
    setMessages((prior) => [...prior, { id: nextId(), role: 'user', text, chartIds: [] }])
    setStatus('thinking')

    try {
      const body = await sendChat({ history: llmHistory.current, question: text })
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

  const retry = useCallback(() => send(lastQuestion.current), [send])
  const selectChart = useCallback((id) => setSelectedChartId(id), [])

  return { messages, charts, traces, selectedChartId, status, error: null, send, selectChart, retry }
}
