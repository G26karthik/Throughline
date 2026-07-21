export default function LiveFeed({ events }) {
  return (
    <div className="live-feed">
      <h2>Live Feed</h2>
      <ul>
        {events.map((e, i) => (
          <li key={i} className={e.decision === 'allow' ? 'row-allow' : 'row-block'}>
            <span className="agent">{e.agent_id}</span>
            <span className="action">{e.action_type}</span>
            <span className="amount">${e.amount.toFixed(2)}</span>
            <span className="decision">{e.decision.toUpperCase()}</span>
            <span className="reason">{e.reason}</span>
            <span className="latency">{e.latency_ms.toFixed(2)}ms</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
