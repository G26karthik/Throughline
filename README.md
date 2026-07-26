# Throughline

**Cross-Channel Journey Stitching** — an identity-resolution and event-stitching
platform that links a customer's fragmented interactions across app, web,
call-center, and in-person channels into one chronological timeline, flags
where a journey breaks down or can't be confidently resolved, and surfaces
cross-customer patterns correlated with repeat contact and churn.

**All data in this prototype is mocked/synthetic.** No real AmEx systems,
accounts, or customer data are involved anywhere in this codebase.

Built for AmEx CodeStreet 2026, theme: Cross-Channel Journey Stitching. See
`docs/proposal.md` for the full Round 1 submission. The diagram below is
generated from `docs/architecture.mmd` (source of truth — regenerate the
`.svg`/`.png` copies from it, see "Regenerating the deliverables").

## Architecture

```mermaid
flowchart TD
    subgraph CH["Channel Generators (mocked, deterministic)"]
        APP["app_events\n(device_id - weak signal)"]
        WEB["web_events\n(email - hard identifier)"]
        CALL["callcenter_events\n(phone - hard identifier)"]
        INP["inperson_events\n(card_last4 - hard identifier)"]
    end

    subgraph STREAM["Streaming Ingestion (Redpanda) - alternative real path"]
        PROD["Producer\nthroughline.raw-events topic"]
        CONS["Consumer\n(idle-gap batching)"]
    end

    subgraph RES["Identity Resolution Engine (resolution.py)"]
        VALID["Field validation\n(email / phone / card_last4)\nmalformed -> rejected + logged"]
        DET["Tier 1: Deterministic\nregistry lookup\n(exact email / phone / card_last4)"]
        PROB["Tier 2: Probabilistic scoring\ntime-proximity decay (1hr window)\n+ behavioral-pattern bonus\n(fail_checkout / submit_dispute -> follow-up within 30min)"]
        THRESH{{"score >= 0.5 ?"}}
        UNRES["Left unresolved\n(never force-matched)"]
        LOG["Structured decision log\n(method, matched field/score, threshold)"]
    end

    subgraph PIPE["Stitching Pipeline (pipeline.py)"]
        NORM["Normalize + stitch onto\nresolved-identity timelines"]
        LAT["Per-event latency\n(histogram, not just average)"]
    end

    STORE[("Canonical Event Store\nPostgres, audit-style\ncustomer_id, channel, action,\ntimestamp, confidence, method, raw_ref, detail")]

    subgraph ANALYTICS["Analytics Layer (analytics.py)"]
        REPEAT["Repeat-contact detection"]
        ESC["Escalation-chain detection\n(3+ channels within 1hr)"]
        DROP["Drop-off detection\n(fail_checkout / submit_dispute,\nno follow-up within 30min)"]
        CHURN["Churn correlation\n(friction vs. trailing activity)"]
    end

    subgraph AI["AI Analyst Assistant (Gemini) - presentation only"]
        SUMM["NL journey summary"]
        NLQ["NL query over resolved data"]
    end

    subgraph OBS["Observability"]
        PROM["Prometheus\n/metrics: accuracy, escalation rate,\nlatency histogram, request volume"]
        GRAF["Grafana dashboard"]
    end

    SNOW[("Snowflake\none-way batch mirror,\nrun manually - not scheduled")]

    GATE{"Access gate\n(shared password -> session token,\noptional per deployment)"}

    subgraph DASH["Dashboard"]
        TIMELINE["Single-customer\ntimeline view"]
        AGGVIEW["Aggregate pattern view\n(unresolved cases, journey shapes,\nchurn signal)"]
    end

    APP --> VALID
    WEB --> VALID
    CALL --> VALID
    INP --> VALID

    APP -.->|"or produce"| PROD
    WEB -.->|"or produce"| PROD
    CALL -.->|"or produce"| PROD
    INP -.->|"or produce"| PROD
    PROD -.-> CONS
    CONS -.->|"same pipeline, sourced from Kafka/Redpanda"| VALID

    VALID --> DET
    DET -->|"hard identifier matched"| NORM
    DET -->|"no hard identifier"| PROB
    PROB --> THRESH
    THRESH -->|"yes"| NORM
    THRESH -->|"no"| UNRES
    UNRES --> STORE
    DET --> LOG
    PROB --> LOG
    UNRES --> LOG

    NORM --> LAT
    LAT --> STORE
    LAT --> ANALYTICS
    LAT --> PROM

    STORE --> REPEAT
    STORE --> ESC
    STORE --> DROP
    STORE --> CHURN

    STORE --> SUMM
    ANALYTICS --> NLQ

    PROM --> GRAF
    STORE -.->|"manual export"| SNOW

    GATE --> DASH
    STORE --> TIMELINE
    REPEAT --> AGGVIEW
    ESC --> AGGVIEW
    DROP --> AGGVIEW
    CHURN --> AGGVIEW
    SUMM --> DASH
    NLQ --> DASH
```

Solid arrows are the always-on path (in-process generation → validation →
resolution → Postgres → analytics/dashboard). Dashed arrows are additive,
optional paths: streaming ingestion via Redpanda, and the Snowflake mirror.
The AI assistant and observability layers only ever read already-computed
data — neither can affect a resolution decision.

## Stack

- Backend: FastAPI + Postgres (raw `psycopg`, no ORM)
- Identity resolution: two-tier rule-based matching (deterministic registry
  lookup, then confidence-scored probabilistic linkage) — no ML, deliberately
  explainable; zero LLM involvement in resolution decisions
