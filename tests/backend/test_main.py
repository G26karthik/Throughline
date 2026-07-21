from fastapi.testclient import TestClient

from src.backend.main import create_app


def make_client():
    app = create_app(db_path=":memory:")
    return TestClient(app)


def test_action_allowed_returns_200_and_decision():
    client = make_client()
    resp = client.post("/actions", json={
        "agent_id": "dispute_agent", "action_type": "issue_refund",
        "amount": 100.0, "target_account": "acct-1",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is True


def test_over_cap_action_blocked_reason_returned():
    client = make_client()
    resp = client.post("/actions", json={
        "agent_id": "dispute_agent", "action_type": "issue_refund",
        "amount": 9000.0, "target_account": "acct-1",
    })
    body = resp.json()
    assert "spend_cap exceeded" in body["reason"]


def test_patch_policy_updates_spend_cap():
    client = make_client()
    resp = client.patch("/policies/dispute_agent", json={"spend_cap": 10.0})
    assert resp.status_code == 200
    resp2 = client.post("/actions", json={
        "agent_id": "dispute_agent", "action_type": "issue_refund",
        "amount": 20.0, "target_account": "acct-1",
    })
    assert resp2.json()["allowed"] is False


def test_fleet_halt_blocks_all_agents():
    client = make_client()
    client.post("/fleet/halt")
    resp = client.post("/actions", json={
        "agent_id": "servicing_agent", "action_type": "reissue_card",
        "amount": 0.0, "target_account": "acct-1",
    })
    assert resp.json()["reason"] == "fleet halted"


def test_audit_endpoint_returns_recorded_rows():
    client = make_client()
    client.post("/actions", json={
        "agent_id": "dispute_agent", "action_type": "issue_refund",
        "amount": 10.0, "target_account": "acct-1",
    })
    resp = client.get("/audit")
    assert len(resp.json()) == 1


def test_websocket_receives_decision_event():
    client = make_client()
    with client.websocket_connect("/ws") as ws:
        client.post("/actions", json={
            "agent_id": "dispute_agent", "action_type": "issue_refund",
            "amount": 10.0, "target_account": "acct-1",
        })
        msg = ws.receive_json()
        assert msg["type"] == "decision"
        assert msg["agent_id"] == "dispute_agent"
