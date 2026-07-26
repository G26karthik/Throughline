"""Real streaming ingestion, consumer side: consumes throughline.raw-events
and feeds the existing stitching pipeline exactly as /seed does, just
sourced from Kafka/Redpanda instead of an in-process call. A gap of
IDLE_POLLS_FOR_BATCH_COMPLETE empty polls after activity is treated as one
completed batch (a full generated dataset lands in one producer flush).

Run standalone: python -m src.backend.streaming.consumer
"""
import json
import logging
import os

from confluent_kafka import Consumer

from src.backend.generators import CUSTOMER_REGISTRY, generate_trailing_activity
from src.backend.pipeline import run_pipeline
from src.backend.store import EventStore, get_connection

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("throughline.streaming.consumer")

TOPIC = "throughline.raw-events"
GROUP_ID = "throughline-pipeline"
IDLE_POLLS_FOR_BATCH_COMPLETE = 5


def _empty_batch() -> dict[str, list]:
    return {"app_events": [], "web_events": [], "callcenter_events": [], "inperson_events": []}


def _process_batch(batch: dict[str, list], store: EventStore) -> None:
    count = sum(len(v) for v in batch.values())
    result = run_pipeline(
        batch["app_events"], batch["web_events"], batch["callcenter_events"], batch["inperson_events"],
        CUSTOMER_REGISTRY, store,
    )
    activity = generate_trailing_activity()
    for i, e in enumerate(activity):
        store.insert(
            e["customer_id"], "trailing_activity", e["action"], e["timestamp"],
            1.0, "deterministic", f"trailing:{i}", "trailing activity ping",
        )
    logger.info(json.dumps({
        "event": "stream_batch_consumed", "raw_events": count, "inserted": result["inserted"],
    }))


def consume_forever() -> None:
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    store = EventStore(get_connection(os.environ["DATABASE_URL"]))

    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([TOPIC])
    logger.info(json.dumps({"event": "stream_consumer_started", "topic": TOPIC, "group_id": GROUP_ID}))

    batch = _empty_batch()
    idle_polls = 0
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                idle_polls += 1
                if idle_polls >= IDLE_POLLS_FOR_BATCH_COMPLETE and any(batch.values()):
                    _process_batch(batch, store)
                    batch = _empty_batch()
                    idle_polls = 0
                continue
            if msg.error():
                logger.warning(json.dumps({"event": "stream_consumer_error", "error": str(msg.error())}))
                continue

            idle_polls = 0
            value = json.loads(msg.value().decode("utf-8"))
            batch[value["channel"]].append(value["event"])
    finally:
        consumer.close()


if __name__ == "__main__":
    consume_forever()
