import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.backend.agents import all_scripted_actions
from src.backend.audit import AuditLog, get_connection
from src.backend.gateway import Action, PolicyGateway
from src.backend.recovery import Recovery


class ActionIn(BaseModel):
    agent_id: str
    action_type: str
    amount: float = 0.0
    target_account: str = ""


class PolicyPatch(BaseModel):
    spend_cap: Optional[float] = None
    toggle_action_type: Optional[str] = None


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)


def create_app(db_path: str = "governance.db") -> FastAPI:
    app = FastAPI(title="CodeStreet Governance Layer")
    conn = get_connection(db_path)
    audit = AuditLog(conn)
    gateway = PolicyGateway()
    recovery = Recovery(gateway, audit)
    manager = ConnectionManager()

    async def broadcast_decision(action: Action, decision):
        await manager.broadcast({
            "type": "decision",
            "agent_id": action.agent_id,
            "action_type": action.action_type,
            "amount": action.amount,
            "target_account": action.target_account,
            "decision": "allow" if decision.allowed else "block",
            "reason": decision.reason,
            "latency_ms": decision.latency_ms,
            "ts": time.time(),
        })

    @app.post("/actions")
    async def post_action(payload: ActionIn):
        action = Action(payload.agent_id, payload.action_type, payload.amount, payload.target_account)
        result = recovery.handle(action)
        await broadcast_decision(action, result.decision)
        if result.retry_action is not None and result.retry_decision is not None:
            await broadcast_decision(result.retry_action, result.retry_decision)
        return {"allowed": result.decision.allowed, "reason": result.decision.reason, "latency_ms": result.decision.latency_ms}

    @app.get("/policies")
    def get_policies():
        return {
            "halted": gateway.halted,
            "agents": {
                agent_id: {
                    "allowed_actions": sorted(p["allowed_actions"]),
                    "spend_cap": p["spend_cap"],
                    "revoked": p["revoked"],
                }
                for agent_id, p in gateway.policies.items()
            },
        }

    @app.patch("/policies/{agent_id}")
    def patch_policy(agent_id: str, patch: PolicyPatch):
        if patch.spend_cap is not None:
            gateway.set_spend_cap(agent_id, patch.spend_cap)
        if patch.toggle_action_type is not None:
            gateway.toggle_permission(agent_id, patch.toggle_action_type)
        p = gateway.policies[agent_id]
        return {"allowed_actions": sorted(p["allowed_actions"]), "spend_cap": p["spend_cap"], "revoked": p["revoked"]}

    @app.post("/agents/{agent_id}/revoke")
    def revoke_agent(agent_id: str):
        gateway.revoke(agent_id)
        return {"agent_id": agent_id, "revoked": True}

    @app.post("/agents/{agent_id}/unrevoke")
    def unrevoke_agent(agent_id: str):
        gateway.unrevoke(agent_id)
        return {"agent_id": agent_id, "revoked": False}

    @app.post("/fleet/halt")
    def fleet_halt():
        gateway.halt_fleet()
        return {"halted": True}

    @app.post("/fleet/resume")
    def fleet_resume():
        gateway.resume_fleet()
        return {"halted": False}

    @app.get("/audit")
    def get_audit(limit: int = 200):
        return audit.list(limit)

    @app.post("/seed")
    async def seed():
        results = []
        for scripted in all_scripted_actions():
            result = recovery.handle(scripted.action)
            await broadcast_decision(scripted.action, result.decision)
            if result.retry_action is not None and result.retry_decision is not None:
                await broadcast_decision(result.retry_action, result.retry_decision)
            results.append({"agent_id": scripted.action.agent_id, "allowed": result.decision.allowed})
        return {"seeded": len(results), "results": results}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


app = create_app()
