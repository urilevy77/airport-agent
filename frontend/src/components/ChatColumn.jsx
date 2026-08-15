import { useEffect, useRef } from 'react'
import ChartChips from './ChartChips'
import EmptyState from './EmptyState'
import MessageBubble from './MessageBubble'
import TraceDisclosure from './TraceDisclosure'
import { InlineChart } from '../charts/registry.jsx'

export default function ChatColumn({ messages, charts, traces, selectedChartId,
                                     onSelectChart, status, onPickStarter }) {
  const scrollRef = useRef(null)
  // Scroll the log itself rather than calling scrollIntoView on a sentinel:
  // scrollIntoView walks UP the tree and may animate ancestors too, and it
  // starts its animation against the layout of the frame the new bubble was
  // inserted in. Driving scrollTop on the one element that actually scrolls
  // keeps the animation and its repaints inside this box.
  useEffect(() => {
    const log = scrollRef.current
    if (!log) return
    // Element.scrollTo is absent in jsdom and in older engines, and an
    // exception thrown from an effect during commit takes the whole tree down
    // with it — so the plain assignment is the fallback, not an optimization.
    if (typeof log.scrollTo === 'function') {
      log.scrollTo({ top: log.scrollHeight, behavior: 'smooth' })
    } else {
      log.scrollTop = log.scrollHeight
    }
  }, [messages.length, status])

  if (!messages.length) {
    return (
      <div className="chat-scroll" ref={scrollRef}>
        <EmptyState onPick={onPickStarter || (() => {})} />
      </div>
    )
  }

  return (
    <div className="chat-scroll" ref={scrollRef}>
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
    </div>
  )
}
