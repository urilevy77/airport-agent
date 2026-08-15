import { useEffect, useRef } from 'react'
import ChartChips from './ChartChips'
import EmptyState from './EmptyState'
import MessageBubble from './MessageBubble'
import TraceDisclosure from './TraceDisclosure'
import { InlineChart } from '../charts/registry.jsx'

export default function ChatColumn({ messages, charts, traces, selectedChartId,
                                     onSelectChart, status, onPickStarter }) {
  const endRef = useRef(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) },
    [messages.length, status])

  if (!messages.length) {
    return (
      <div className="chat-scroll">
        <EmptyState onPick={onPickStarter || (() => {})} />
      </div>
    )
  }

  return (
    <div className="chat-scroll">
      {messages.map((message) => {
        const own = charts.filter((c) => message.chartIds.includes(c.id))
        return (
          <MessageBubble key={message.id} role={message.role} text={message.text}>
            <ChartChips charts={own} selectedChartId={selectedChartId}
                        onSelectChart={onSelectChart} />
            {/* On narrow screens the side panel is hidden, so charts render here. */}
            {own.map((chart) => (
              <div className="inline-chart" key={chart.id}>
                <InlineChart chart={chart} />
              </div>
            ))}
            <TraceDisclosure trace={(traces || {})[message.id]} />
          </MessageBubble>
        )
      })}
      {status === 'thinking' && (
        <div className="thinking">Still working — querying BTS and measuring…</div>
      )}
      <div ref={endRef} />
    </div>
  )
}
