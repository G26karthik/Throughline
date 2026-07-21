import { useState } from 'react'
import SpendMeter from './SpendMeter'

export default function AgentCard({ agentId, policy, spent, onRevoke, onEditPolicy }) {
  const [confirming, setConfirming] = useState(false)

  async function handleRevokeClick() {
    if (!confirming) {
      setConfirming(true)
      return
    }
    setConfirming(false)
    await onRevoke(agentId, !policy.revoked)
  }

  return (
    <article className={`agent-card ${policy.revoked ? 'agent-card-revoked' : ''}`}>
      <div className="agent-card-header">
        <h3 className="agent-name mono">{agentId}</h3>
        {policy.revoked && <span className="revoked-tag">REVOKED</span>}
      </div>

      <div className="scope-tags">
        {policy.allowed_actions.map((scope) => (
          <span key={scope} className="scope-tag mono">
            {scope}
          </span>
        ))}
      </div>

      <SpendMeter cap={policy.spend_cap} spent={spent} />

      <div className="agent-card-actions">
        <button type="button" className="btn-link" onClick={() => onEditPolicy(agentId)}>
          Edit policy
        </button>
        <button
          type="button"
          className={confirming ? 'btn-revoke-confirm' : 'btn-revoke'}
          onClick={handleRevokeClick}
          onBlur={() => setConfirming(false)}
        >
          {confirming ? 'Confirm?' : policy.revoked ? 'Un-revoke' : 'Revoke'}
        </button>
      </div>
    </article>
  )
}
