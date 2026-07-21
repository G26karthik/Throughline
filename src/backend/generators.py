"""Mock event generators for four channels, plus ground-truth identity and
trailing-activity data used to score the resolution engine and compute the
churn correlation in analytics.py.

All timestamps are deterministic (anchored to BASE_TS) so every reported
metric is exactly reproducible between runs - no random module anywhere.
"""

BASE_TS = 1_700_000_000.0  # fixed anchor, 2023-11-14T22:13:20Z - arbitrary but stable
MIN = 60
HOUR = 3600
DAY = 86400


def _t(offset_seconds: float) -> float:
    return BASE_TS + offset_seconds


# Ground truth: customer_id -> friction_count seeded into their journey.
# friction_count >= 2 customers get a deliberately thin trailing-activity
# window in generate_trailing_activity(); this is the correlation Phase 4
# recovers and reports, not something analytics.py invents.
FRICTION_COUNT = {
    "cust_001": 0,
    "cust_002": 0,
    "cust_003": 0,
    "cust_004": 0,
    "cust_005": 1,
    "cust_006": 3,
    "cust_007": 2,
    "cust_008": 0,
    "cust_009": 0,
    "cust_010": 0,
    "cust_011": 1,
    "cust_012": 2,
    "cust_013": 0,
    # cust_014 has no resolvable journey (single orphan event) - excluded
    # from the friction/clean churn comparison, not enough journey to judge.
}


def generate_dataset():
    app_events = []
    web_events = []
    callcenter_events = []
    inperson_events = []
    ground_truth = {}  # f"{channel}:{index}" -> customer_id or None

    def add(bucket, channel, customer_id, **fields):
        idx = len(bucket)
        ref = f"{channel}:{idx}"
        bucket.append(dict(fields))
        ground_truth[ref] = customer_id

    # --- cust_001: clean, single channel (app only) ---
    add(app_events, "app_events", "cust_001", user_id="u_001", device_id="dev_001",
        action="login", timestamp=_t(0))
    add(app_events, "app_events", "cust_001", user_id="u_001", device_id="dev_001",
        action="view_claim", timestamp=_t(5 * MIN))

    # --- cust_002: clean, cross-channel via shared email (web -> app) ---
    add(web_events, "web_events", "cust_002", cookie_id="ck_002", email="a.reyes@example.com",
        action="login", timestamp=_t(0))
    add(app_events, "app_events", "cust_002", user_id="u_002", device_id="dev_002",
        action="view_claim", timestamp=_t(20 * MIN))

    # --- cust_003: clean, cross-channel via shared phone (web auth -> callcenter) ---
    add(web_events, "web_events", "cust_003", cookie_id="ck_003", email="j.park@example.com",
        action="submit_dispute", timestamp=_t(0))
    add(callcenter_events, "callcenter_events", "cust_003", phone_number="+1-555-0103",
        case_id="case_1003", reason_code="dispute_followup", duration=240, timestamp=_t(45 * MIN))

    # --- cust_004: clean, probabilistic link (no shared field, time+device proximity) ---
    add(app_events, "app_events", "cust_004", user_id="u_004", device_id="dev_004",
        action="fail_checkout", timestamp=_t(0))
    add(web_events, "web_events", "cust_004", cookie_id="ck_004", email=None,
        action="view_claim", timestamp=_t(4 * MIN))

    # --- cust_005: friction=1, repeat-contact (web fail_checkout -> callcenter, same phone) ---
    add(web_events, "web_events", "cust_005", cookie_id="ck_005", email="m.diallo@example.com",
        action="fail_checkout", timestamp=_t(0))
    add(callcenter_events, "callcenter_events", "cust_005", phone_number="+1-555-0105",
        case_id="case_1005", reason_code="checkout_failure", duration=310, timestamp=_t(8 * MIN))

    # --- cust_006: friction=3, escalation chain across all 4 channels, tight window ---
    add(app_events, "app_events", "cust_006", user_id="u_006", device_id="dev_006",
        action="submit_dispute", timestamp=_t(0))
    add(web_events, "web_events", "cust_006", cookie_id="ck_006", email="t.chen@example.com",
        action="view_claim", timestamp=_t(3 * MIN))
    add(callcenter_events, "callcenter_events", "cust_006", phone_number="+1-555-0106",
        case_id="case_1006", reason_code="dispute_escalation", duration=520, timestamp=_t(9 * MIN))
    add(inperson_events, "inperson_events", "cust_006", card_last4="6006", terminal_id="term_44",
        merchant="Branch Office 12", amount=0.0, timestamp=_t(40 * MIN))

    # --- cust_007: friction=2, two escalation hops (app -> callcenter -> web) ---
    add(app_events, "app_events", "cust_007", user_id="u_007", device_id="dev_007",
        action="fail_checkout", timestamp=_t(0))
    add(callcenter_events, "callcenter_events", "cust_007", phone_number="+1-555-0107",
        case_id="case_1007", reason_code="checkout_failure", duration=280, timestamp=_t(6 * MIN))
    add(web_events, "web_events", "cust_007", cookie_id="ck_007", email="r.oduya@example.com",
        action="submit_dispute", timestamp=_t(30 * MIN))

    # --- cust_008 / cust_009: ambiguous shared device, distinguishable via own web session ---
    add(app_events, "app_events", "cust_008", user_id="u_008", device_id="dev_shared_89",
        action="login", timestamp=_t(0))
    add(web_events, "web_events", "cust_008", cookie_id="ck_008", email="l.novak@example.com",
        action="view_claim", timestamp=_t(10 * MIN))
    add(app_events, "app_events", "cust_009", user_id="u_009", device_id="dev_shared_89",
        action="login", timestamp=_t(2 * HOUR))
    add(web_events, "web_events", "cust_009", cookie_id="ck_009", email="s.abara@example.com",
        action="view_claim", timestamp=_t(2 * HOUR + 12 * MIN))

    # --- cust_010: clean, single channel (in-person only) ---
    add(inperson_events, "inperson_events", "cust_010", card_last4="7010", terminal_id="term_02",
        merchant="Downtown Cafe", amount=14.50, timestamp=_t(0))

    # --- cust_011: friction=1, drop-off (fail_checkout, never followed up) ---
    add(app_events, "app_events", "cust_011", user_id="u_011", device_id="dev_011",
        action="fail_checkout", timestamp=_t(0))

    # --- cust_012: friction=2, repeat-contact then in-branch resolution ---
    add(web_events, "web_events", "cust_012", cookie_id="ck_012", email="p.singh@example.com",
        action="fail_checkout", timestamp=_t(0))
    add(callcenter_events, "callcenter_events", "cust_012", phone_number="+1-555-0112",
        case_id="case_1012", reason_code="checkout_failure", duration=390, timestamp=_t(11 * MIN))
    add(inperson_events, "inperson_events", "cust_012", card_last4="6012", terminal_id="term_09",
        merchant="Branch Office 3", amount=0.0, timestamp=_t(3 * HOUR))

    # --- cust_013: clean, cross-channel via shared card_last4 (web intent -> in-person) ---
    add(web_events, "web_events", "cust_013", cookie_id="ck_013", email="d.okafor@example.com",
        action="view_claim", timestamp=_t(0))
    add(inperson_events, "inperson_events", "cust_013", card_last4="9013", terminal_id="term_15",
        merchant="Midtown Electronics", amount=249.99, timestamp=_t(90 * MIN))

    # --- cust_014: orphan, phone number matches no known customer record ---
    add(callcenter_events, "callcenter_events", None, phone_number="+1-555-9999",
        case_id="case_9999", reason_code="general_inquiry", duration=95, timestamp=_t(0))

    return {
        "app_events": app_events,
        "web_events": web_events,
        "callcenter_events": callcenter_events,
        "inperson_events": inperson_events,
        "ground_truth": ground_truth,
    }


