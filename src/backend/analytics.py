"""Journey analytics over stitched, resolved timelines: repeat-contact and
escalation-chain detection, drop-off detection, and the churn correlation
that crosses computed friction against the independently-generated
trailing-activity signal.

Friction here is COMPUTED from the resolved timeline itself (not read back
from the generator's seeded ground truth) - that's what makes the churn
correlation a real, derived finding rather than an asserted one.
"""

TRIGGER_ACTIONS = {"fail_checkout", "submit_dispute"}
REPEAT_CONTACT_WINDOW_SECONDS = 1800  # 30 minutes
ESCALATION_WINDOW_SECONDS = 3600      # 1 hour
DROPOFF_WINDOW_SECONDS = 1800         # 30 minutes


def detect_repeat_contacts(timeline: list[dict]) -> list[dict]:
    hits = []
    for i, trig in enumerate(timeline):
        if trig["action"] not in TRIGGER_ACTIONS:
            continue
        for later in timeline[i + 1:]:
            gap = later["timestamp"] - trig["timestamp"]
            if gap > REPEAT_CONTACT_WINDOW_SECONDS:
                break
            if later["channel"] == "callcenter_events":
                hits.append({
                    "trigger_ref": trig["raw_ref"],
                    "contact_ref": later["raw_ref"],
                    "gap_seconds": gap,
                })
                break
    return hits


def detect_escalation_chain(timeline: list[dict]):
    if not timeline:
        return None
    span = timeline[-1]["timestamp"] - timeline[0]["timestamp"]
    channels = {e["channel"] for e in timeline}
    if span <= ESCALATION_WINDOW_SECONDS and len(channels) >= 3:
        return {
            "channels": sorted(channels),
            "span_seconds": span,
            "event_refs": [e["raw_ref"] for e in timeline],
        }
    return None


def detect_dropoffs(timeline: list[dict]) -> list[dict]:
    hits = []
    for i, trig in enumerate(timeline):
        if trig["action"] not in TRIGGER_ACTIONS:
            continue
        followed = any(
            later["timestamp"] - trig["timestamp"] <= DROPOFF_WINDOW_SECONDS
            for later in timeline[i + 1:]
        )
        if not followed:
            hits.append({"trigger_ref": trig["raw_ref"], "customer_timeline_position": i})
    return hits


def compute_friction(timeline: list[dict]) -> dict:
    """0-3 friction flags for one customer's resolved timeline."""
    repeat_contacts = detect_repeat_contacts(timeline)
    escalation = detect_escalation_chain(timeline)
    dropoffs = detect_dropoffs(timeline)
    friction_count = sum([bool(repeat_contacts), bool(escalation), bool(dropoffs)])
    return {
        "repeat_contacts": repeat_contacts,
        "escalation_chain": escalation,
        "dropoffs": dropoffs,
        "friction_count": friction_count,
    }


def _journey_shape(timeline: list[dict]) -> str:
    shape = []
    for e in timeline:
        label = e["channel"].replace("_events", "")
        if not shape or shape[-1] != label:
            shape.append(label)
    return "->".join(shape)


def compute_aggregate_analytics(store, trailing_activity_events: list[dict]) -> dict:
    customer_ids = store.known_customer_ids()

    friction_by_customer = {}
    shape_counts: dict[str, int] = {}
    dropoff_points = []
    repeat_contact_customers = 0
    escalation_customers = 0

    for customer_id in customer_ids:
        timeline = store.timeline_for_customer(customer_id)
        friction = compute_friction(timeline)
        friction_by_customer[customer_id] = friction["friction_count"]

        if friction["repeat_contacts"]:
            repeat_contact_customers += 1
        if friction["escalation_chain"]:
            escalation_customers += 1
        for d in friction["dropoffs"]:
            dropoff_points.append({"customer_id": customer_id, **d})

        shape = _journey_shape(timeline)
        shape_counts[shape] = shape_counts.get(shape, 0) + 1

    total = len(customer_ids) or 1
    journey_shapes = sorted(
        ({"shape": s, "count": c} for s, c in shape_counts.items()),
        key=lambda x: x["count"], reverse=True,
    )

    trailing_counts: dict[str, int] = {}
    for e in trailing_activity_events:
        trailing_counts[e["customer_id"]] = trailing_counts.get(e["customer_id"], 0) + 1

    high_friction = [c for c in customer_ids if friction_by_customer.get(c, 0) >= 2]
    clean = [c for c in customer_ids if friction_by_customer.get(c, 0) == 0]

    def _avg_trailing(customers):
        if not customers:
            return 0.0
        return sum(trailing_counts.get(c, 0) for c in customers) / len(customers)

    high_friction_avg = _avg_trailing(high_friction)
    clean_avg = _avg_trailing(clean)
    churn_correlation = {
        "high_friction_customers": len(high_friction),
        "clean_customers": len(clean),
        "high_friction_avg_trailing_activity": high_friction_avg,
        "clean_avg_trailing_activity": clean_avg,
        "high_friction_rate_vs_clean": (high_friction_avg / clean_avg) if clean_avg else None,
    }

    return {
        "total_customers": len(customer_ids),
        "repeat_contact_rate_pct": 100 * repeat_contact_customers / total,
        "escalation_rate_pct": 100 * escalation_customers / total,
        "dropoff_points": dropoff_points,
        "journey_shapes": journey_shapes,
        "churn_correlation": churn_correlation,
    }
