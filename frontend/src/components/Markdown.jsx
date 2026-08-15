/**
 * The small Markdown subset the agent actually writes, rendered as elements.
 *
 * Deliberately not a Markdown library: the answers are analyst prose, and the
 * only syntax that shows up in them is emphasis, inline code, and the odd list
 * or sub-heading. A parser for that is smaller than the dependency, and it
 * keeps a hard security property — this returns React NODES, never HTML, so
 * there is no `dangerouslySetInnerHTML` for model output to reach. Anything
 * outside the subset (tables, links, blockquotes) falls through as plain text
 * rather than being mangled.
 *
 * Underscore emphasis (`_x_`, `__x__`) is NOT supported, on purpose: the agent
 * names its own tools and fields in prose (`get_traffic_mix`,
 * `international_share_pct`), and every one of those would italicize itself.
 * Asterisks carry emphasis; underscores are always literal.
 */

// `**` before `*` so bold wins over italic; `+?` so the shortest run matches
// and two bold spans in one line don't merge into one.
const INLINE = /(\*\*[\s\S]+?\*\*|`[^`\n]+`|\*[^*\n]+\*)/g

const BULLET = /^\s*[-*]\s+/
const NUMBER = /^\s*\d+[.)]\s+/
const HEADING = /^(#{1,4})\s+(.*)$/

/** Emphasis and code within one line of text. */
function inline(text, key) {
  const out = []
  let last = 0
  let n = 0
  let match
  INLINE.lastIndex = 0
  while ((match = INLINE.exec(text)) !== null) {
    if (match.index > last) out.push(text.slice(last, match.index))
    const token = match[0]
    const id = `${key}i${n++}`
    if (token.startsWith('**')) out.push(<strong key={id}>{token.slice(2, -2)}</strong>)
    else if (token.startsWith('`')) out.push(<code key={id}>{token.slice(1, -1)}</code>)
    else out.push(<em key={id}>{token.slice(1, -1)}</em>)
    last = match.index + token.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

function block(raw, key) {
  const lines = raw.split('\n')

  const heading = lines.length === 1 && HEADING.exec(lines[0])
  if (heading) {
    // One step down from the bubble's own text: these are sub-headings inside
    // an answer, never the page's headings.
    const Tag = `h${Math.min(heading[1].length + 3, 6)}`
    return <Tag key={key} className="md-h">{inline(heading[2], key)}</Tag>
  }

  // A list only when EVERY line is a marker line — otherwise a paragraph that
  // happens to open with a dash would swallow the sentences under it.
  if (lines.every((l) => BULLET.test(l))) {
    return (
      <ul key={key} className="md-list">
        {lines.map((l, i) => <li key={i}>{inline(l.replace(BULLET, ''), `${key}${i}`)}</li>)}
      </ul>
    )
  }
  if (lines.every((l) => NUMBER.test(l))) {
    return (
      <ol key={key} className="md-list">
        {lines.map((l, i) => <li key={i}>{inline(l.replace(NUMBER, ''), `${key}${i}`)}</li>)}
      </ol>
    )
  }

  // Single newlines inside a paragraph are the author's line breaks; `pre-wrap`
  // on .bubble p is what preserves them, so the text goes in unmodified.
  return <p key={key}>{inline(raw, key)}</p>
}

export default function Markdown({ text }) {
  const source = String(text ?? '')
  // A blank line is the block separator, as in Markdown proper.
  const blocks = source.split(/\n{2,}/).filter((b) => b.trim() !== '')
  if (!blocks.length) return null
  // A wrapper, not a fragment: the between-blocks spacing is set with an
  // adjacent-sibling rule, and inside a fragment that rule would also fire on
  // the chart chips and trace disclosure the bubble renders after the text.
  return <div className="md">{blocks.map((b, i) => block(b, `b${i}`))}</div>
}
