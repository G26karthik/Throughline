import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from src.backend.main import create_app
from tests.backend.conftest import TEST_DASHBOARD_PASSWORD, TEST_DATABASE_URL


def make_client():
    app = create_app(db_path=TEST_DATABASE_URL)
    client = TestClient(app)
    token = client.post("/auth/login", json={"password": TEST_DASHBOARD_PASSWORD}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client, token


def test_seed_reports_high_accuracy_and_latency():
    client, _token = make_client()
    resp = client.post("/seed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolution_accuracy_pct"] == 100.0
    assert body["pipeline_latency_ms"] > 0
    assert body["avg_latency_per_event_ms"] > 0


def test_customers_endpoint_lists_resolved_customers_with_friction():
    client, _token = make_client()
    client.post("/seed")
    resp = client.get("/customers")
    customers = {c["customer_id"]: c for c in resp.json()}
    assert "cust_014" not in customers  # orphan never resolves to a customer
    assert customers["cust_006"]["friction_count"] == 2


def test_timeline_endpoint_marks_escalation_events():
    client, _token = make_client()
    client.post("/seed")
    resp = client.get("/timeline/cust_006")
    body = resp.json()
    assert len(body["timeline"]) == 4
    assert all(e["is_escalation"] for e in body["timeline"])
    assert body["friction_count"] == 2


def test_unresolved_endpoint_surfaces_orphan_and_weak_signal_events():
    client, _token = make_client()
    client.post("/seed")
    resp = client.get("/unresolved")
    refs = {e["raw_ref"] for e in resp.json()}
    assert "callcenter_events:5" in refs  # true orphan
    assert len(refs) == 3


def test_aggregate_endpoint_reports_churn_correlation():
    client, _token = make_client()
    client.post("/seed")
    resp = client.get("/aggregate")
    body = resp.json()
    churn = body["churn_correlation"]
    assert churn["high_friction_avg_trailing_activity"] < churn["clean_avg_trailing_activity"]


def test_demo_run_streams_all_beats_over_websocket():
    client, token = make_client()
    with client.websocket_connect(f"/ws?token={token}") as ws:
        client.post("/demo/run", params={"delay_seconds": 0})
        messages = [ws.receive_json() for _ in range(9)]  # 4 scattered + 4 resolved + 1 unresolved
        types = [m["type"] for m in messages]
        assert types == ["scattered"] * 4 + ["resolved"] * 4 + ["unresolved_case"]


def test_dashboard_endpoints_reject_missing_or_wrong_credentials():
    app = create_app(db_path=TEST_DATABASE_URL)
    client = TestClient(app)

    assert client.get("/customers").status_code == 401
    assert client.post("/auth/login", json={"password": "wrong"}).status_code == 401

    token = client.post("/auth/login", json={"password": TEST_DASHBOARD_PASSWORD}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/customers").status_code == 200

    # no ?token= on the handshake -- server closes with the custom auth-failure code
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()


def test_ai_endpoints_503_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client, _token = make_client()
    client.post("/seed")

    assert client.post("/ai/summarize/cust_006").status_code == 503
    assert client.post("/ai/query", json={"question": "anything"}).status_code == 503
