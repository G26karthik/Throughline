export default function SpendMeter({ cap, spent }) {
  const pct = cap > 0 ? Math.min(100, (spent / cap) * 100) : 0
  const nearCap = pct >= 80

  return (
    <div className="spend-meter">
      <div className="spend-meter-row">
        <span className="spend-meter-amount mono">
          ${spent.toFixed(2)} <span className="muted">/ ${cap.toFixed(2)}</span>
        </span>
        <span className="spend-meter-pct mono muted">{pct.toFixed(0)}%</span>
      </div>
      <div
        className="spend-meter-bar"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Spend against cap"
      >
        <div
          className={`spend-meter-fill ${nearCap ? 'spend-meter-fill-warn' : ''}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