- Streaming ingestion: Redpanda (Kafka-API compatible) — a real topic,
  producer, and consumer feed the same stitching pipeline `/seed` uses
  in-process, as an alternative real path, not a replacement
- Observability: Prometheus (resolution accuracy, escalation rate, pipeline
  latency histogram, request volume) + a provisioned Grafana dashboard
- AI analyst assistant: Gemini-powered natural-language journey summaries
  and NL queries, strictly a presentation layer over already-resolved data
- CI: GitHub Actions runs the full test suite (with a real Postgres service
  container) on every push
- Access gate: shared-password session auth in front of the analyst
  dashboard; `/health` and `/metrics` stay open for probes/scraping
- Warehouse mirror: one-way batch export from Postgres to Snowflake for
  analytical workloads — Postgres stays the primary/canonical store
- Frontend: React 18 + Vite, WebSocket-driven live resolution demo
- Boring, auditable stack by design; see the proposal's scalability section
  for what's built vs. still forward-looking (Amplitude/Mixpanel downstream)

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

36 tests covering the event generators, identity resolution engine (incl.
deliberately ambiguous cases), event store, stitching pipeline, journey
analytics, and the FastAPI/WebSocket integration — including the access
gate's reject/accept/disabled paths and the AI assistant's unconfigured
guard. Run against a real Postgres, including in CI, not sqlite `:memory:`.

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
`throughline-demo` — leave it unset/empty in `.env` to disable the gate
entirely, e.g. for a public demo deployment), Postgres, Prometheus (`localhost:9090`), Grafana
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

**Snowflake warehouse mirror** (needs the six `SNOWFLAKE_*` vars in `.env`;
one-way batch export, Postgres stays the primary/canonical store):

```bash
python -m src.backend.warehouse.snowflake_mirror
```

Creates the database/schema/table if they don't exist, truncates and reloads
the full `EVENTS` mirror from Postgres. Snowflake enforces MFA on password
auth for human users -- generate a Personal Access Token (Snowsight ->
Admin -> Users & Roles -> your user -> Programmatic access tokens) and use
that as `SNOWFLAKE_PASSWORD` instead of your login password.

## Deploying

**Live right now:** [`http://18.60.216.62/`](http://18.60.216.62/) — AWS EC2
free-tier `t2.micro`, running the current codebase (Postgres, access gate,
AI assistant) via `docker-compose up -d postgres app`. The access gate is
switched off on this specific deployment (`DASHBOARD_PASSWORD` left empty)
so the link is directly usable — see `docs/DEPLOY_EC2.md` for exactly how
it's set up and why the heavier services (Redpanda/Prometheus/Grafana)
aren't part of this deployment.

`Dockerfile` builds the frontend and serves it + the API from one FastAPI
process on port 8000 (no CORS, single origin), and requires a reachable
Postgres via `DATABASE_URL` — see `docker-compose.yml` for the full stack, or
point `DATABASE_URL` at any Postgres instance for a standalone `docker run`.

```bash
docker build -t throughline .
docker run -d -p 80:8000 -e DATABASE_URL=postgresql://user:pass@host:5432/db throughline
```

## Repo layout

```
/.github/workflows   tests.yml (CI: pytest against a real Postgres service container)
/docs   proposal.md (Round 1 submission), DEPLOY_EC2.md, architecture.mmd/.svg/.png
/deck   generate_deck.py, capture_screenshots.py, screenshots/, Throughline_Deck.pptx
/video  record_demo.py (Playwright, paced w/ on-screen captions), demo.webm
/docker prometheus.yml, grafana provisioning (datasource + dashboard), postgres init.sql
/src
  /backend
    main.py           FastAPI app: routes, auth gate, lifespan/auto-seed
    resolution.py      identity resolution engine (validation + 2-tier matching)
    pipeline.py        stitching pipeline (normalize, insert, per-event latency)
    store.py           Postgres event store (psycopg3, no ORM)
    analytics.py        repeat-contact / escalation / drop-off / churn detection
    generators.py       synthetic multi-channel dataset generator
    metrics.py          Prometheus metric definitions
    ai_assistant.py      Gemini-backed NL summary/query, presentation layer only
    /streaming          Redpanda producer.py / consumer.py
    /warehouse          snowflake_mirror.py (one-way Postgres -> Snowflake batch export)
  /frontend  React + Vite dashboard (login screen, journey timeline, aggregate view, resolution demo)
docker-compose.yml      app, postgres, prometheus, grafana, redpanda, redpanda-console, consumer
/tests/backend   pytest suite (36 tests), run against real Postgres in CI
```

## Measured results (not estimates)

Re-measured against the live local stack (Postgres, not the original SQLite),
same 28-event / 13-resolved-customer seeded scenario used throughout:

- **Identity resolution accuracy:** 100% on the seeded set, including both
  deliberately ambiguous cases — a shared-device pair and a true orphan
  phone number — correctly left `unresolved` rather than force-matched.
- **Pipeline latency:** varies by run/system load with Postgres in the loop
  — observed 2.6ms-7.3ms average per event across consecutive runs on the
  same machine. Not a single fixed number; re-run `/seed` and read
  `avg_latency_per_event_ms` for a fresh figure, or watch the histogram live
  in Grafana.
- **Pattern actionability:** 8 distinct ranked journey shapes surfaced from
  the seeded data; 3 concrete drop-off points identified; churn correlation
  shows high-friction customers average 1.0 trailing-activity events vs. 5.0
  for clean customers — a 5x gap, re-confirmed on a fresh, truncated-then-
  reseeded run.
- **No larger synthetic run has been done.** Every number above is on the
  original fixed 28-event scenario, not a stress test.

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
