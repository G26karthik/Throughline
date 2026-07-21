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
    d = rec.handle(Action("dispute_agent", "issue_refund", 120.0, "acct-1"))
    assert d.allowed is True
    assert len(audit.list()) == 1


def test_over_cap_action_retries_clamped_amount_and_succeeds():
    rec, gw, audit = make_recovery()
    d = rec.handle(Action("dispute_agent", "issue_refund", 9000.0, "acct-1"))
    assert d.allowed is True  # retry succeeded at clamped cap amount
    rows = audit.list()
    assert len(rows) == 2  # original block + retry allow
    assert rows[0]["decision"] == "allow"
    assert rows[0]["reason"].startswith("retry:")
    assert rows[1]["decision"] == "block"


def test_wrong_scope_action_escalates_not_retries():
    rec, _gw, audit = make_recovery()
    d = rec.handle(Action("benefit_agent", "raise_credit_limit", 100.0, "acct-1"))
    assert d.allowed is False
    rows = audit.list()
    assert len(rows) == 1  # no retry row, scope violations aren't retryable
    escalations = audit.conn.execute("SELECT * FROM escalations").fetchall()
    assert len(escalations) == 1
    assert escalations[0]["agent_id"] == "benefit_agent"


def test_revoked_agent_escalates():
    rec, gw, audit = make_recovery()
    gw.revoke("servicing_agent")
    d = rec.handle(Action("servicing_agent", "reissue_card", 0.0, "acct-1"))
    assert d.allowed is False
    escalations = audit.conn.execute("SELECT * FROM escalations").fetchall()
    assert len(escalations) == 1
