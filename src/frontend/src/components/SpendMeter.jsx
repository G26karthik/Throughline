export default function SpendMeter({ agentId, cap, spent }) {
  const pct = cap > 0 ? Math.min(100, (spent / cap) * 100) : 0
  return (
    <div className="spend-meter">
      <div className="spend-meter-label">{agentId}: ${spent.toFixed(2)} / ${cap.toFixed(2)}</div>
      <div className="spend-meter-bar">
        <div className="spend-meter-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
