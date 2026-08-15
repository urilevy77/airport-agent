// Lives in the composer bar, next to the mic, so the choice sits where the
// question is asked rather than in a header the user stops looking at.
//
// model/effort default to '' (not a value in `models`/`efforts`), meaning "let
// the server pick" — the <select>'s first option is always the default, so
// there's no separate placeholder entry to keep in sync with the list.
export default function ModelPicker({ models, efforts, model, effort, onModelChange, onEffortChange }) {
  if (models.length === 0 && efforts.length === 0) return null

  return (
    <div className="model-picker">
      {models.length > 0 && (
        <select
          className="picker-select"
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          aria-label="Model"
          title="Model"
        >
          <option value="">Default model</option>
          {models.map((m) => (
            <option key={m.id} value={m.id}>{m.label}</option>
          ))}
        </select>
      )}
      {efforts.length > 0 && (
        <select
          className="picker-select"
          value={effort}
          onChange={(e) => onEffortChange(e.target.value)}
          aria-label="Effort"
          title="Reasoning effort"
        >
          <option value="">Default effort</option>
          {efforts.map((e) => (
            <option key={e} value={e}>{e}</option>
          ))}
        </select>
      )}
    </div>
  )
}
