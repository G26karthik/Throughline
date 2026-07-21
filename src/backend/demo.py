"""Runs the Phase 6 demo sequence against a live server. Start the server first:
    uvicorn src.backend.main:app --port 8000
Then run:
    python -m src.backend.demo
"""
import time

import httpx

BASE = "http://localhost:8000"


def step(label: str, fn):
    print(f"\n=== {label} ===")
    result = fn()
    print(result)
    time.sleep(1.5)
    return result


def main():
    with httpx.Client(timeout=30.0) as client:
        step(
            "Run the Phase 6 sequence (scattered -> live resolution -> unresolved case -> aggregate reveal)",
            lambda: client.post(f"{BASE}/demo/run", params={"delay_seconds": 1.2}).json(),
        )
        step("Fetch the aggregate pattern view", lambda: client.get(f"{BASE}/aggregate").json())
        step("Fetch cust_006's resolved timeline (the escalation chain)", lambda: client.get(f"{BASE}/timeline/cust_006").json())
        step("Fetch the unresolved events (orphan + weak-signal shared device)", lambda: client.get(f"{BASE}/unresolved").json())


if __name__ == "__main__":
    main()
