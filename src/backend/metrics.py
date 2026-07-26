"""Prometheus metrics for the resolution engine, pipeline, and API surface.

Two are point-in-time gauges recomputed on every seed/demo run (accuracy,
escalation rate); one is a real per-event histogram, not just an average
(pipeline insert latency); one is a request-volume counter via middleware.
"""
from prometheus_client import Counter, Gauge, Histogram

RESOLUTION_ACCURACY_PCT = Gauge(
    "throughline_resolution_accuracy_pct",
    "Identity resolution accuracy against ground truth on the most recent seed/demo run",
)

ESCALATION_RATE_PCT = Gauge(
    "throughline_escalation_rate_pct",
    "Percent of resolved customers with a detected escalation chain, most recent run",
)

PIPELINE_EVENT_LATENCY_MS = Histogram(
    "throughline_pipeline_event_latency_ms",
    "Per-event latency (resolve + store insert) through the stitching pipeline",
    buckets=(0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000),
)

HTTP_REQUESTS_TOTAL = Counter(
    "throughline_http_requests_total",
    "Total HTTP requests handled",
    ["method", "path", "status"],
)
