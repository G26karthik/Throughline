from src.backend.generators import generate_dataset, CUSTOMER_REGISTRY
from src.backend.resolution import resolve_identities, PROBABILISTIC_THRESHOLD


def _resolve():
    data = generate_dataset()
    resolved = resolve_identities(
        data["app_events"], data["web_events"], data["callcenter_events"], data["inperson_events"],
        CUSTOMER_REGISTRY,
    )
    return data, resolved


def test_single_channel_deterministic_match():
    _, resolved = _resolve()
    r = resolved["web_events:0"]  # cust_001, email-anchored
    assert r.resolved_customer_id == "cust_001"
    assert r.method == "deterministic"
    assert r.confidence == 1.0


def test_independent_dual_anchor_cross_channel_match():
    _, resolved = _resolve()
    web = resolved["web_events:1"]  # cust_002 web, email-anchored
    inperson = resolved["inperson_events:0"]  # cust_002 inperson, card-anchored
    assert web.resolved_customer_id == "cust_002"
    assert inperson.resolved_customer_id == "cust_002"
    assert web.method == "deterministic"
    assert inperson.method == "deterministic"


def test_probabilistic_match_via_time_and_behavior():
    _, resolved = _resolve()
    app = resolved["app_events:0"]  # cust_004 app, no hard id, linked via fail_checkout->view_claim
    assert app.resolved_customer_id == "cust_004"
    assert app.method == "probabilistic"
    assert PROBABILISTIC_THRESHOLD <= app.confidence < 1.0


def test_escalation_chain_app_event_resolves_probabilistically():
    _, resolved = _resolve()
    app = resolved["app_events:1"]  # cust_006 app, submit_dispute -> view_claim followup
    assert app.resolved_customer_id == "cust_006"
    assert app.method == "probabilistic"


def test_shared_device_events_stay_unresolved_not_force_matched():
    _, resolved = _resolve()
    first_login = resolved["app_events:3"]   # dev_shared_89, u_008, no hard id, weak signal
    second_login = resolved["app_events:4"]  # dev_shared_89, u_009, 3h later
    assert first_login.resolved_customer_id is None
    assert second_login.resolved_customer_id is None
    assert first_login.method == "unresolved"
    assert second_login.method == "unresolved"
    # and critically: they must not have been merged with EACH OTHER either
    assert first_login.resolved_customer_id != "cust_008"
    assert second_login.resolved_customer_id != "cust_009"


def test_shared_device_customers_own_web_sessions_still_resolve():
    _, resolved = _resolve()
    assert resolved["web_events:7"].resolved_customer_id == "cust_008"
    assert resolved["web_events:8"].resolved_customer_id == "cust_009"


def test_anonymous_web_checkout_links_to_inperson_completion():
    _, resolved = _resolve()
    web = resolved["web_events:11"]  # cust_013, anonymous fail_checkout, no email
    assert web.resolved_customer_id == "cust_013"
    assert web.method == "probabilistic"


def test_orphan_phone_number_stays_unresolved():
    _, resolved = _resolve()
    orphan = resolved["callcenter_events:5"]  # phone matches no registry record
    assert orphan.resolved_customer_id is None
    assert orphan.method == "unresolved"


def test_dropoff_customer_self_anchors_with_no_followup():
    _, resolved = _resolve()
    r = resolved["web_events:9"]  # cust_011, fail_checkout, email-anchored, never followed up
    assert r.resolved_customer_id == "cust_011"
    assert r.method == "deterministic"


def test_overall_accuracy_against_ground_truth():
    data, resolved = _resolve()
    total = len(data["ground_truth"])
    correct = 0
    for ref, expected in data["ground_truth"].items():
        actual = resolved[ref].resolved_customer_id
        if actual == expected:
            correct += 1
    accuracy = correct / total
    assert accuracy == 1.0, f"accuracy {accuracy:.2%}, mismatches expected"
