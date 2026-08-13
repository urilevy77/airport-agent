export default function MessageBubble({ role, text, children }) {
  return (
    <div className={`bubble-row ${role}`}>
      <div className={`bubble ${role}`}>
        <p>{text}</p>
        {children}
      </div>
    </div>
  )
}
