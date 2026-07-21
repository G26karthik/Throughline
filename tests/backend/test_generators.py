from src.backend.generators import generate_dataset, generate_trailing_activity, FRICTION_COUNT


def test_dataset_has_all_four_channels_populated():
    data = generate_dataset()
    assert len(data["app_events"]) > 0
    assert len(data["web_events"]) > 0
    assert len(data["callcenter_events"]) > 0
    assert len(data["inperson_events"]) > 0


def test_dataset_includes_shared_device_ambiguous_case():
    data = generate_dataset()
    devices = [e["device_id"] for e in data["app_events"]]
    assert devices.count("dev_shared_89") == 2  # two distinct customers, same device


def test_dataset_includes_unresolvable_orphan_case():
    data = generate_dataset()
    orphan_refs = [ref for ref, cust in data["ground_truth"].items() if cust is None]
    assert len(orphan_refs) == 1
    ref = orphan_refs[0]
    channel, idx = ref.split(":")
    event = data[channel][int(idx)]
    assert event["phone_number"] == "+1-555-9999"


def test_friction_distribution_has_both_buckets():
    high_friction = [c for c, n in FRICTION_COUNT.items() if n >= 2]
    clean = [c for c, n in FRICTION_COUNT.items() if n == 0]
    assert len(high_friction) >= 3
    assert len(clean) >= 3


def test_trailing_activity_thinner_for_high_friction_customers():
    events = generate_trailing_activity()
    counts = {}
    for e in events:
        counts[e["customer_id"]] = counts.get(e["customer_id"], 0) + 1

    high_friction_avg = sum(counts[c] for c in FRICTION_COUNT if FRICTION_COUNT[c] >= 2) / \
        len([c for c in FRICTION_COUNT if FRICTION_COUNT[c] >= 2])
    clean_avg = sum(counts[c] for c in FRICTION_COUNT if FRICTION_COUNT[c] == 0) / \
        len([c for c in FRICTION_COUNT if FRICTION_COUNT[c] == 0])

    assert high_friction_avg < clean_avg
