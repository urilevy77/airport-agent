export default function MicButton({ supported, listening, error, onStart, onStop }) {
  // Hidden entirely where the browser can't do it — typing always works.
  if (!supported) return null

  return (
    <div className="mic-wrap">
      <button
        type="button"
        className={`mic ${listening ? 'listening' : ''}`}
        onClick={listening ? onStop : onStart}
        aria-label={listening ? 'Stop dictation' : 'Dictate a question'}
        title={listening ? 'Stop dictation' : 'Dictate a question'}
      >
        {listening ? '■' : '🎤'}
      </button>
      {error && <span className="mic-error">{error}</span>}
    </div>
  )
}
