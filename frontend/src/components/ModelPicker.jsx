// Lives in the composer bar, next to the mic, so the choice sits where the
// question is asked rather than in a header the user stops looking at.
//
// Every option here is a REAL model/effort id — there is no "Default" entry.
// The selects open on Sonnet and medium (App picks them once /config lands), so
// the control always names what the next turn will actually run on rather than
// deferring to a server default the user can't see.
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
          {efforts.map((e) => (
            <option key={e} value={e}>{e}</option>
          ))}
        </select>
      )}
    </div>
  )
}
