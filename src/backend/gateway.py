import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Action:
    agent_id: str
    action_type: str
    amount: float = 0.0
    target_account: str = ""


@dataclass
class Decision:
    allowed: bool
    reason: str
    latency_ms: float


DEFAULT_POLICIES = {
    "dispute_agent": {"allowed_actions": {"issue_refund", "request_evidence"}, "spend_cap": 500.0, "revoked": False},
    "benefit_agent": {"allowed_actions": {"activate_benefit", "file_claim"}, "spend_cap": 1000.0, "revoked": False},
    "servicing_agent": {"allowed_actions": {"raise_credit_limit", "reverse_fee", "reissue_card"}, "spend_cap": 2000.0, "revoked": False},
}


class PolicyGateway:
    def __init__(self, policies: Optional[dict] = None):
        source = policies if policies is not None else DEFAULT_POLICIES
        self.policies = {
            agent_id: {
                "allowed_actions": set(p["allowed_actions"]),
                "spend_cap": p["spend_cap"],
                "revoked": p["revoked"],
            }
            for agent_id, p in source.items()
        }
        self.halted = False

    def check(self, action: Action) -> Decision:
        start = time.perf_counter()
        allowed, reason = True, "ok"

        if self.halted:
            allowed, reason = False, "fleet halted"
        else:
            policy = self.policies.get(action.agent_id)
            if policy is None:
                allowed, reason = False, f"unknown agent {action.agent_id}"
            elif policy["revoked"]:
                allowed, reason = False, f"agent {action.agent_id} revoked"
            elif action.action_type not in policy["allowed_actions"]:
                allowed, reason = False, f"action '{action.action_type}' not in scope for {action.agent_id}"
            elif action.amount and action.amount > policy["spend_cap"]:
                allowed, reason = False, (
                    f"spend_cap exceeded: requested ${action.amount:.2f} > cap ${policy['spend_cap']:.2f}"
                )

        latency_ms = (time.perf_counter() - start) * 1000
        return Decision(allowed=allowed, reason=reason, latency_ms=latency_ms)

    def revoke(self, agent_id: str) -> None:
        self.policies[agent_id]["revoked"] = True

    def unrevoke(self, agent_id: str) -> None:
        self.policies[agent_id]["revoked"] = False

    def halt_fleet(self) -> None:
        self.halted = True

    def resume_fleet(self) -> None:
        self.halted = False

    def set_spend_cap(self, agent_id: str, cap: float) -> None:
        self.policies[agent_id]["spend_cap"] = cap

    def toggle_permission(self, agent_id: str, action_type: str) -> None:
        allowed = self.policies[agent_id]["allowed_actions"]
        if action_type in allowed:
            allowed.remove(action_type)
        else:
            allowed.add(action_type)
