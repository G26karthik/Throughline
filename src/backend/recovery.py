import time

from src.backend.audit import AuditLog
from src.backend.gateway import Action, Decision, PolicyGateway


class Recovery:
    def __init__(self, gateway: PolicyGateway, audit: AuditLog):
        self.gateway = gateway
        self.audit = audit

    def handle(self, action: Action) -> Decision:
        decision = self.gateway.check(action)
        self.audit.record(
            action.agent_id, action.action_type, action.amount, action.target_account,
            "allow" if decision.allowed else "block", decision.reason, decision.latency_ms,
        )
        if decision.allowed:
            return decision

        if decision.reason.startswith("spend_cap exceeded"):
            policy = self.gateway.policies.get(action.agent_id)
            if policy is not None:
                retry_action = Action(action.agent_id, action.action_type, policy["spend_cap"], action.target_account)
                retry_decision = self.gateway.check(retry_action)
                self.audit.record(
                    action.agent_id, action.action_type, retry_action.amount, action.target_account,
                    "allow" if retry_decision.allowed else "block",
                    f"retry: {retry_decision.reason}", retry_decision.latency_ms,
                )
                if retry_decision.allowed:
                    return retry_decision

        self._escalate(action, decision.reason)
        return decision

    def _escalate(self, action: Action, reason: str) -> None:
        self.audit.conn.execute(
            "INSERT INTO escalations (ts, agent_id, action_type, amount, target_account, reason, resolved) "
            "VALUES (?,?,?,?,?,?,0)",
            (time.time(), action.agent_id, action.action_type, action.amount, action.target_account, reason),
        )
        self.audit.conn.commit()
