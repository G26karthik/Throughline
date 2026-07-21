"""Records the Phase 6 demo as a real browser session against the actual
running prototype. Requires both servers running:
    python -m uvicorn src.backend.main:app --port 8000
    (cd src/frontend && npm run dev)
Then: python video/record_demo.py

Pacing: the demo sequence is driven with a longer per-beat delay
(DELAY_SECONDS) than the dashboard's own "Run demo" button default (1.2s),
specifically so each of the five beats (scattered events, four live
resolutions, the unresolved case, the aggregate reveal) is individually
legible to someone watching cold, per the brief. On-screen captions are
injected into the live page (not added in post) so the pacing is
self-explanatory without narration.
"""
import threading

import httpx
from playwright.sync_api import sync_playwright

FRONTEND = "http://localhost:5173"
BACKEND = "http://localhost:8000"
DELAY_SECONDS = 2.2  # per-beat pacing, generous enough to read cold
CAPTION_HOLD_SECONDS = 1.6

CAPTION_JS = """
(text) => {
  let el = document.getElementById('demo-caption-overlay');
  if (!el) {
    el = document.createElement('div');
    el.id = 'demo-caption-overlay';
    el.style.position = 'fixed';
    el.style.left = '50%';
    el.style.bottom = '32px';
    el.style.transform = 'translateX(-50%)';
    el.style.background = '#1C1D1F';
    el.style.color = '#F7F7F5';
    el.style.font = '600 20px "IBM Plex Sans", sans-serif';
    el.style.padding = '14px 28px';
    el.style.borderRadius = '8px';
    el.style.zIndex = '9999';
    el.style.boxShadow = '0 8px 24px rgba(0,0,0,0.25)';
    document.body.appendChild(el);
  }
  el.textContent = text;
}
"""


def caption(page, text):
    page.evaluate(CAPTION_JS, text)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            record_video_dir="video/",
            record_video_size={"width": 1440, "height": 900},
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()

        page.goto(FRONTEND)
        page.wait_for_timeout(1200)
        caption(page, "Throughline: four disconnected channel events, before resolution")
        page.get_by_role("button", name="Resolution Demo").click()
        page.wait_for_timeout(1500)

        with httpx.Client(timeout=60.0) as client:
            # /demo/run only returns after the whole paced sequence finishes
            # server-side, so it has to run in the background - otherwise
            # our own wait_for_timeout/caption calls below would all fire
            # AFTER the visuals already finished, not alongside them.
            demo_thread = threading.Thread(
                target=lambda: client.post(f"{BACKEND}/demo/run", params={"delay_seconds": DELAY_SECONDS})
            )
            demo_thread.start()

            # Beat 1: four scattered events appear one at a time
            for i in range(4):
                page.wait_for_timeout(int(DELAY_SECONDS * 1000))
            caption(page, "Scattered events, resolving live into one identity...")
            page.wait_for_timeout(int(CAPTION_HOLD_SECONDS * 1000))

            # Beat 2: four resolved events, thread draws in
            for i in range(4):
                page.wait_for_timeout(int(DELAY_SECONDS * 1000))
            caption(page, "One resolved identity: cust_006, four channels, one thread")
            page.wait_for_timeout(int(CAPTION_HOLD_SECONDS * 1000))

            # Beat 3: the deliberately unresolved case
            page.wait_for_timeout(int(DELAY_SECONDS * 1000))
            caption(page, "An ambiguous case, correctly left unresolved — not force-matched")
            page.wait_for_timeout(int((DELAY_SECONDS + CAPTION_HOLD_SECONDS) * 1000))

            # Beat 4: aggregate reveal
            caption(page, "Aggregate view: ranked patterns across the full customer set")
            page.wait_for_timeout(int((DELAY_SECONDS + CAPTION_HOLD_SECONDS) * 1000))

            demo_thread.join(timeout=5)

        page.wait_for_timeout(2000)
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
