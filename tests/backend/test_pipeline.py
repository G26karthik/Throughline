from src.backend.generators import generate_dataset, CUSTOMER_REGISTRY
from src.backend.store import EventStore, get_connection
from src.backend.pipeline import run_pipeline


def test_pipeline_inserts_every_raw_event_exactly_once():
    data = generate_dataset()
    store = EventStore(get_connection(":memory:"))
    result = run_pipeline(
        data["app_events"], data["web_events"], data["callcenter_events"], data["inperson_events"],
        CUSTOMER_REGISTRY, store,
    )
    total_raw = sum(len(data[c]) for c in ("app_events", "web_events", "callcenter_events", "inperson_events"))
    assert result["inserted"] == total_raw
    assert len(store.all_events()) == total_raw


def test_pipeline_reports_latency_stats():
    data = generate_dataset()
    store = EventStore(get_connection(":memory:"))
    result = run_pipeline(
        data["app_events"], data["web_events"], data["callcenter_events"], data["inperson_events"],
        CUSTOMER_REGISTRY, store,
    )
    assert result["pipeline_latency_ms"] > 0
    assert result["avg_latency_per_event_ms"] > 0
    assert result["avg_latency_per_event_ms"] < result["pipeline_latency_ms"]


def test_resolved_customer_timeline_ordered_and_detailed():
    data = generate_dataset()
    store = EventStore(get_connection(":memory:"))
    run_pipeline(
        data["app_events"], data["web_events"], data["callcenter_events"], data["inperson_events"],
        CUSTOMER_REGISTRY, store,
    )
    timeline = store.timeline_for_customer("cust_006")
    assert len(timeline) == 4  # app, web, callcenter, inperson - the escalation chain
    timestamps = [e["timestamp"] for e in timeline]
    assert timestamps == sorted(timestamps)
    assert all(e["detail"] for e in timeline)


def test_unresolved_events_land_in_store_with_null_customer():
    data = generate_dataset()
    store = EventStore(get_connection(":memory:"))
    run_pipeline(
        data["app_events"], data["web_events"], data["callcenter_events"], data["inperson_events"],
        CUSTOMER_REGISTRY, store,
    )
    unresolved = store.unresolved_events()
    # true orphan + 2 shared-device weak-signal app logins
    assert len(unresolved) == 3
