import { useEffect, useState } from 'react'
import { getPolicies, connectFeed, computeStats, revokeAgent, fleetResume } from './api'
import TopBar from './components/TopBar'
import LiveFeed from './components/LiveFeed'
import AgentCard from './components/AgentCard'
import PolicyDrawer from './components/PolicyDrawer'
import EmergencyStop, { HaltedBanner } from './components/EmergencyStop'

export default function App() {
  const [policies, setPolicies] = useState({ halted: false, agents: {} })
  const [policiesLoaded, setPoliciesLoaded] = useState(false)
  const [events, setEvents] = useState([])
  const [spent, setSpent] = useState({})
  const [connectionStatus, setConnectionStatus] = useState('connecting')
  const [editingAgentId, setEditingAgentId] = useState(null)
  const [haltedAt, setHaltedAt] = useState(null)

  useEffect(() => {
    getPolicies().then((p) => {
      setPolicies(p)
      setPoliciesLoaded(true)
    })
    const ws = connectFeed(
      (evt) => {
        setEvents((prev) => [evt, ...prev].slice(0, 100))
        if (evt.decision === 'allow') {
          setSpent((prev) => ({ ...prev, [evt.agent_id]: (prev[evt.agent_id] || 0) + evt.amount }))
        }
      },
      (status) => setConnectionStatus(status),
    )
    return () => ws.close()
  }, [])

  function handlePolicySaved(agentId, patch) {
    setPolicies((prev) => ({ ...prev, agents: { ...prev.agents, [agentId]: { ...prev.agents[agentId], ...patch } } }))
  }

  async function handleRevoke(agentId, revoked) {
    const updated = await revokeAgent(agentId, revoked)
    setPolicies((prev) => ({
      ...prev,
      agents: { ...prev.agents, [agentId]: { ...prev.agents[agentId], revoked: updated.revoked } },
    }))
  }

  function handleHalt() {
    setPolicies((prev) => ({ ...prev, halted: true }))
    setHaltedAt(Date.now() / 1000)
  }

  async function handleResume() {
    await fleetResume()
    setPolicies((prev) => ({ ...prev, halted: false }))
    setHaltedAt(null)
  }

  const stats = computeStats(events, policies.agents)
  const editingPolicy = editingAgentId ? policies.agents[editingAgentId] : null

  return (
    <div className={`app ${policies.halted ? 'app-halted' : ''}`}>
      <TopBar stats={stats} connectionStatus={connectionStatus} />

      {policies.halted && <HaltedBanner haltedAt={haltedAt} onResume={handleResume} />}

      <div className="estop-dock">
        <EmergencyStop halted={policies.halted} onHalt={handleHalt} />
      </div>

      <main className="console-layout">
        <LiveFeed events={events} connectionStatus={connectionStatus} />

        <aside className="agent-rail" aria-label="Agents">
          {!policiesLoaded && <div className="feed-placeholder">Loading agents…</div>}
          {policiesLoaded &&
            Object.entries(policies.agents).map(([agentId, policy]) => (
              <AgentCard
                key={agentId}
                agentId={agentId}
                policy={policy}
                spent={spent[agentId] || 0}
                onRevoke={handleRevoke}
                onEditPolicy={setEditingAgentId}
              />
            ))}
        </aside>
      </main>

      <footer className="app-footer">All data mocked/synthetic — hackathon prototype</footer>

      {editingAgentId && editingPolicy && (
        <PolicyDrawer
          agentId={editingAgentId}
          policy={editingPolicy}
          onClose={() => setEditingAgentId(null)}
          onSaved={handlePolicySaved}
        />
      )}
    </div>
  )
}
