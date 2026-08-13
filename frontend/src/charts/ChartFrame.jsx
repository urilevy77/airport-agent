/** Title + chart + caption. The caption makes a screenshot stand alone. */
export default function ChartFrame({ title, caption, children }) {
  return (
    <figure className="chart-frame">
      <h3>{title}</h3>
      <div className="chart-body">{children}</div>
      <figcaption className="tabular">{caption}</figcaption>
    </figure>
  )
}

export const AXIS = { fontSize: 11, fill: '#5c6672' }
export const ACCENT = '#1f5f8b'
export const GRID = '#e3e6ea'
