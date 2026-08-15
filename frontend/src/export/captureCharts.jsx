/**
 * Render every chart of a conversation off-screen and photograph each one.
 *
 * The pane only ever mounts the SELECTED chart (components/ChartPanel.jsx), so
 * there is nothing on screen to capture for the rest of the conversation. This
 * mounts them all into a detached sheet at a fixed print width, in light theme,
 * long enough to be photographed, then tears the sheet back down.
 *
 * Deliberately thin: the two decisions worth testing live in readCard.js (what
 * text a card carries) and rasterize.js (how a plot becomes a PNG). What is
 * left here — mount, wait, unmount — needs a real browser to mean anything, and
 * is verified by running the app.
 */
import { createRoot } from 'react-dom/client'
import { InlineChart } from '../charts/registry.jsx'
import { ThemeOverride } from '../theme/ThemeContext'
import readCard from './readCard'
import { svgToPng } from './rasterize'

/** Matches the 6in text column the document lays a plot into. */
export const SHEET_WIDTH = 720

/** A long conversation would otherwise post tens of megabytes of base64. */
export const MAX_CHARTS = 40

/**
 * Recharts animates bars and lines in over ~1.5s. Photographed early, the
 * export is a document full of half-grown bars.
 */
const SETTLE_MS = 1700

/** A chart whose height we could not measure — an error card, most likely. */
const FALLBACK_HEIGHT = 300

function Sheet({ charts, width }) {
  return (
    <ThemeOverride theme="light">
      {charts.map((chart) => (
        <div key={chart.id} data-chart-id={chart.id} style={{ width }}>
          <InlineChart chart={chart} />
        </div>
      ))}
    </ThemeOverride>
  )
}

/**
 * The sheet has to be laid out for recharts to size anything, so it is moved
 * off-screen rather than hidden: `display: none` and `visibility: hidden` both
 * give every element a zero box, and ResponsiveContainer would render nothing.
 */
function openSheet(width) {
  const host = document.createElement('div')
  host.setAttribute('aria-hidden', 'true')
  Object.assign(host.style, {
    position: 'fixed', top: '0', left: '-99999px',
    width: `${width}px`, background: '#ffffff', pointerEvents: 'none',
  })
  document.body.appendChild(host)
  return host
}

async function photograph(card, width) {
  if (!card.svg) return ''
  const box = card.svg.getBoundingClientRect()
  try {
    return await svgToPng(card.svg, {
      width: Math.round(box.width) || width,
      height: Math.round(box.height) || FALLBACK_HEIGHT,
    })
  } catch {
    // One plot that would not draw costs its picture, not the export. The
    // card's title and numbers still reach the document.
    return ''
  }
}

/**
 * @returns { [chartId]: { title, caption, source, tiles, png_b64 } }
 */
export default async function captureCharts(charts, {
  width = SHEET_WIDTH, settle = SETTLE_MS, max = MAX_CHARTS } = {}) {
  const subject = (charts || []).slice(0, max)
  if (!subject.length) return {}

  const host = openSheet(width)
  const root = createRoot(host)
  try {
    root.render(<Sheet charts={subject} width={width} />)
    await new Promise((done) => setTimeout(done, settle))

    const captures = {}
    for (const chart of subject) {
      const element = host.querySelector(`[data-chart-id="${CSS.escape(chart.id)}"]`)
      if (!element) continue
      const card = readCard(element)
      captures[chart.id] = {
        title: card.title,
        caption: card.caption,
        source: card.source,
        tiles: card.tiles,
        bars: card.bars,
        // eslint-disable-next-line no-await-in-loop -- sequential on purpose:
        // forty plots decoded at once is a memory spike on a modest machine.
        png_b64: await photograph(card, width),
      }
    }
    return captures
  } finally {
    root.unmount()
    host.remove()
  }
}
