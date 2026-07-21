"""Mock event generators for four channels, plus a known-customer registry
and trailing-activity data used to score the resolution engine and compute
the churn correlation in analytics.py.

All timestamps are deterministic (anchored to BASE_TS, one distinct day per
customer) so every reported metric is exactly reproducible between runs -
no random module anywhere, and no cross-customer timestamp collisions that
would let the probabilistic matcher spuriously link unrelated customers.

Design note: only email, phone, and card_last4 are treated as registry
("known customer") identifiers - the kind AmEx already has on file. device_id
and cookie_id are deliberately NOT registry keys; they're weak, possibly
-shared pseudonymous signals that can only ever contribute to probabilistic
scoring, never a direct match. That's what makes the shared-device case
(cust_008/cust_009) a real test of "don't force a match on a weak signal."
"""

BASE_TS = 1_700_000_000.0  # fixed anchor, 2023-11-14T22:13:20Z - arbitrary but stable
MIN = 60
HOUR = 3600
DAY = 86400

# Index of each customer in this list determines their day offset, keeping
# every customer's story on its own day so pooled probabilistic matching
# never sees two unrelated customers' events fall inside the same window.
_CUSTOMER_ORDER = [
    "cust_001", "cust_002", "cust_003", "cust_004", "cust_005", "cust_006",
    "cust_007", "cust_008_009", "cust_010", "cust_011", "cust_012", "cust_013",
    "cust_014",
]


def _day(customer_key: str) -> float:
    return _CUSTOMER_ORDER.index(customer_key) * DAY


def _t(day_offset: float, local_offset: float = 0.0) -> float:
    return BASE_TS + day_offset + local_offset


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

# Known-customer registry: only email/phone/card_last4 are hard identifiers.
CUSTOMER_REGISTRY = {
    "cust_001": {"email": "a.reyes@example.com"},
    "cust_002": {"email": "b.moreno@example.com", "card_last4": "4402"},
    "cust_003": {"email": "j.park@example.com", "phone": "+1-555-0103"},
    "cust_004": {"email": "k.iwata@example.com"},
    "cust_005": {"email": "m.diallo@example.com", "phone": "+1-555-0105"},
    "cust_006": {"email": "t.chen@example.com", "phone": "+1-555-0106", "card_last4": "6006"},
    "cust_007": {"email": "r.oduya@example.com", "phone": "+1-555-0107"},
    "cust_008": {"email": "l.novak@example.com"},
    "cust_009": {"email": "s.abara@example.com"},
    "cust_010": {"card_last4": "7010"},
    "cust_011": {"email": "f.moreau@example.com"},
    "cust_012": {"email": "p.singh@example.com", "phone": "+1-555-0112", "card_last4": "6012"},
    "cust_013": {"card_last4": "9013"},
}


