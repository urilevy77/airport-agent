import { useCallback, useMemo, useState } from 'react'
import { ChatError, exportDocx } from '../api/chat'
import buildExport from '../export/buildExport'
import captureCharts from '../export/captureCharts'
import saveBlob from '../export/saveBlob'

/**
 * The Export button's whole job: photograph the charts, describe the
 * conversation, post it, save what comes back.
 *
 * Not a tool the agent can call. Assembling the document is deterministic work
 * — the same category as the scoring — and putting it behind the model would
 * let it re-author content it should only be reporting.
 */

const stamp = (now) => now.toISOString().slice(0, 10)

/** Matches the name server/app.py puts in Content-Disposition. */
const filenameFor = (now) => `airport-intelligence-${stamp(now)}.docx`

export default function useExport({ messages = [], charts = [], model = '' } = {}) {
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState(null)

  // An answer is the smallest thing worth a document. Before one exists the
  // button would produce a title page and nothing else.
  const canExport = useMemo(
    () => messages.some((message) => message.role === 'agent'), [messages])

  const run = useCallback(async () => {
    setExporting(true)
    setError(null)
    try {
      // Before the payload is built, not after: buildExport() folds the
      // captures in, so posting first would send a document with every plot
      // missing.
      const captures = await captureCharts(charts)
      const now = new Date()
      const blob = await exportDocx(buildExport({ messages, charts, captures, model, now }))
      saveBlob(blob, filenameFor(now))
    } catch (thrown) {
      // A ChatError already carries a sentence meant for a person. Anything
      // else is a browser fault (no canvas, blocked download) and would
      // otherwise put a stack-trace phrase in the UI.
      setError(thrown instanceof ChatError ? thrown.message
        : 'The conversation could not be exported. Try again, or use a different browser.')
    } finally {
      setExporting(false)
    }
  }, [messages, charts, model])

  return { canExport, exporting, error, run }
}
