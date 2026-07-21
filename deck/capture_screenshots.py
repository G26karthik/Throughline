"""Captures screenshots of both dashboard views for the pitch deck. Requires
both servers running:
    python -m uvicorn src.backend.main:app --port 8000
    (cd src/frontend && npm run dev)
Then: python deck/capture_screenshots.py
"""
import time

import httpx
from playwright.sync_api import sync_playwright

FRONTEND = "http://localhost:5173"
BACKEND = "http://localhost:8000"


def main():
    with httpx.Client() as client:
        client.post(f"{BACKEND}/seed")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(FRONTEND)
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Journey Timeline").click()
        page.wait_for_timeout(500)
        page.get_by_text("cust_006", exact=True).click()
        page.wait_for_timeout(1000)
        page.screenshot(path="deck/screenshots/journey_timeline.png")

        page.get_by_role("button", name="Aggregate Patterns").click()
        page.wait_for_timeout(1000)
        page.screenshot(path="deck/screenshots/aggregate_patterns.png")

        browser.close()


if __name__ == "__main__":
    main()
