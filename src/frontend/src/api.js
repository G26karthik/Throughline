const BASE = 'http://localhost:8000'
const WS_URL = 'ws://localhost:8000/ws'
const RECONNECT_DELAY_MS = 2000

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
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `PATCH /policies/${agentId} failed (${res.status})`)
  }
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

// Connects to the decision feed with auto-reconnect. onStatus receives
// "connecting" | "connected" | "disconnected" so the UI can show a state
// that's visibly different from the normal feed, not just silently retry.
export function connectFeed(onEvent, onStatus) {
  let ws = null
  let reconnectTimer = null
  let closedByCaller = false

  function open() {
    onStatus('connecting')
    ws = new WebSocket(WS_URL)
    ws.onopen = () => onStatus('connected')
    ws.onmessage = (msg) => onEvent(JSON.parse(msg.data))
    ws.onclose = () => {
      onStatus('disconnected')
      if (!closedByCaller) {
        reconnectTimer = setTimeout(open, RECONNECT_DELAY_MS)
      }
    }
    ws.onerror = () => ws.close()
  }

  open()

  return {
    close() {
      closedByCaller = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (ws) ws.close()
    },
  }
}

// Client-side rollups from the feed buffer, feeding the top-bar stat cards.
export function computeStats(events, agents) {
  const totalAgents = Object.keys(agents).length
  const activeAgents = Object.values(agents).filter((p) => !p.revoked).length

  const windowStart = Date.now() / 1000 - 60
  const recentCount = events.filter((e) => e.ts >= windowStart).length

  const blocks = events.filter((e) => e.decision === 'block').length
  const blockRate = events.length > 0 ? (blocks / events.length) * 100 : 0

  const avgLatency =
    events.length > 0 ? events.reduce((sum, e) => sum + e.latency_ms, 0) / events.length : 0

  return {
    activeAgents,
    totalAgents,
    actionsPerMin: recentCount,
    blockRatePct: blockRate,
    avgLatencyMs: avgLatency,
  }
}
