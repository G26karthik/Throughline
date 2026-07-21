import { useRef, useState } from 'react'
import { fleetHalt } from '../api'

const HOLD_MS = 900

export default function EmergencyStop({ halted, onHalt }) {
  const [holding, setHolding] = useState(false)
  const timerRef = useRef(null)

  function startHold() {
    if (halted) return
    setHolding(true)
    timerRef.current = setTimeout(async () => {
      setHolding(false)
      const result = await fleetHalt()
      onHalt(result.halted)
    }, HOLD_MS)
  }

  function cancelHold() {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    setHolding(false)
  }

  if (halted) {
    // The persistent HaltedBanner is the single source of truth for "you are
    // halted, here's how to resume" - this dock stays quiet so it doesn't
    // compete with that banner.
    return <span className="estop-dock-halted mono">HALTED</span>
  }

  return (
    <button
      type="button"
      className={`btn-estop ${holding ? 'btn-estop-holding' : ''}`}
      onPointerDown={startHold}
      onPointerUp={cancelHold}
      onPointerLeave={cancelHold}
      style={{ '--hold-duration': `${HOLD_MS}ms` }}
    >
      <span className="btn-estop-fill" />
      <span className="btn-estop-label">
        {holding ? 'Keep holding…' : 'Hold to halt fleet'}
      </span>
    </button>
  )
}

export function HaltedBanner({ haltedAt, onResume }) {
  const time = haltedAt ? new Date(haltedAt * 1000).toLocaleTimeString('en-US', { hour12: false }) : ''
  return (
    <div className="halted-banner" role="alert">
      <span className="halted-banner-text">
        FLEET HALTED — all agent actions blocked <span className="mono muted">since {time}</span>
      </span>
      <button type="button" className="btn-resume" onClick={onResume}>
        Resume fleet
      </button>
    </div>
  )
}
