# Throughline

**Cross-Channel Journey Stitching** — an identity-resolution and event-stitching
platform that links a customer's fragmented interactions across app, web,
call-center, and in-person channels into one chronological timeline, flags
where a journey breaks down or can't be confidently resolved, and surfaces
cross-customer patterns correlated with repeat contact and churn.

**All data in this prototype is mocked/synthetic.** No real AmEx systems,
accounts, or customer data are involved anywhere in this codebase.

Built for AmEx CodeStreet 2026, theme: Cross-Channel Journey Stitching. See
`docs/proposal.md` for the full Round 1 submission and `docs/architecture.svg`
/ `docs/architecture.png` for the architecture diagram.

## Stack

- Backend: FastAPI + raw `sqlite3` (no ORM, no Postgres/Redis)
- Identity resolution: two-tier rule-based matching (deterministic registry
  lookup, then confidence-scored probabilistic linkage) — no ML, deliberately
  explainable
- Frontend: React 18 + Vite, WebSocket-driven live resolution demo
- Boring, auditable stack by design; see the proposal's scalability section
  for the production migration path (Kafka/Spark, Snowflake/BigQuery,
  Amplitude/Mixpanel)

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt

cd src/frontend
npm install
cd ../..
```

## Run

Needs Postgres reachable via `DATABASE_URL` -- easiest is `docker-compose up -d postgres`
(see "Local full-stack dev" below), then two processes in separate terminals from the repo root:

```bash
# Terminal 1: backend (FastAPI + WebSocket), port 8000
DATABASE_URL=postgresql://throughline:throughline@localhost:5432/throughline python -m uvicorn src.backend.main:app --port 8000

# Terminal 2: frontend dashboard, port 5173
cd src/frontend
npm run dev
```

Open `http://localhost:5173`. Use the nav to switch between **Journey
Timeline**, **Aggregate Patterns**, and **Resolution Demo**.

Seed the dataset first (either click through the UI or):

```bash
curl -X POST http://localhost:8000/seed
```

## Run the tests

Also needs Postgres reachable (`docker-compose up -d postgres` creates the
`throughline_test` database automatically via `docker/postgres/init.sql`):

```bash
python -m pytest tests/backend -v
```

33 tests covering the event generators, identity resolution engine (incl.
deliberately ambiguous cases), event store, stitching pipeline, journey
analytics, and the FastAPI/WebSocket integration.

## Run the Phase 6 demo sequence

With both servers running:

```bash
python -m src.backend.demo
```

This runs the exact sequence used for the pitch: four scattered channel
events resolve live into one identity, one deliberately ambiguous case
resolves honestly as `unresolved` instead of being force-matched, then the
aggregate pattern view reveals a real repeat-contact/churn correlation. Watch
it unfold on the **Resolution Demo** tab at `localhost:5173`, or trigger it
directly:

```bash
curl -X POST "http://localhost:8000/demo/run?delay_seconds=1.2"
```

## Regenerating the deliverables

**Architecture diagram** (`docs/architecture.mmd` → `.svg`/`.png`):

```bash
npx -y @mermaid-js/mermaid-cli -i docs/architecture.mmd -o docs/architecture.svg
npx -y @mermaid-js/mermaid-cli -i docs/architecture.mmd -o docs/architecture.png
```

**Dashboard screenshots** (used in the deck), with both servers running:

```bash
python deck/capture_screenshots.py
```

**Pitch deck** (`deck/Throughline_Deck.pptx`):

```bash
python deck/generate_deck.py
```

**Demo video** (`video/demo.webm`), with both servers already running:

```bash
playwright install chromium   # once
python video/record_demo.py
```

## Local full-stack dev (Postgres, Prometheus, Grafana, Redpanda)

```bash
docker-compose up -d --build
```

