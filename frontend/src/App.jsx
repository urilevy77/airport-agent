import { useEffect, useMemo, useState } from 'react'
import { fetchConfig } from './api/chat'
import ChartPanel from './components/ChartPanel'
import ChatColumn from './components/ChatColumn'
import Composer from './components/Composer'
import Header from './components/Header'
import MicButton from './components/MicButton'
import ModelPicker from './components/ModelPicker'
import TracesPage from './components/TracesPage'
import useChat from './hooks/useChat'
import useExport from './hooks/useExport'
import useSpeech from './hooks/useSpeech'
import { ThemeProvider } from './theme/ThemeContext'
import './theme.css'

// The model allowlist, fetched once at startup — each model carries its OWN
// effort list (some models, e.g. Haiku, take none at all), which is why this
// is `models: [{id, label, efforts}]` rather than one flat effort list shared
// by every model. Never fatal: if /config is unreachable (offline dev server,
// older backend) the picker just doesn't render, and /chat runs on its own
// defaults — same as picking nothing.
function usePickerConfig() {
  const [config, setConfig] = useState({ models: [], defaultModel: '' })
  useEffect(() => {
    let cancelled = false
    fetchConfig()
      .then((cfg) => {
        if (!cancelled) {
          setConfig({ models: cfg.models || [], defaultModel: cfg.default_model || '' })
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])
  return config
}

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

/** The question whose answer produced the selected chart, for the pane header. */
function questionFor(messages, selectedChartId) {
  const turn = String(selectedChartId || '').split('-')[0]
  const answerAt = messages.findIndex((m) => m.id === turn)
  if (answerAt < 1) return ''
  const asked = messages[answerAt - 1]
  return asked?.role === 'user' ? asked.text : ''
}

// The effort the pickers open on, whenever the chosen model offers it. Named
// rather than inlined because two places below have to agree on it.
const PREFERRED_EFFORT = 'medium'

function keyFromHash(hash) {
  const query = hash.indexOf('?')
  if (query === -1) return ''
  return new URLSearchParams(hash.slice(query + 1)).get('key') || ''
}

export default function App() {
  const hash = useHash()
  const chat = useChat()
  const { models, defaultModel } = usePickerConfig()
  const [model, setModel] = useState('')
  const [effort, setEffort] = useState('')
  const [draft, setDraft] = useState('')

  // The effort options for whichever model is ACTUALLY in effect ('' only
  // before /config lands, and it falls back to defaultModel) — never a flat
  // list shared by every model, since e.g. Haiku takes no effort at all.
  const efforts = useMemo(
    () => models.find((m) => m.id === (model || defaultModel))?.efforts ?? [],
    [models, model, defaultModel])

  // The pickers show a real choice rather than a "Default" entry, so the state
  // has to be seeded once the allowlist arrives: the server's own default model
  // (Sonnet), at medium effort.
  useEffect(() => {
    if (!model && defaultModel) setModel(defaultModel)
  }, [model, defaultModel])

  // Reconciles effort with the model in BOTH directions, because the picker no
  // longer has an empty option to fall back on. Leaving Haiku (no efforts) for
  // Sonnet must re-fill it, or the select would sit blank on a value that isn't
  // in its list; moving TO Haiku must clear it, since sending an effort that
  // model rejects is exactly the 400 this picker exists to prevent.
  useEffect(() => {
    if (!efforts.length) {
      if (effort) setEffort('')
    } else if (!efforts.includes(effort)) {
      setEffort(efforts.includes(PREFERRED_EFFORT) ? PREFERRED_EFFORT : efforts[0])
    }
  }, [effort, efforts])
  // Dictation writes into the same draft the user types into, then STOPS.
  // No auto-send: recognition mishears airport codes ("PWM" -> "PW M"), so the
  // user gets one glance to fix it before sending.
  const speech = useSpeech({ onTranscript: setDraft })

  // The model the export names is the one that is actually in effect — `model`
  // is empty until /config lands, and /chat falls back to the same default.
  const exporter = useExport({
    messages: chat.messages, charts: chat.charts, model: model || defaultModel,
  })

  if (hash.startsWith('#traces')) {
    return (
      <ThemeProvider>
        <TracesPage traceKey={keyFromHash(hash)} />
      </ThemeProvider>
    )
  }

  return (
    <ThemeProvider>
    <div className="app">
      <Header
        onNewChat={() => { chat.reset(); setDraft('') }}
        canStartNew={chat.messages.length > 0 && chat.status !== 'thinking'}
        onExport={exporter.run}
        // Not mid-turn: the answer being written would be missing from the
        // document, and the charts are still arriving.
        canExport={exporter.canExport && chat.status !== 'thinking'}
        exporting={exporter.exporting}
        exportError={exporter.error}
      />
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
            onSend={(question) => chat.send(question, { model, effort })}
            disabled={chat.status === 'thinking'}
            status={chat.status}
            value={draft}
            onChange={setDraft}
            settingsSlot={
              <ModelPicker
                models={models}
                efforts={efforts}
                model={model}
                effort={effort}
                onModelChange={setModel}
                onEffortChange={setEffort}
              />
            }
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
          <ChartPanel
            charts={chat.charts}
            selectedChartId={chat.selectedChartId}
            question={questionFor(chat.messages, chat.selectedChartId)}
          />
        </aside>
      </div>
    </div>
    </ThemeProvider>
  )
}
