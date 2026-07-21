from dataclasses import dataclass

from src.backend.gateway import Action


@dataclass
class ScriptedAction:
    action: Action
    label: str  # "in_policy" or "violation"


def dispute_agent_actions() -> list[ScriptedAction]:
    return [
        ScriptedAction(Action("dispute_agent", "issue_refund", 120.0, "acct-1001"), "in_policy"),
        ScriptedAction(Action("dispute_agent", "request_evidence", 0.0, "acct-1002"), "in_policy"),
        ScriptedAction(Action("dispute_agent", "issue_refund", 9000.0, "acct-1003"), "violation"),
    ]


def benefit_agent_actions() -> list[ScriptedAction]:
    return [
        ScriptedAction(Action("benefit_agent", "activate_benefit", 0.0, "acct-2001"), "in_policy"),
        ScriptedAction(Action("benefit_agent", "file_claim", 300.0, "acct-2002"), "in_policy"),
        ScriptedAction(Action("benefit_agent", "raise_credit_limit", 500.0, "acct-2003"), "violation"),
    ]


def servicing_agent_actions() -> list[ScriptedAction]:
    return [
        ScriptedAction(Action("servicing_agent", "reverse_fee", 25.0, "acct-3001"), "in_policy"),
        ScriptedAction(Action("servicing_agent", "reissue_card", 0.0, "acct-3002"), "in_policy"),
        ScriptedAction(Action("servicing_agent", "raise_credit_limit", 1500.0, "acct-3003"), "in_policy"),
    ]


def all_scripted_actions() -> list[ScriptedAction]:
    return dispute_agent_actions() + benefit_agent_actions() + servicing_agent_actions()
