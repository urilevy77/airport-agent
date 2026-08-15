/**
 * Read one rendered chart card back out of the DOM.
 *
 * The title and caption a chart writes live inside the chart component itself
 * (charts/*.jsx, through ChartFrame), and its LeaderPanel tiles are HTML beside
 * the plot rather than part of it. Reading them from the rendered card is what
 * lets the export carry that text without a second copy of it in JS — a copy is
 * how a document starts disagreeing with the screen.
 */

const text = (node) => (node?.textContent || '').trim()

/** "Source: BTS T-100 · r495-tyji" -> "BTS T-100 · r495-tyji". */
const SOURCE_LABEL = /^Source:\s*/

/**
 * The caption without the provenance line that shares its <figcaption>.
 * Concatenated they read as one sentence ending "...12 months. Source: BTS".
 */
function caption(figure) {
  const node = figure?.querySelector('figcaption')
  if (!node) return ''
  const clone = node.cloneNode(true)
  clone.querySelector('.chart-source')?.remove()
  return text(clone)
}

function tiles(host) {
  return [...host.querySelectorAll('.stat-tile')].map((tile) => ({
    label: text(tile.querySelector('.stat-label')),
    value: text(tile.querySelector('.stat-value')),
    note: text(tile.querySelector('.stat-note')),
  }))
}

/** "rgb(42, 120, 214)" -> "#2a78d6", the form the .docx shading wants. */
function hex(color) {
  const channels = (color.match(/\d+/g) || []).slice(0, 3)
  if (channels.length < 3) return ''
  return `#${channels.map((c) => Number(c).toString(16).padStart(2, '0')).join('')}`
}

/**
 * A part-to-whole bar drawn in CSS rather than SVG (TrafficMixChart), as
 * segments the document can redraw: label, share, color.
 *
 * The widths are taken as drawn, not as measured, so the printed bar matches
 * the one on screen — including the hairline floor that keeps a tiny share
 * visible. The true number rides in the label beside it.
 *
 * Segments and legend keys are paired by position, so a mismatch means the
 * chart dropped a zero-width segment while still legending it. Rather than
 * guess, the bar is skipped: the caption and tiles still carry the numbers.
 */
function bars(host) {
  const segments = [...host.querySelectorAll('.mix-bar .mix-seg')]
  const keys = [...host.querySelectorAll('.chart-legend .legend-key')]
  if (!segments.length || segments.length !== keys.length) return []

  return segments.map((segment, index) => ({
    label: text(keys[index]),
    pct: parseFloat(segment.style.width) || 0,
    color: hex(getComputedStyle(segment).backgroundColor),
  }))
}

/**
 * @param host the element one InlineChart was rendered into
 * @returns { title, caption, source, tiles, svg } — svg is null when the tool
 *   failed and InlineChart drew an error card instead of a chart.
 */
export default function readCard(host) {
  const figure = host.querySelector('.chart-frame')
  return {
    title: text(figure?.querySelector('h3')),
    caption: caption(figure),
    source: text(figure?.querySelector('.chart-source')).replace(SOURCE_LABEL, ''),
    tiles: tiles(host),
    bars: bars(host),
    svg: host.querySelector('svg'),
  }
}
