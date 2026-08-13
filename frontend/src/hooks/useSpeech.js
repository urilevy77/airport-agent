import { useCallback, useEffect, useRef, useState } from 'react'

// Chrome/Edge expose it prefixed; Safari added the standard name. Firefox has
// neither, which is why `supported` is part of the contract. Resolved lazily
// (not at module load) so tests can install a mock before rendering the hook.
function getRecognition() {
  return typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : undefined
}

// Keys are the browser's own SpeechRecognitionErrorEvent codes — quoted,
// because they contain hyphens.
const MESSAGES = {
  'not-allowed': 'Microphone blocked — check your browser settings.',
  'service-not-allowed': 'Microphone blocked — check your browser settings.',
  'no-speech': "Didn't catch that — try again.",
  'audio-capture': 'No microphone found.',
}

export default function useSpeech({ onTranscript }) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState(null)
  const recognition = useRef(null)
  const report = useRef(onTranscript)
  report.current = onTranscript

  const supported = Boolean(getRecognition())

  const start = useCallback(() => {
    const Recognition = getRecognition()
    if (!Recognition || recognition.current) return
    setError(null)

    const engine = new Recognition()
    engine.continuous = true        // don't cut off between sentences
    engine.interimResults = true    // stream words as they're heard
    engine.lang = 'en-US'

    engine.onresult = (event) => {
      // Rebuild the whole utterance each time: interim chunks get revised, so
      // appending would duplicate words.
      let text = ''
      for (let i = 0; i < event.results.length; i += 1) {
        text += event.results[i][0].transcript
      }
      report.current?.(text.trim())
    }
    engine.onerror = (event) => {
      setError(MESSAGES[event.error] || 'Speech recognition failed — type instead.')
      setListening(false)
      recognition.current = null
    }
    engine.onend = () => {
      setListening(false)
      recognition.current = null
    }

    recognition.current = engine
    engine.start()
    setListening(true)
  }, [])

  const stop = useCallback(() => {
    recognition.current?.stop()
    recognition.current = null
    setListening(false)
  }, [])

  // Never leave the mic open on unmount.
  useEffect(() => () => { recognition.current?.stop() }, [])

  return { supported, listening, error, start, stop }
}
