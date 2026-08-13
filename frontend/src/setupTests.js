import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement scrollIntoView; ChatColumn calls it to keep the
// transcript pinned to the latest message.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}
