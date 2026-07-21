const BASE = 'http://localhost:8000'

export async function getPolicies() {
  const res = await fetch(`${BASE}/policies`)
  return res.json()
}

export async function getAudit(limit = 200) {
  const res = await fetch(`${BASE}/audit?limit=${limit}`)
  return res.json()
}

export async function patchPolicy(agentId, body) {
  const res = await fetch(`${BASE}/policies/${agentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

export async function revokeAgent(agentId, revoked) {
  const path = revoked ? 'revoke' : 'unrevoke'
  const res = await fetch(`${BASE}/agents/${agentId}/${path}`, { method: 'POST' })
  return res.json()
}

export async function fleetHalt() {
  const res = await fetch(`${BASE}/fleet/halt`, { method: 'POST' })
  return res.json()
}

export async function fleetResume() {
  const res = await fetch(`${BASE}/fleet/resume`, { method: 'POST' })
  return res.json()
}

export function connectFeed(onEvent) {
  const ws = new WebSocket('ws://localhost:8000/ws')
  ws.onmessage = (msg) => onEvent(JSON.parse(msg.data))
  return ws
}
