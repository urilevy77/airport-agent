/**
 * A live recharts plot -> a PNG the document can embed.
 *
 * This works only because charts/palette.js hands recharts literal hex rather
 * than CSS custom properties: the colors are attributes on the elements
 * themselves, so a serialization detached from the page still looks like the
 * page. Webfonts do NOT come along — the axis labels fall back through the
 * stacks in palette.js MONO and theme.css --font, which is a small price for
 * not embedding font binaries in every export.
 *
 * The browser seams (Image, canvas) are injectable so the drawing rules can be
 * tested; jsdom provides neither.
 */

const SVG_NS = 'http://www.w3.org/2000/svg'

/** How long one plot gets to decode before the export moves on without it. */
const DEFAULT_TIMEOUT = 10000

/**
 * The plot as standalone SVG markup, sized to what it measured on screen.
 * Detached from the document it is no longer inline SVG, so it has to declare
 * its own namespace or the browser decodes it as text.
 */
export function svgSource(svg, { width, height }) {
  const clone = svg.cloneNode(true)
  clone.setAttribute('xmlns', SVG_NS)
  clone.setAttribute('width', String(width))
  clone.setAttribute('height', String(height))
  // Without a viewBox the scaled-up canvas crops the plot instead of enlarging it.
  if (!clone.getAttribute('viewBox')) {
    clone.setAttribute('viewBox', `0 0 ${width} ${height}`)
  }
  return new XMLSerializer().serializeToString(clone)
}

const dataUrl = (source) =>
  `data:image/svg+xml;charset=utf-8,${encodeURIComponent(source)}`

function decode(source, { createImage, timeout }) {
  return new Promise((resolve, reject) => {
    const image = createImage()
    const timer = setTimeout(
      () => reject(new Error('The chart took too long to render.')), timeout)
    image.onload = () => { clearTimeout(timer); resolve(image) }
    image.onerror = () => { clearTimeout(timer); reject(new Error('The chart could not be drawn.')) }
    image.src = dataUrl(source)
  })
}

/**
 * @param svg     the live <svg> element
 * @param size    { width, height } as measured on screen
 * @param scale   pixel ratio for the capture; 1x is visibly soft in print
 * @returns a PNG data URL
 */
export async function svgToPng(svg, size, {
  createImage = () => new Image(),
  createCanvas = () => document.createElement('canvas'),
  scale = 2,
  timeout = DEFAULT_TIMEOUT,
} = {}) {
  const image = await decode(svgSource(svg, size), { createImage, timeout })

  const canvas = createCanvas()
  canvas.width = Math.round(size.width * scale)
  canvas.height = Math.round(size.height * scale)

  const context = canvas.getContext('2d')
  // A chart has no background of its own. Left transparent, the PNG shows
  // whatever sits behind it — in Word, often dark axis text on a dark fill.
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.drawImage(image, 0, 0, canvas.width, canvas.height)

  // No external references went into the SVG, so the canvas is not tainted and
  // this cannot throw a security error.
  return canvas.toDataURL('image/png')
}
