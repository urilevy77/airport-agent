/**
 * The conversation on screen, flattened into the document description POST
 * /export renders.
 *
 * Pure: state in, payload out, no DOM and no fetch — the browser-only work
 * (rendering charts off-screen and rasterizing them) happens in ExportHarness
 * and arrives here as `captures`. Nothing is re-derived: prose comes from the
 * messages, numbers from statsFor(), captions from the chart's own frame. The
 * document can therefore disagree with the screen only if the screen is wrong.
 */
import { chipLabel } from '../charts/registry.jsx'
import { statsFor } from '../charts/stats'

export const DOCUMENT_TITLE = 'Airport Investment Intelligence'

const WHEN = new Intl.DateTimeFormat('en-US',
  { day: 'numeric', month: 'long', year: 'numeric' })

/**
 * A tile as the document wants it: three strings.
 *
 * `tone` is dropped on the way through — it only ever meant a color on the
 * left rule of a tile, and the verdict it tinted is already spelled out in the
 * note beside it (see components/StatRow.jsx).
 */
const flatten = (tiles) => (tiles || []).map(({ label, value, note }) => ({
  label: String(label ?? ''), value: String(value ?? ''), note: String(note ?? ''),
}))

/**
 * One chart card, or null if there is nothing worth a heading.
 *
 * Ranking tools have no statsFor() entry on purpose — LeaderPanel reports those
 * numbers instead, and that panel is HTML beside the plot rather than part of
 * it, so the raster cannot hold it. The harness reads its tiles back out of the
 * DOM and they stand in here.
 */
function chartEntry(chart, captured) {
  const capture = captured || {}
  const stats = flatten(statsFor(chart.tool, chart.data))
  const fallback = flatten(capture.tiles)
  const png = capture.png_b64 || ''
  // Not every chart is an <svg>: TrafficMixChart draws in CSS, so it sends the
  // shares and the document redraws them.
  const bars = capture.bars || []
  const both = stats.length ? stats : fallback

  // A tool that drew nothing AND measured nothing (unregistered, or an error
  // card where the chart should be) would leave a bare heading over blank
  // space. Its failure is already visible in the transcript above.
  if (!png && !bars.length && !both.length) return null

  return {
    title: capture.title || chipLabel(chart),
    caption: capture.caption || '',
    source: capture.source || '',
    stats: both,
    bars,
    png_b64: png,
  }
}

/**
 * @param messages    the display transcript from useChat
 * @param charts      every chart of the conversation, each carrying its own id
 * @param captures    { [chartId]: { title, caption, source, tiles, png_b64 } }
 * @param model       which model answered, for the provenance line
 * @param now         injected so the formatted date is testable
 */
export default function buildExport({ messages = [], charts = [], captures = {},
                                      model = '', now = new Date() } = {}) {
  const byId = new Map(charts.map((chart) => [chart.id, chart]))
  const turns = []

  messages.forEach((message, index) => {
    // Only an answer opens a turn. A 'system' message is an error the user saw
    // in the transcript, not something the agent said — exporting it as an
    // answer would put the agent's name on a network failure. A trailing
    // question with no answer yet has nothing to report.
    if (message.role !== 'agent') return
    const asked = messages[index - 1]

    turns.push({
      question: asked?.role === 'user' ? asked.text : '',
      answer: message.text || '',
      charts: (message.chartIds || [])
        .map((id) => byId.get(id))
        .filter(Boolean)
        .map((chart) => chartEntry(chart, captures[chart.id]))
        .filter(Boolean),
    })
  })

  return {
    title: DOCUMENT_TITLE,
    generated_at: WHEN.format(now),
    model: model || '',
    turns,
  }
}
