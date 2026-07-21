function StatCard({ label, value, suffix }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {suffix && <span className="stat-suffix">{suffix}</span>}
      </div>
    </div>
  )
}

export default function TopBar({ stats, connectionStatus }) {
  return (
    <header className="top-bar">
      <div className="top-bar-title">
        <span className="system-name">Governance Console</span>
        <span className={`connection-pill connection-${connectionStatus}`}>
          <span className="connection-dot" />
          {connectionStatus === 'connected' && 'live'}
          {connectionStatus === 'connecting' && 'connecting'}
          {connectionStatus === 'disconnected' && 'reconnecting'}
        </span>
      </div>
      <div className="stat-cards">
        <StatCard label="Agents active" value={`${stats.activeAgents}/${stats.totalAgents}`} />
        <StatCard label="Actions / min" value={stats.actionsPerMin} />
        <StatCard label="Block rate" value={stats.blockRatePct.toFixed(1)} suffix="%" />
        <StatCard label="Avg decision latency" value={stats.avgLatencyMs.toFixed(3)} suffix="ms" />
      </div>
    </header>
  )
}
