/**
 * Title + chart + caption, so a screenshot of one card stands alone.
 *
 * The provenance line is split out of the caption prose and set in the mono
 * label style: it is the same sentence on every chart, so it should read as
 * chrome rather than as part of the finding.
 */
export default function ChartFrame({ title, caption, source = 'BTS T-100 · r495-tyji',
                                     children }) {
  return (
    <figure className="chart-frame">
      <h3>{title}</h3>
      <div className="chart-body">{children}</div>
      <figcaption>
        {caption}
        {source ? <span className="chart-source">Source: {source}</span> : null}
      </figcaption>
    </figure>
  )
}
