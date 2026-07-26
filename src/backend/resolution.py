"""Two-tier identity resolution: deterministic registry matching, then
scored probabilistic linkage for events that carry no hard identifier.

Deliberately rule-based, not ML - defensible and explainable in a pitch.
Below PROBABILISTIC_THRESHOLD, an event is left unresolved rather than
force-matched; that's a real, surfaced output, not a gap to hide.
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("throughline.resolution")

PROBABILISTIC_THRESHOLD = 0.5
TIME_WINDOW_SECONDS = 3600  # 1 hour full decay window for the time-proximity component
TIME_WEIGHT = 0.5
BEHAVIOR_WEIGHT = 0.3
BEHAVIOR_WINDOW_SECONDS = 1800  # 30 minutes

# Governance boundary: identity fields the resolution engine matches on are
# validated at the point they're read, not trusted from the raw channel
# payload. A field that fails validation is treated as absent (never used
# for matching) and the rejection itself is logged - the audit trail covers
# bad input the same way it covers every resolution decision.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[\d\-]{7,20}$")
CARD_LAST4_RE = re.compile(r"^\d{4}$")


def _validate(raw_ref: str, field: str, value: Optional[str], pattern: re.Pattern) -> Optional[str]:
    if value is None:
        return None
    if not pattern.match(value):
        logger.warning(json.dumps({
            "event": "identity_field_rejected", "raw_ref": raw_ref, "field": field,
        }))
        return None
    return value

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
        raw_ref = f"web_events:{i}"
        email = _validate(raw_ref, "email", e.get("email"), EMAIL_RE)
        keyed.append(KeyedEvent(raw_ref, "web_events", e["timestamp"], email, None, None, e["action"]))
    for i, e in enumerate(callcenter_events):
        raw_ref = f"callcenter_events:{i}"
        phone = _validate(raw_ref, "phone", e["phone_number"], PHONE_RE)
        keyed.append(KeyedEvent(raw_ref, "callcenter_events", e["timestamp"], None, phone, None, e["reason_code"]))
    for i, e in enumerate(inperson_events):
        raw_ref = f"inperson_events:{i}"
        card_last4 = _validate(raw_ref, "card_last4", e["card_last4"], CARD_LAST4_RE)
        keyed.append(KeyedEvent(raw_ref, "inperson_events", e["timestamp"], None, None, card_last4, "purchase"))
    return keyed


def _registry_lookup(event: KeyedEvent, registry: dict) -> tuple[Optional[str], Optional[str]]:
    """Returns (customer_id, matched_field) so the caller can log exactly
    which identifier drove a deterministic match."""
    for customer_id, ids in registry.items():
        if event.email and ids.get("email") == event.email:
            return customer_id, "email"
        if event.phone and ids.get("phone") == event.phone:
            return customer_id, "phone"
        if event.card_last4 and ids.get("card_last4") == event.card_last4:
            return customer_id, "card_last4"
    return None, None


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
        customer_id, matched_field = _registry_lookup(ev, registry)
        if customer_id:
            resolved[ev.raw_ref] = ResolvedEvent(ev.raw_ref, ev.channel, ev.timestamp, customer_id, 1.0, "deterministic")
            anchors.append((ev, customer_id))
            logger.info(json.dumps({
                "event": "resolution_decision", "raw_ref": ev.raw_ref, "method": "deterministic",
                "customer_id": customer_id, "matched_field": matched_field, "confidence": 1.0,
            }))
        else:
            unanchored.append(ev)

    for ev in unanchored:
        best_customer_id, best_score, best_anchor_ref = None, 0.0, None
        for anchor_ev, customer_id in anchors:
            score = _score(ev, anchor_ev)
            if score > best_score:
                best_score, best_customer_id, best_anchor_ref = score, customer_id, anchor_ev.raw_ref

        if best_customer_id and best_score >= PROBABILISTIC_THRESHOLD:
            resolved[ev.raw_ref] = ResolvedEvent(ev.raw_ref, ev.channel, ev.timestamp, best_customer_id, best_score, "probabilistic")
            logger.info(json.dumps({
                "event": "resolution_decision", "raw_ref": ev.raw_ref, "method": "probabilistic",
                "customer_id": best_customer_id, "anchor_ref": best_anchor_ref,
                "score": best_score, "threshold": PROBABILISTIC_THRESHOLD,
            }))
        else:
            resolved[ev.raw_ref] = ResolvedEvent(ev.raw_ref, ev.channel, ev.timestamp, None, best_score, "unresolved")
            logger.info(json.dumps({
                "event": "resolution_decision", "raw_ref": ev.raw_ref, "method": "unresolved",
                "customer_id": None, "best_score": best_score, "threshold": PROBABILISTIC_THRESHOLD,
            }))

    return resolved
