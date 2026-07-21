import { useState } from 'react'
import { patchPolicy, revokeAgent } from '../api'

export default function AgentControls({ agentId, policy, onUpdate }) {
  const [capInput, setCapInput] = useState(policy.spend_cap)
  const [scopeInput, setScopeInput] = useState('')

  async function handleRevokeToggle() {
    const updated = await revokeAgent(agentId, !policy.revoked)
    onUpdate(agentId, { ...policy, revoked: updated.revoked })
  }

  async function handleCapSubmit(e) {
    e.preventDefault()
    const updated = await patchPolicy(agentId, { spend_cap: parseFloat(capInput) })
    onUpdate(agentId, updated)
  }

  async function handleScopeToggle(e) {
    e.preventDefault()
    if (!scopeInput) return
    const updated = await patchPolicy(agentId, { toggle_action_type: scopeInput })
    onUpdate(agentId, updated)
    setScopeInput('')
  }

  return (
    <div className="agent-controls">
      <button className={policy.revoked ? 'btn-revoked' : 'btn-revoke'} onClick={handleRevokeToggle}>
        {policy.revoked ? 'Un-revoke' : 'Revoke'} {agentId}
      </button>
      <form onSubmit={handleCapSubmit} className="policy-form">
        <label>
          Spend cap
          <input type="number" value={capInput} onChange={(e) => setCapInput(e.target.value)} />
        </label>
        <button type="submit">Update cap</button>
      </form>
      <form onSubmit={handleScopeToggle} className="policy-form">
        <label>
          Toggle scope
          <input type="text" placeholder="e.g. issue_refund" value={scopeInput} onChange={(e) => setScopeInput(e.target.value)} />
        </label>
        <button type="submit">Toggle</button>
      </form>
      <div className="current-scopes">Scopes: {policy.allowed_actions.join(', ')}</div>
    </div>
  )
}
