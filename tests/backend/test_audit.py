from src.backend.audit import get_connection, AuditLog


def test_record_and_list_roundtrip():
    conn = get_connection(":memory:")
    log = AuditLog(conn)
    row_id = log.record("dispute_agent", "issue_refund", 120.0, "acct-1", "allow", "ok", 0.42)
    assert row_id == 1
    rows = log.list()
    assert len(rows) == 1
    assert rows[0]["agent_id"] == "dispute_agent"
    assert rows[0]["decision"] == "allow"
    assert rows[0]["reason"] == "ok"
    assert rows[0]["latency_ms"] == 0.42


def test_list_orders_newest_first():
    conn = get_connection(":memory:")
    log = AuditLog(conn)
    log.record("a", "x", 1.0, "acct", "allow", "ok", 0.1)
    log.record("b", "y", 2.0, "acct", "block", "no", 0.2)
    rows = log.list()
    assert [r["agent_id"] for r in rows] == ["b", "a"]


def test_escalations_table_exists():
    conn = get_connection(":memory:")
    AuditLog(conn)
    conn.execute(
        "INSERT INTO escalations (ts, agent_id, action_type, amount, target_account, reason, resolved) "
        "VALUES (0,'a','x',1.0,'acct','why',0)"
    )
    row = conn.execute("SELECT * FROM escalations").fetchone()
    assert row["agent_id"] == "a"
