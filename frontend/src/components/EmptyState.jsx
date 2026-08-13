const STARTERS = [
  'Which New England airport most needs a terminal expansion?',
  'Is PWM a major airport?',
  'Compare congestion at BOS and JFK',
  'What kind of terminal does JFK need?',
]

export default function EmptyState({ onPick }) {
  return (
    <div className="empty-state">
      <h2>Where would a terminal renovation actually pay off?</h2>
      <p>
        Ask in plain English. Answers come from live BTS T-100 data, and every chart
        shows the numbers actually measured. Delays, gate counts and fares are not in
        this dataset, so those questions get refused rather than guessed.
      </p>
      <div className="starters">
        {STARTERS.map((question) => (
          <button key={question} type="button" className="starter"
                  onClick={() => onPick(question)}>
            {question}
          </button>
        ))}
      </div>
    </div>
  )
}
