import { useState } from 'react'
import ChartPanel from './components/ChartPanel'
import ChatColumn from './components/ChatColumn'
import Composer from './components/Composer'
import Header from './components/Header'
import MicButton from './components/MicButton'
import useChat from './hooks/useChat'
import useSpeech from './hooks/useSpeech'
import './theme.css'

export default function App() {
  const chat = useChat()
  const [draft, setDraft] = useState('')
  // Dictation writes into the same draft the user types into, then STOPS.
  // No auto-send: recognition mishears airport codes ("PWM" -> "PW M"), so the
  // user gets one glance to fix it before sending.
  const speech = useSpeech({ onTranscript: setDraft })

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
