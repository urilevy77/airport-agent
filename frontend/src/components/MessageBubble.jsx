import Markdown from './Markdown'

export default function MessageBubble({ role, text, children }) {
  return (
    <div className={`bubble-row ${role}`}>
      <div className={`bubble ${role}`}>
        <Markdown text={text} />
        {children}
      </div>
    </div>
  )
}
