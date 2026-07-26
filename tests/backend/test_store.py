from src.backend.store import get_connection, EventStore
from tests.backend.conftest import TEST_DATABASE_URL


def test_insert_and_all_events_roundtrip():
    store = EventStore(get_connection(TEST_DATABASE_URL))
    row_id = store.insert("cust_001", "web_events", "login", 100.0, 1.0, "deterministic", "web_events:0", "login")
    assert row_id == 1
    rows = store.all_events()
    assert len(rows) == 1
    assert rows[0]["customer_id"] == "cust_001"
    assert rows[0]["confidence"] == 1.0


def test_timeline_for_customer_orders_chronologically():
    store = EventStore(get_connection(TEST_DATABASE_URL))
    store.insert("cust_001", "app_events", "view_claim", 200.0, 1.0, "deterministic", "app_events:1", "view_claim")
    store.insert("cust_001", "web_events", "login", 100.0, 1.0, "deterministic", "web_events:0", "login")
    store.insert("cust_002", "web_events", "login", 50.0, 1.0, "deterministic", "web_events:2", "login")

    timeline = store.timeline_for_customer("cust_001")
    assert len(timeline) == 2
    assert [e["timestamp"] for e in timeline] == [100.0, 200.0]


def test_unresolved_events_have_null_customer_id():
    store = EventStore(get_connection(TEST_DATABASE_URL))
    store.insert(None, "callcenter_events", "general_inquiry", 10.0, 0.0, "unresolved", "callcenter_events:0", "orphan")
    unresolved = store.unresolved_events()
    assert len(unresolved) == 1
    assert unresolved[0]["customer_id"] is None
