import { useState } from 'react'

export default function Composer({ onSend, disabled, status, micSlot, value, onChange }) {
  const [internal, setInternal] = useState('')
  // Controlled when a parent supplies `value` (voice dictation writes into it).
  const text = value !== undefined ? value : internal
  const setText = onChange || setInternal

  function submit(event) {
    event?.preventDefault()
    if (!text.trim() || disabled) return
    onSend(text.trim())
    setText('')
  }

  return (
    <form className="composer" onSubmit={submit}>
      {micSlot}
      <input
        type="text"
        className="composer-input"
        placeholder="Ask about any US airport…"
        value={text}
        disabled={disabled}
        onChange={(event) => setText(event.target.value)}
        aria-label="Ask a question"
      />
      <button type="submit" className="send" disabled={disabled || !text.trim()}>
        Send
      </button>
      {status === 'thinking' && <span className="composer-status">working…</span>}
    </form>
  )
}
