"""Two-tier identity resolution: deterministic registry matching, then
scored probabilistic linkage for events that carry no hard identifier.

Deliberately rule-based, not ML - defensible and explainable in a pitch.
Below PROBABILISTIC_THRESHOLD, an event is left unresolved rather than
force-matched; that's a real, surfaced output, not a gap to hide.
"""
from dataclasses import dataclass
from typing import Optional

PROBABILISTIC_THRESHOLD = 0.5
TIME_WINDOW_SECONDS = 3600  # 1 hour full decay window for the time-proximity component
TIME_WEIGHT = 0.5
BEHAVIOR_WEIGHT = 0.3
BEHAVIOR_WINDOW_SECONDS = 1800  # 30 minutes

# A "trigger" action followed (or preceded) by a "followup" action on
# another channel, within BEHAVIOR_WINDOW_SECONDS, is a recognized
# behavioral pattern (e.g. a failed checkout followed by a support contact).
TRIGGER_ACTIONS = {"fail_checkout", "submit_dispute"}
FOLLOWUP_ACTIONS = {
    "view_claim", "submit_dispute", "checkout_failure",
    "dispute_followup", "dispute_escalation", "purchase",
}


@dataclass
class KeyedEvent:
    raw_ref: str
    channel: str
    timestamp: float
    email: Optional[str]
    phone: Optional[str]
    card_last4: Optional[str]
    action: Optional[str]


@dataclass
class ResolvedEvent:
    raw_ref: str
    channel: str
    timestamp: float
    resolved_customer_id: Optional[str]
    confidence: float
    method: str  # "deterministic" | "probabilistic" | "unresolved"


def _extract_keyed_events(app_events, web_events, callcenter_events, inperson_events) -> list[KeyedEvent]:
    keyed = []
    for i, e in enumerate(app_events):
        keyed.append(KeyedEvent(f"app_events:{i}", "app_events", e["timestamp"], None, None, None, e["action"]))
    for i, e in enumerate(web_events):
        keyed.append(KeyedEvent(f"web_events:{i}", "web_events", e["timestamp"], e.get("email"), None, None, e["action"]))
    for i, e in enumerate(callcenter_events):
        keyed.append(KeyedEvent(
            f"callcenter_events:{i}", "callcenter_events", e["timestamp"],
            None, e["phone_number"], None, e["reason_code"],
        ))
    for i, e in enumerate(inperson_events):
        keyed.append(KeyedEvent(f"inperson_events:{i}", "inperson_events", e["timestamp"], None, None, e["card_last4"], "purchase"))
    return keyed


def _registry_lookup(event: KeyedEvent, registry: dict) -> Optional[str]:
    for customer_id, ids in registry.items():
        if event.email and ids.get("email") == event.email:
            return customer_id
        if event.phone and ids.get("phone") == event.phone:
            return customer_id
        if event.card_last4 and ids.get("card_last4") == event.card_last4:
            return customer_id
    return None


def _behavioral_score(a: KeyedEvent, b: KeyedEvent) -> float:
    dt = abs(a.timestamp - b.timestamp)
    if dt > BEHAVIOR_WINDOW_SECONDS:
        return 0.0
    if a.action in TRIGGER_ACTIONS and b.action in FOLLOWUP_ACTIONS:
        return BEHAVIOR_WEIGHT
    if b.action in TRIGGER_ACTIONS and a.action in FOLLOWUP_ACTIONS:
        return BEHAVIOR_WEIGHT
    return 0.0


def _time_score(a: KeyedEvent, b: KeyedEvent) -> float:
    dt = abs(a.timestamp - b.timestamp)
    return max(0.0, 1 - dt / TIME_WINDOW_SECONDS) * TIME_WEIGHT


def _score(u: KeyedEvent, anchor: KeyedEvent) -> float:
    return _time_score(u, anchor) + _behavioral_score(u, anchor)


def resolve_identities(app_events, web_events, callcenter_events, inperson_events, registry) -> dict[str, ResolvedEvent]:
    keyed = _extract_keyed_events(app_events, web_events, callcenter_events, inperson_events)

    resolved: dict[str, ResolvedEvent] = {}
    anchors: list[tuple[KeyedEvent, str]] = []
    unanchored: list[KeyedEvent] = []

    for ev in keyed:
        customer_id = _registry_lookup(ev, registry)
        if customer_id:
            resolved[ev.raw_ref] = ResolvedEvent(ev.raw_ref, ev.channel, ev.timestamp, customer_id, 1.0, "deterministic")
            anchors.append((ev, customer_id))
        else:
            unanchored.append(ev)

    for ev in unanchored:
        best_customer_id, best_score = None, 0.0
        for anchor_ev, customer_id in anchors:
            score = _score(ev, anchor_ev)
            if score > best_score:
                best_score, best_customer_id = score, customer_id

        if best_customer_id and best_score >= PROBABILISTIC_THRESHOLD:
            resolved[ev.raw_ref] = ResolvedEvent(ev.raw_ref, ev.channel, ev.timestamp, best_customer_id, best_score, "probabilistic")
        else:
            resolved[ev.raw_ref] = ResolvedEvent(ev.raw_ref, ev.channel, ev.timestamp, None, best_score, "unresolved")

    return resolved
