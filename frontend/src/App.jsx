import { useState } from 'react'
import ChatColumn from './components/ChatColumn'
import Composer from './components/Composer'
import Header from './components/Header'
import useChat from './hooks/useChat'
import './theme.css'

export default function App() {
  const chat = useChat()
  const [draft, setDraft] = useState('')

  return (
    <div className="app">
      <Header />
      <div className="workspace">
        <div className="chat-pane">
          <ChatColumn
            messages={chat.messages}
            charts={chat.charts}
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
          />
        </div>
        <aside className="chart-pane" />
      </div>
    </div>
  )
}
