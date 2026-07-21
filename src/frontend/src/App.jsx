import { useEffect, useState } from 'react'
import { getPolicies, connectFeed } from './api'
import LiveFeed from './components/LiveFeed'
import SpendMeter from './components/SpendMeter'
import AgentControls from './components/AgentControls'
import EmergencyStop from './components/EmergencyStop'

export default function App() {
  const [policies, setPolicies] = useState({ halted: false, agents: {} })
  const [events, setEvents] = useState([])
  const [spent, setSpent] = useState({})

  useEffect(() => {
    getPolicies().then(setPolicies)
    const ws = connectFeed((evt) => {
      setEvents((prev) => [evt, ...prev].slice(0, 100))
      if (evt.decision === 'allow') {
        setSpent((prev) => ({ ...prev, [evt.agent_id]: (prev[evt.agent_id] || 0) + evt.amount }))
      }
    })
    return () => ws.close()
  }, [])

  function updateAgentPolicy(agentId, patch) {
    setPolicies((prev) => ({ ...prev, agents: { ...prev.agents, [agentId]: { ...prev.agents[agentId], ...patch } } }))
  }

  return (
    <div className="app">
      <h1>CodeStreet Governance Layer</h1>
      <p className="mock-label">All data mocked/synthetic — hackathon prototype</p>
      <EmergencyStop halted={policies.halted} onToggle={(h) => setPolicies((p) => ({ ...p, halted: h }))} />
      <div className="agent-cards">
        {Object.entries(policies.agents).map(([agentId, policy]) => (
          <div key={agentId} className="agent-card">
            <SpendMeter agentId={agentId} cap={policy.spend_cap} spent={spent[agentId] || 0} />
            <AgentControls agentId={agentId} policy={policy} onUpdate={updateAgentPolicy} />
          </div>
        ))}
      </div>
      <LiveFeed events={events} />
    </div>
  )
}