# customer_id -> registered identifiers, used only to build the dataset above
# and as the deterministic-match reference table for resolution.py.
CUSTOMER_REGISTRY = {
    "cust_001": {"email": None, "phone": None, "card_last4": None},
    "cust_002": {"email": "a.reyes@example.com", "phone": None, "card_last4": None},
    "cust_003": {"email": "j.park@example.com", "phone": "+1-555-0103", "card_last4": None},
    "cust_004": {"email": None, "phone": None, "card_last4": None},
    "cust_005": {"email": "m.diallo@example.com", "phone": "+1-555-0105", "card_last4": None},
    "cust_006": {"email": "t.chen@example.com", "phone": "+1-555-0106", "card_last4": "6006"},
    "cust_007": {"email": "r.oduya@example.com", "phone": "+1-555-0107", "card_last4": None},
    "cust_008": {"email": "l.novak@example.com", "phone": None, "card_last4": None},
    "cust_009": {"email": "s.abara@example.com", "phone": None, "card_last4": None},
    "cust_010": {"email": None, "phone": None, "card_last4": "7010"},
    "cust_011": {"email": None, "phone": None, "card_last4": None},
    "cust_012": {"email": "p.singh@example.com", "phone": "+1-555-0112", "card_last4": "6012"},
    "cust_013": {"email": "d.okafor@example.com", "phone": None, "card_last4": "9013"},
}


def generate_trailing_activity():
    """Trailing-activity app_events per customer, generated beyond their
    seeded journey. Customers with friction_count >= 2 get a deliberately
    thin window; clean-journey customers get a full one. This is the raw
    signal analytics.py measures the churn correlation from - the ratio
    itself is computed there, not asserted here.
    """
    events = []
    window_start = 30 * DAY

    for customer_id, friction in FRICTION_COUNT.items():
        count = 1 if friction >= 2 else 5
        for i in range(count):
            events.append({
                "customer_id": customer_id,  # ground truth, used directly - this is
                                              # first-party trailing telemetry, not an
                                              # identity-resolution input
                "action": "login",
                "timestamp": _t(window_start + i * DAY),
            })
    return events
