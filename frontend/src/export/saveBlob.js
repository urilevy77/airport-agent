/**
 * Hand a finished file to the browser's download machinery.
 *
 * The server's Content-Disposition names the file, but a fetch() never sees a
 * download — the response arrives as a blob — so the name has to be set again
 * here. Object URLs are released immediately: a long session would otherwise
 * pin every export it produced in memory until the tab closed.
 */
export default function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  // Attached only for the click: some browsers ignore a download on an anchor
  // that was never in the document.
  document.body.appendChild(anchor)
  try {
    anchor.click()
  } finally {
    anchor.remove()
    URL.revokeObjectURL(url)
  }
}
