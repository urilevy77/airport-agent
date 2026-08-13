import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import useSpeech from '../hooks/useSpeech'

class FakeRecognition {
  static last = null
  continuous = false
  interimResults = false
  lang = ''
  constructor() { FakeRecognition.last = this; this.started = false }
  start() { this.started = true }
  stop() { this.started = false; this.onend?.() }
  // Test helpers
  emit(transcript, isFinal = false) {
    this.onresult?.({ resultIndex: 0,
      results: [Object.assign([{ transcript }], { isFinal, length: 1 })] })
  }
  fail(error) { this.onerror?.({ error }) }
}

beforeEach(() => { window.SpeechRecognition = FakeRecognition })
afterEach(() => { delete window.SpeechRecognition; vi.restoreAllMocks() })

test('reports unsupported when the browser has no speech recognition', () => {
  delete window.SpeechRecognition
  const { result } = renderHook(() => useSpeech({ onTranscript: () => {} }))
  expect(result.current.supported).toBe(false)
})

test('start begins listening and transcripts stream to onTranscript', () => {
  const onTranscript = vi.fn()
  const { result } = renderHook(() => useSpeech({ onTranscript }))

  act(() => { result.current.start() })
  expect(result.current.listening).toBe(true)

  act(() => { FakeRecognition.last.emit('is jfk busy') })
  expect(onTranscript).toHaveBeenCalledWith('is jfk busy')
})

test('stop ends listening', () => {
  const { result } = renderHook(() => useSpeech({ onTranscript: () => {} }))
  act(() => { result.current.start() })
  act(() => { result.current.stop() })
  expect(result.current.listening).toBe(false)
})

test('a denied microphone surfaces a readable error and stops listening', () => {
  const { result } = renderHook(() => useSpeech({ onTranscript: () => {} }))
  act(() => { result.current.start() })
  act(() => { FakeRecognition.last.fail('not-allowed') })

  expect(result.current.listening).toBe(false)
  expect(result.current.error).toMatch(/microphone/i)
})

test('never auto-sends — it only reports the transcript', () => {
  const onTranscript = vi.fn()
  const { result } = renderHook(() => useSpeech({ onTranscript }))
  act(() => { result.current.start() })
  act(() => { FakeRecognition.last.emit('is jfk busy', true) })
  act(() => { FakeRecognition.last.stop() })
  // The hook exposes no send path at all; the user presses Send.
  expect(result.current.listening).toBe(false)
  expect(Object.keys(result.current)).not.toContain('send')
})
