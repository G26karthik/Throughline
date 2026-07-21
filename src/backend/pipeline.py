"""Normalizes raw per-channel events into the canonical event shape and
stitches them onto resolved-identity timelines in the event store.
"""
import time

from src.backend.resolution import resolve_identities
from src.backend.store import EventStore


def _detail_for(channel: str, raw_event: dict) -> str:
    if channel == "app_events":
        return f"{raw_event['action']} (device {raw_event['device_id']})"
    if channel == "web_events":
        email = raw_event.get("email")
        return f"{raw_event['action']}" + (f" ({email})" if email else " (anonymous session)")
    if channel == "callcenter_events":
        return f"{raw_event['reason_code']} - case {raw_event['case_id']}"
    if channel == "inperson_events":
        return f"{raw_event['merchant']} ${raw_event['amount']:.2f}"
    return ""


def run_pipeline(app_events, web_events, callcenter_events, inperson_events, registry, store: EventStore) -> dict:
    channel_lookup = {
        "app_events": app_events,
        "web_events": web_events,
        "callcenter_events": callcenter_events,
        "inperson_events": inperson_events,
    }

    start = time.perf_counter()
    resolved = resolve_identities(app_events, web_events, callcenter_events, inperson_events, registry)

    inserted = 0
    for raw_ref, r in resolved.items():
        channel, idx_str = raw_ref.split(":")
        raw_event = channel_lookup[channel][int(idx_str)]
        store.insert(
            r.resolved_customer_id, r.channel, raw_event.get("action") or raw_event.get("reason_code"),
            r.timestamp, r.confidence, r.method, raw_ref, _detail_for(channel, raw_event),
        )
        inserted += 1
    pipeline_latency_ms = (time.perf_counter() - start) * 1000

    return {
        "inserted": inserted,
        "resolved": resolved,
        "pipeline_latency_ms": pipeline_latency_ms,
        "avg_latency_per_event_ms": pipeline_latency_ms / inserted if inserted else 0.0,
    }
