import { useEffect, useRef, useState } from 'react'
import { patchPolicy } from '../api'

function useEscapeKey(onEscape) {
  useEffect(() => {
    function handler(e) {
      if (e.key === 'Escape') onEscape()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onEscape])
}

export default function PolicyDrawer({ agentId, policy, onClose, onSaved }) {
  const [capInput, setCapInput] = useState(String(policy.spend_cap))
  const [capState, setCapState] = useState({ status: 'idle', message: '' })
  const [scopeInput, setScopeInput] = useState('')
  const [scopeState, setScopeState] = useState({ status: 'idle', message: '' })
  const closeButtonRef = useRef(null)

  useEscapeKey(onClose)

  useEffect(() => {
    closeButtonRef.current?.focus()
  }, [])

  async function handleCapSubmit(e) {
    e.preventDefault()
    const value = Number(capInput)
    if (!Number.isFinite(value) || value <= 0) {
      setCapState({ status: 'error', message: 'Spend cap must be a number greater than 0.' })
      return
    }
    setCapState({ status: 'saving', message: '' })
    try {
      const updated = await patchPolicy(agentId, { spend_cap: value })
      onSaved(agentId, updated)
      setCapState({ status: 'success', message: `Saved. New cap: $${value.toFixed(2)}.` })
    } catch (err) {
      setCapState({ status: 'error', message: err.message || 'Save failed.' })
    }
  }

  async function handleScopeSubmit(e) {
    e.preventDefault()
    const value = scopeInput.trim()
    if (!value) {
      setScopeState({ status: 'error', message: 'Enter an action type to toggle, e.g. issue_refund.' })
      return
    }
    setScopeState({ status: 'saving', message: '' })
    try {
      const updated = await patchPolicy(agentId, { toggle_action_type: value })
      onSaved(agentId, updated)
      const nowAllowed = updated.allowed_actions.includes(value)
      setScopeState({
        status: 'success',
        message: nowAllowed ? `"${value}" added to scope.` : `"${value}" removed from scope.`,
      })
      setScopeInput('')
    } catch (err) {
      setScopeState({ status: 'error', message: err.message || 'Save failed.' })
    }
  }

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-header">
          <h2 id="drawer-title" className="mono">
            Edit policy — {agentId}
          </h2>
          <button ref={closeButtonRef} type="button" className="btn-icon" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <form className="drawer-form" onSubmit={handleCapSubmit}>
          <label htmlFor="cap-input">Spend cap</label>
          <div className="drawer-form-row">
            <input
              id="cap-input"
              type="number"
              min="0.01"
              step="0.01"
              value={capInput}
              onChange={(e) => setCapInput(e.target.value)}
              aria-invalid={capState.status === 'error'}
            />
            <button type="submit" disabled={capState.status === 'saving'}>
              {capState.status === 'saving' ? 'Saving…' : 'Save cap'}
            </button>
          </div>
          {capState.status === 'error' && <p className="form-feedback form-feedback-error">{capState.message}</p>}
          {capState.status === 'success' && (
            <p className="form-feedback form-feedback-success">{capState.message}</p>
          )}
        </form>

        <form className="drawer-form" onSubmit={handleScopeSubmit}>
          <label htmlFor="scope-input">Toggle permission scope</label>
          <div className="drawer-form-row">
            <input
              id="scope-input"
              type="text"
              placeholder="e.g. issue_refund"
              value={scopeInput}
              onChange={(e) => setScopeInput(e.target.value)}
              aria-invalid={scopeState.status === 'error'}
            />
            <button type="submit" disabled={scopeState.status === 'saving'}>
              {scopeState.status === 'saving' ? 'Saving…' : 'Toggle'}
            </button>
          </div>
          {scopeState.status === 'error' && (
            <p className="form-feedback form-feedback-error">{scopeState.message}</p>
          )}
          {scopeState.status === 'success' && (
            <p className="form-feedback form-feedback-success">{scopeState.message}</p>
          )}
        </form>

        <div className="drawer-current-scopes">
          <span className="muted">Current scope:</span>
          <div className="scope-tags">
            {policy.allowed_actions.map((scope) => (
              <span key={scope} className="scope-tag mono">
                {scope}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