def generate_dataset():
    app_events = []
    web_events = []
    callcenter_events = []
    inperson_events = []
    ground_truth = {}  # f"{channel}:{index}" -> customer_id, or None if
                        # expected to stay unresolved (orphan or genuinely
                        # weak-signal-only event)

    def add(bucket, channel, expected_customer_id, **fields):
        idx = len(bucket)
        ref = f"{channel}:{idx}"
        bucket.append(dict(fields))
        ground_truth[ref] = expected_customer_id

    # --- cust_001: single-channel clean (web only, email-anchored) ---
    d = _day("cust_001")
    add(web_events, "web_events", "cust_001", cookie_id="ck_001", email="a.reyes@example.com",
        action="login", timestamp=_t(d))

    # --- cust_002: cross-channel clean, two independent hard anchors (email + card) ---
    d = _day("cust_002")
    add(web_events, "web_events", "cust_002", cookie_id="ck_002", email="b.moreno@example.com",
        action="login", timestamp=_t(d))
    add(inperson_events, "inperson_events", "cust_002", card_last4="4402", terminal_id="term_07",
        merchant="Uptown Pharmacy", amount=32.10, timestamp=_t(d, 45 * MIN))

    # --- cust_003: cross-channel clean, two independent hard anchors (email + phone) ---
    d = _day("cust_003")
    add(web_events, "web_events", "cust_003", cookie_id="ck_003", email="j.park@example.com",
        action="submit_dispute", timestamp=_t(d))
    add(callcenter_events, "callcenter_events", "cust_003", phone_number="+1-555-0103",
        case_id="case_1003", reason_code="dispute_followup", duration=240, timestamp=_t(d, 45 * MIN))

    # --- cust_004: clean probabilistic - web anchor + app linked via time+behavior ---
    d = _day("cust_004")
    add(web_events, "web_events", "cust_004", cookie_id="ck_004", email="k.iwata@example.com",
        action="fail_checkout", timestamp=_t(d))
    add(app_events, "app_events", "cust_004", user_id="u_004", device_id="dev_004",
        action="view_claim", timestamp=_t(d, 4 * MIN))

    # --- cust_005: friction=1, repeat-contact, two independent hard anchors ---
    d = _day("cust_005")
    add(web_events, "web_events", "cust_005", cookie_id="ck_005", email="m.diallo@example.com",
        action="fail_checkout", timestamp=_t(d))
    add(callcenter_events, "callcenter_events", "cust_005", phone_number="+1-555-0105",
        case_id="case_1005", reason_code="checkout_failure", duration=310, timestamp=_t(d, 8 * MIN))

    # --- cust_006: friction=3, escalation chain across all 4 channels ---
    d = _day("cust_006")
    add(app_events, "app_events", "cust_006", user_id="u_006", device_id="dev_006",
        action="submit_dispute", timestamp=_t(d))
    add(web_events, "web_events", "cust_006", cookie_id="ck_006", email="t.chen@example.com",
        action="view_claim", timestamp=_t(d, 3 * MIN))
    add(callcenter_events, "callcenter_events", "cust_006", phone_number="+1-555-0106",
        case_id="case_1006", reason_code="dispute_escalation", duration=520, timestamp=_t(d, 9 * MIN))
    add(inperson_events, "inperson_events", "cust_006", card_last4="6006", terminal_id="term_44",
        merchant="Branch Office 12", amount=0.0, timestamp=_t(d, 40 * MIN))

    # --- cust_007: friction=2, app links probabilistically to callcenter anchor ---
    d = _day("cust_007")
    add(app_events, "app_events", "cust_007", user_id="u_007", device_id="dev_007",
        action="fail_checkout", timestamp=_t(d))
    add(callcenter_events, "callcenter_events", "cust_007", phone_number="+1-555-0107",
        case_id="case_1007", reason_code="checkout_failure", duration=280, timestamp=_t(d, 6 * MIN))
    add(web_events, "web_events", "cust_007", cookie_id="ck_007", email="r.oduya@example.com",
        action="submit_dispute", timestamp=_t(d, 30 * MIN))

    # --- cust_008 / cust_009: shared device, same day, hours apart. Their
    # app logins carry no hard identifier and no behavioral trigger, so
    # they're expected to stay unresolved rather than being force-matched
    # off the shared device_id - that's the point of this pair. ---
    d = _day("cust_008_009")
    add(app_events, "app_events", None, user_id="u_008", device_id="dev_shared_89",
        action="login", timestamp=_t(d))
    add(web_events, "web_events", "cust_008", cookie_id="ck_008", email="l.novak@example.com",
        action="view_claim", timestamp=_t(d, 10 * MIN))
    add(app_events, "app_events", None, user_id="u_009", device_id="dev_shared_89",
        action="login", timestamp=_t(d, 3 * HOUR))
    add(web_events, "web_events", "cust_009", cookie_id="ck_009", email="s.abara@example.com",
        action="view_claim", timestamp=_t(d, 3 * HOUR + 12 * MIN))

    # --- cust_010: single-channel clean (in-person only, card-anchored) ---
    d = _day("cust_010")
    add(inperson_events, "inperson_events", "cust_010", card_last4="7010", terminal_id="term_02",
        merchant="Downtown Cafe", amount=14.50, timestamp=_t(d))

    # --- cust_011: friction=1, drop-off - self-anchoring fail, never followed up ---
    d = _day("cust_011")
    add(web_events, "web_events", "cust_011", cookie_id="ck_011", email="f.moreau@example.com",
        action="fail_checkout", timestamp=_t(d))

    # --- cust_012: friction=2, repeat-contact then in-branch resolution, 3 hard anchors ---
    d = _day("cust_012")
    add(web_events, "web_events", "cust_012", cookie_id="ck_012", email="p.singh@example.com",
        action="fail_checkout", timestamp=_t(d))
    add(callcenter_events, "callcenter_events", "cust_012", phone_number="+1-555-0112",
        case_id="case_1012", reason_code="checkout_failure", duration=390, timestamp=_t(d, 11 * MIN))
    add(inperson_events, "inperson_events", "cust_012", card_last4="6012", terminal_id="term_09",
        merchant="Branch Office 3", amount=0.0, timestamp=_t(d, 3 * HOUR))

    # --- cust_013: clean probabilistic - anonymous web fail_checkout (no
    # email) completes as an in-person purchase, linked via time+behavior
    # to the card-anchored in-person event. ---
    d = _day("cust_013")
    add(web_events, "web_events", "cust_013", cookie_id="ck_013", email=None,
        action="fail_checkout", timestamp=_t(d))
    add(inperson_events, "inperson_events", "cust_013", card_last4="9013", terminal_id="term_15",
        merchant="Midtown Electronics", amount=249.99, timestamp=_t(d, 9 * MIN))

    # --- cust_014: orphan, phone number matches no known customer record ---
    d = _day("cust_014")
    add(callcenter_events, "callcenter_events", None, phone_number="+1-555-9999",
        case_id="case_9999", reason_code="general_inquiry", duration=95, timestamp=_t(d))

    return {
        "app_events": app_events,
        "web_events": web_events,
        "callcenter_events": callcenter_events,
        "inperson_events": inperson_events,
        "ground_truth": ground_truth,
    }


def generate_trailing_activity():
    """Trailing-activity app_events per customer, generated beyond their
    seeded journey. Customers with friction_count >= 2 get a deliberately
    thin window; clean-journey customers get a full one. This is the raw
    signal analytics.py measures the churn correlation from - the ratio
    itself is computed there, not asserted here.
    """
    events = []
    window_start = 60 * DAY  # well beyond the last customer's day offset

    for customer_id, friction in FRICTION_COUNT.items():
        count = 1 if friction >= 2 else 5
        for i in range(count):
            events.append({
                "customer_id": customer_id,  # ground truth, used directly - this is
                                              # first-party trailing telemetry, not an
                                              # identity-resolution input
                "action": "login",
                "timestamp": _t(window_start, i * DAY),
            })
    return events
