from src.backend.generators import generate_dataset, generate_trailing_activity, CUSTOMER_REGISTRY
from src.backend.store import EventStore, get_connection
from src.backend.pipeline import run_pipeline
from src.backend.analytics import compute_friction, compute_aggregate_analytics
from tests.backend.conftest import TEST_DATABASE_URL


def _seeded_store():
    data = generate_dataset()
    store = EventStore(get_connection(TEST_DATABASE_URL))
    run_pipeline(
        data["app_events"], data["web_events"], data["callcenter_events"], data["inperson_events"],
        CUSTOMER_REGISTRY, store,
    )
    return store


def test_repeat_contact_and_escalation_detected_for_cust_006():
    store = _seeded_store()
    timeline = store.timeline_for_customer("cust_006")
    friction = compute_friction(timeline)
    assert friction["repeat_contacts"]
    assert friction["escalation_chain"] is not None
    assert set(friction["escalation_chain"]["channels"]) == {
        "app_events", "web_events", "callcenter_events", "inperson_events",
    }
    assert friction["friction_count"] == 2


def test_dropoff_detected_for_cust_011_no_followup():
    store = _seeded_store()
    timeline = store.timeline_for_customer("cust_011")
    friction = compute_friction(timeline)
    assert len(friction["dropoffs"]) == 1
    assert friction["friction_count"] == 1


def test_clean_customer_has_zero_friction():
    store = _seeded_store()
    timeline = store.timeline_for_customer("cust_002")
    friction = compute_friction(timeline)
    assert friction["friction_count"] == 0


def test_aggregate_analytics_reports_rates_and_shapes():
    store = _seeded_store()
    activity = generate_trailing_activity()
    agg = compute_aggregate_analytics(store, activity)

    assert agg["total_customers"] == 13  # cust_014 orphan never resolves, excluded
    assert agg["repeat_contact_rate_pct"] > 0
    assert agg["escalation_rate_pct"] > 0
    assert len(agg["journey_shapes"]) > 0
    assert agg["journey_shapes"][0]["count"] >= agg["journey_shapes"][-1]["count"]


def test_churn_correlation_shows_lower_trailing_activity_for_high_friction():
    store = _seeded_store()
    activity = generate_trailing_activity()
    agg = compute_aggregate_analytics(store, activity)
    churn = agg["churn_correlation"]

    assert churn["high_friction_customers"] > 0
    assert churn["clean_customers"] > 0
    assert churn["high_friction_avg_trailing_activity"] < churn["clean_avg_trailing_activity"]
