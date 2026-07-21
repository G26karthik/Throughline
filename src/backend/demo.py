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
    time.sleep(2)
    return result


def main():
    with httpx.Client() as client:
        step("1. Normal flow: seed in-policy + violating actions", lambda: client.post(f"{BASE}/seed").json())

        step(
            "2. Explicit over-cap action, blocked live",
            lambda: client.post(f"{BASE}/actions", json={
                "agent_id": "dispute_agent", "action_type": "issue_refund",
                "amount": 50000.0, "target_account": "acct-demo",
            }).json(),
        )

        step("3. Fleet-wide EMERGENCY STOP", lambda: client.post(f"{BASE}/fleet/halt").json())

        step(
            "3b. Any action now blocked fleet-wide",
            lambda: client.post(f"{BASE}/actions", json={
                "agent_id": "servicing_agent", "action_type": "reissue_card",
                "amount": 0.0, "target_account": "acct-demo",
            }).json(),
        )

        step("3c. Resume fleet (reset for next run)", lambda: client.post(f"{BASE}/fleet/resume").json())


if __name__ == "__main__":
    main()
