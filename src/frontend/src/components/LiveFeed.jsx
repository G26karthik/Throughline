function VerdictBadge({ decision }) {
  return <span className={`verdict-badge verdict-${decision}`}>{decision.toUpperCase()}</span>
}

function formatTime(ts) {
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0')
}

export default function LiveFeed({ events, connectionStatus }) {
  if (connectionStatus === 'connecting') {
    return (
      <section className="feed-panel" aria-label="Live decision feed">
        <h2 className="panel-title">Live decision feed</h2>
        <div className="feed-placeholder">Connecting to gateway…</div>
      </section>
    )
  }

  return (
    <section className="feed-panel" aria-label="Live decision feed">
      <h2 className="panel-title">
        Live decision feed
        {connectionStatus === 'disconnected' && (
          <span className="feed-reconnecting">reconnecting…</span>
        )}
      </h2>
      <div className={`feed-table-wrap ${connectionStatus === 'disconnected' ? 'feed-stale' : ''}`}>
        {events.length === 0 ? (
          <div className="feed-placeholder">
            No actions yet. Mock agents will begin submitting actions to the policy gateway shortly.
          </div>
        ) : (
          <table className="feed-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Agent</th>
                <th>Action</th>
                <th className="col-amount">Amount</th>
                <th>Verdict</th>
                <th>Reason</th>
                <th className="col-amount">Latency</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={`${e.ts}-${i}`} className="feed-row">
                  <td className="mono muted">{formatTime(e.ts)}</td>
                  <td className="mono">{e.agent_id}</td>
                  <td className="mono">{e.action_type}</td>
                  <td className="mono col-amount">${e.amount.toFixed(2)}</td>
                  <td>
                    <VerdictBadge decision={e.decision} />
                  </td>
                  <td className="reason-cell">{e.reason}</td>
                  <td className="mono col-amount muted">{e.latency_ms.toFixed(3)}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
