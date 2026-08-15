import { useEffect, useState } from 'react'
import ChartPanel from './components/ChartPanel'
import ChatColumn from './components/ChatColumn'
import Composer from './components/Composer'
import Header from './components/Header'
import MicButton from './components/MicButton'
import TracesPage from './components/TracesPage'
import useChat from './hooks/useChat'
import useSpeech from './hooks/useSpeech'
import './theme.css'

// A hash route, not a real one, and not a router dependency. FastAPI serves the
// build through StaticFiles(html=True), which does NOT fall back to index.html
// for unknown paths — so /traces would 404 on refresh without a server-side
// catch-all. The fragment buys a second property worth having: browsers never
// transmit it, so a key pasted into /#traces?key=... stays out of the server's
// access logs.
function useHash() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return hash
}

function keyFromHash(hash) {
  const query = hash.indexOf('?')
  if (query === -1) return ''
  return new URLSearchParams(hash.slice(query + 1)).get('key') || ''
}

export default function App() {
  const hash = useHash()
  const chat = useChat()
  const [draft, setDraft] = useState('')
  // Dictation writes into the same draft the user types into, then STOPS.
  // No auto-send: recognition mishears airport codes ("PWM" -> "PW M"), so the
  // user gets one glance to fix it before sending.
  const speech = useSpeech({ onTranscript: setDraft })

  if (hash.startsWith('#traces')) return <TracesPage traceKey={keyFromHash(hash)} />

  return (
    <div className="app">
      <Header />
      <div className="workspace">
        <div className="chat-pane">
          <ChatColumn
            messages={chat.messages}
            charts={chat.charts}
            traces={chat.traces}
            selectedChartId={chat.selectedChartId}
            onSelectChart={chat.selectChart}
            status={chat.status}
            onPickStarter={setDraft}
          />
          <Composer
            onSend={chat.send}
            disabled={chat.status === 'thinking'}
            status={chat.status}
            value={draft}
            onChange={setDraft}
            micSlot={
              <MicButton
                supported={speech.supported}
                listening={speech.listening}
                error={speech.error}
                onStart={speech.start}
                onStop={speech.stop}
              />
            }
          />
        </div>
        <aside className="chart-pane">
          <ChartPanel charts={chat.charts} selectedChartId={chat.selectedChartId} />
        </aside>
      </div>
    </div>
  )
}
