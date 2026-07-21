"""Records the Phase 6 demo as a real browser session. Requires both servers running:
    uvicorn src.backend.main:app --port 8000
    (cd src/frontend && npm run dev)
Then: python video/record_demo.py
"""
import time

import httpx
from playwright.sync_api import sync_playwright

FRONTEND = "http://localhost:5173"
BACKEND = "http://localhost:8000"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(record_video_dir="video/", record_video_size={"width": 1280, "height": 800})
        page = context.new_page()
        page.goto(FRONTEND)
        page.wait_for_timeout(2000)

        with httpx.Client() as client:
            client.post(f"{BACKEND}/seed")
            page.wait_for_timeout(3000)

            client.post(f"{BACKEND}/actions", json={
                "agent_id": "dispute_agent", "action_type": "issue_refund",
                "amount": 50000.0, "target_account": "acct-demo",
            })
            page.wait_for_timeout(3000)

        estop = page.get_by_text("EMERGENCY STOP", exact=False)
        estop.click()
        page.wait_for_timeout(3000)

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
