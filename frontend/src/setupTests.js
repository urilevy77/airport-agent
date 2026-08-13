import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement scrollIntoView; ChatColumn calls it to keep the
// transcript pinned to the latest message.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// jsdom doesn't implement ResizeObserver either; recharts' ResponsiveContainer
// uses it to size the chart. Tests that mock recharts don't need this, but
// pre-existing tests that render InlineChart with real recharts (e.g.
// ChatColumn.test.jsx) do, since a real chart now sits behind that chip.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}
