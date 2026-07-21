import { fleetHalt, fleetResume } from '../api'

export default function EmergencyStop({ halted, onToggle }) {
  async function handleClick() {
    const result = halted ? await fleetResume() : await fleetHalt()
    onToggle(result.halted)
  }

  return (
    <button className={halted ? 'btn-estop-active' : 'btn-estop'} onClick={handleClick}>
      {halted ? 'RESUME FLEET' : 'EMERGENCY STOP — HALT FLEET'}
    </button>
  )
}
