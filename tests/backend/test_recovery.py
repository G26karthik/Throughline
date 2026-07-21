from src.backend.gateway import PolicyGateway, Action
from src.backend.audit import get_connection, AuditLog
from src.backend.recovery import Recovery


def make_recovery():
    gw = PolicyGateway()
    conn = get_connection(":memory:")
    audit = AuditLog(conn)
    return Recovery(gw, audit), gw, audit


def test_in_policy_action_allowed_once_logged_once():
    rec, _gw, audit = make_recovery()
    result = rec.handle(Action("dispute_agent", "issue_refund", 120.0, "acct-1"))
    assert result.decision.allowed is True
    assert result.retry_decision is None
    assert len(audit.list()) == 1


def test_over_cap_action_blocked_and_retry_succeeds_as_separate_event():
    rec, _gw, audit = make_recovery()
    result = rec.handle(Action("dispute_agent", "issue_refund", 9000.0, "acct-1"))
    assert result.decision.allowed is False  # caller sees the TRUE outcome of their request
    assert "spend_cap exceeded" in result.decision.reason
    assert result.retry_decision is not None
    assert result.retry_decision.allowed is True  # self-healed retry succeeded separately
    rows = audit.list()
    assert len(rows) == 2  # original block + retry allow
    assert rows[0]["decision"] == "allow"
    assert rows[0]["reason"].startswith("retry:")
    assert rows[1]["decision"] == "block"
    escalations = audit.conn.execute("SELECT * FROM escalations").fetchall()
    assert len(escalations) == 0  # retry succeeded, no escalation needed


def test_wrong_scope_action_escalates_not_retries():
    rec, _gw, audit = make_recovery()
    result = rec.handle(Action("benefit_agent", "raise_credit_limit", 100.0, "acct-1"))
    assert result.decision.allowed is False
    assert result.retry_decision is None
    rows = audit.list()
    assert len(rows) == 1  # no retry row, scope violations aren't retryable
    escalations = audit.conn.execute("SELECT * FROM escalations").fetchall()
    assert len(escalations) == 1
    assert escalations[0]["agent_id"] == "benefit_agent"


def test_revoked_agent_escalates():
    rec, gw, audit = make_recovery()
    gw.revoke("servicing_agent")
    result = rec.handle(Action("servicing_agent", "reissue_card", 0.0, "acct-1"))
    assert result.decision.allowed is False
    escalations = audit.conn.execute("SELECT * FROM escalations").fetchall()
    assert len(escalations) == 1