Brings up the app (`localhost:8000`, password in `DASHBOARD_PASSWORD`, default
`throughline-demo`), Postgres, Prometheus (`localhost:9090`), Grafana
(`localhost:3000`, admin/throughline), a Redpanda broker, Redpanda Console
(`localhost:8080`), and a `consumer` service continuously reading the
`throughline.raw-events` topic into the stitching pipeline. This is the full
stack described in the architecture diagram — the EC2 deploy below is
intentionally lighter (single container, sized for a free-tier instance) and
doesn't run any of this.

**Streaming ingestion** (real topic, real producer, real consumer -- an
alternative path into the same pipeline `/seed` uses in-process):

```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:19092 python -m src.backend.streaming.producer
```

Publishes one freshly-generated synthetic dataset (28 events) onto the topic;
the always-running `consumer` service picks it up, runs it through identity
resolution, and inserts the results into Postgres exactly like `/seed` does.
Inspect the topic and consumer lag:

```bash
docker exec ae-redpanda-1 rpk topic describe throughline.raw-events
docker exec ae-redpanda-1 rpk group describe throughline-pipeline
```

or visually at `localhost:8080` (Redpanda Console).

**AI analyst assistant** (needs `GEMINI_API_KEY` in `.env`; presentation layer
only, zero LLM involvement in resolution/analytics decisions):

```bash
POST /ai/summarize/{customer_id}   # plain-English narrative of a resolved journey
POST /ai/query {"question": "..."} # natural-language question over already-resolved data
```

## Deploying

`Dockerfile` builds the frontend and serves it + the API from one FastAPI
process on port 8000 (no CORS, single origin), and now requires a reachable
Postgres via `DATABASE_URL` — see `docker-compose.yml` for the full stack, or
point `DATABASE_URL` at any Postgres instance for a standalone `docker run`.
See `docs/DEPLOY_EC2.md` for a free-tier AWS EC2 walkthrough (that document's
own note explains why the live instance still runs the pre-Postgres image).

```bash
docker build -t throughline .
docker run -d -p 80:8000 -e DATABASE_URL=postgresql://user:pass@host:5432/db throughline
```

## Repo layout

```
/docs   proposal.md (Round 1 submission), architecture.mmd/.svg/.png
/deck   generate_deck.py, capture_screenshots.py, screenshots/, Throughline_Deck.pptx
/video  record_demo.py (Playwright, paced w/ on-screen captions), demo.webm
/src
  /backend   FastAPI app, generators, resolution engine, store, pipeline, analytics
  /frontend  React + Vite dashboard (journey timeline, aggregate view, resolution demo)
/tests/backend   pytest suite (33 tests)
```

## Measured results (not estimates)

Run against the live server via `time.perf_counter()`, same methodology
throughout:

- **Identity resolution accuracy:** 100% on the seeded set (28 events, 14
  customers), including both deliberately ambiguous cases — a shared-device
  pair and a true orphan phone number — correctly left `unresolved` rather
  than force-matched.
- **Pipeline latency:** ~6.28ms average per event, ingestion through
  placement on a resolved timeline (real SQLite file writes).
- **Pattern actionability:** 8 distinct ranked journey shapes surfaced from
  the seeded data; 3 concrete drop-off points identified; churn correlation
  shows customers with 2+ friction events return 5x less often than
  clean-journey customers.

See `docs/proposal.md` for full detail on how each metric was measured.

## Design notes

- Identity resolution is deliberately rule-based (deterministic + scored
  probabilistic), not ML — more defensible and explainable in a pitch, and
  every decision traces to a specific rule.
- Unresolved events are a first-class, surfaced output — shown directly in
  the UI, not hidden or force-matched away.
- Escalation-chain membership and unresolved status are two separate flags
  in the UI; an event can be one, the other, neither, or (implicitly) part
  of a resolved-but-non-escalating journey.
- Churn correlation is computed from timeline-derived friction, then crossed
  against independently-generated trailing-activity data — a real derived
  finding, not an asserted one.
