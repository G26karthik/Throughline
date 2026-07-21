from src.backend.gateway import PolicyGateway, Action


def test_allows_in_scope_in_cap_action():
    gw = PolicyGateway()
    d = gw.check(Action("dispute_agent", "issue_refund", 120.0, "acct-1"))
    assert d.allowed is True
    assert d.reason == "ok"
    assert d.latency_ms >= 0


def test_blocks_over_cap_with_specific_reason():
    gw = PolicyGateway()
    d = gw.check(Action("dispute_agent", "issue_refund", 9000.0, "acct-1"))
    assert d.allowed is False
    assert "spend_cap exceeded" in d.reason
    assert "9000" in d.reason


def test_blocks_wrong_scope_with_specific_reason():
    gw = PolicyGateway()
    d = gw.check(Action("benefit_agent", "raise_credit_limit", 100.0, "acct-1"))
    assert d.allowed is False
    assert "not in scope" in d.reason


def test_revoked_agent_blocked():
    gw = PolicyGateway()
    gw.revoke("servicing_agent")
    d = gw.check(Action("servicing_agent", "reissue_card", 0.0, "acct-1"))
    assert d.allowed is False
    assert "revoked" in d.reason


def test_fleet_halt_blocks_everyone():
    gw = PolicyGateway()
    gw.halt_fleet()
    d = gw.check(Action("dispute_agent", "issue_refund", 10.0, "acct-1"))
    assert d.allowed is False
    assert d.reason == "fleet halted"


def test_resume_after_halt():
    gw = PolicyGateway()
    gw.halt_fleet()
    gw.resume_fleet()
    d = gw.check(Action("dispute_agent", "issue_refund", 10.0, "acct-1"))
    assert d.allowed is True


def test_set_spend_cap_changes_future_decisions():
    gw = PolicyGateway()
    gw.set_spend_cap("dispute_agent", 50.0)
    d = gw.check(Action("dispute_agent", "issue_refund", 60.0, "acct-1"))
    assert d.allowed is False


def test_toggle_permission_adds_and_removes_scope():
    gw = PolicyGateway()
    gw.toggle_permission("benefit_agent", "raise_credit_limit")
    assert gw.check(Action("benefit_agent", "raise_credit_limit", 10.0, "acct-1")).allowed is True
    gw.toggle_permission("benefit_agent", "raise_credit_limit")
    assert gw.check(Action("benefit_agent", "raise_credit_limit", 10.0, "acct-1")).allowed is False
