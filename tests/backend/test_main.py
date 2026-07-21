from fastapi.testclient import TestClient

from src.backend.main import create_app


def make_client():
    app = create_app(db_path=":memory:")
    return TestClient(app)


def test_seed_reports_high_accuracy_and_latency():
    client = make_client()
    resp = client.post("/seed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolution_accuracy_pct"] == 100.0
    assert body["pipeline_latency_ms"] > 0
    assert body["avg_latency_per_event_ms"] > 0


def test_customers_endpoint_lists_resolved_customers_with_friction():
    client = make_client()
    client.post("/seed")
    resp = client.get("/customers")
    customers = {c["customer_id"]: c for c in resp.json()}
    assert "cust_014" not in customers  # orphan never resolves to a customer
    assert customers["cust_006"]["friction_count"] == 2


def test_timeline_endpoint_marks_escalation_events():
    client = make_client()
    client.post("/seed")
    resp = client.get("/timeline/cust_006")
    body = resp.json()
    assert len(body["timeline"]) == 4
    assert all(e["is_escalation"] for e in body["timeline"])
    assert body["friction_count"] == 2


def test_unresolved_endpoint_surfaces_orphan_and_weak_signal_events():
    client = make_client()
    client.post("/seed")
    resp = client.get("/unresolved")
    refs = {e["raw_ref"] for e in resp.json()}
    assert "callcenter_events:5" in refs  # true orphan
    assert len(refs) == 3


def test_aggregate_endpoint_reports_churn_correlation():
    client = make_client()
    client.post("/seed")
    resp = client.get("/aggregate")
    body = resp.json()
    churn = body["churn_correlation"]
    assert churn["high_friction_avg_trailing_activity"] < churn["clean_avg_trailing_activity"]


def test_demo_run_streams_all_beats_over_websocket():
    client = make_client()
    with client.websocket_connect("/ws") as ws:
        client.post("/demo/run", params={"delay_seconds": 0})
        messages = [ws.receive_json() for _ in range(9)]  # 4 scattered + 4 resolved + 1 unresolved
        types = [m["type"] for m in messages]
        assert types == ["scattered"] * 4 + ["resolved"] * 4 + ["unresolved_case"]
