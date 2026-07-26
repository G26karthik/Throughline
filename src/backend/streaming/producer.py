"""Real streaming ingestion, producer side: publishes a synthetic
multi-channel dataset onto a Redpanda/Kafka topic, one event per message,
instead of feeding the pipeline in-process. Demonstrates the theme's own
reference-stack migration path rather than just claiming it.

Run standalone: python -m src.backend.streaming.producer
"""
import json
import os

from confluent_kafka import Producer

from src.backend.generators import generate_dataset

TOPIC = "throughline.raw-events"


def produce() -> int:
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    producer = Producer({"bootstrap.servers": bootstrap})

    data = generate_dataset()
    sent = 0
    for channel in ("app_events", "web_events", "callcenter_events", "inperson_events"):
        for event in data[channel]:
            producer.produce(TOPIC, json.dumps({"channel": channel, "event": event}).encode("utf-8"))
            sent += 1
    producer.flush()
    print(f"produced {sent} events to {TOPIC}")
    return sent


if __name__ == "__main__":
    produce()
