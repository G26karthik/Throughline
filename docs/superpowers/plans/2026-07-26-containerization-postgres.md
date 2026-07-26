# Containerization + Postgres Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring up the full stack (backend+frontend, Postgres, Prometheus, Grafana) with one `docker-compose up`, and replace SQLite with Postgres as the event store, with the existing 33 tests passing unchanged in behavior.

**Architecture:** The backend already serves the built frontend as static files from one FastAPI process (single-origin design, validated in the EC2 deploy). docker-compose keeps that: one `app` service (existing `Dockerfile`) plus `postgres`, `prometheus`, `grafana` as separate services. Postgres swap is a driver change only — `store.py`'s single `events` table and its method signatures don't change shape, only the connection/placeholder syntax (sqlite3 `?` → psycopg3 `%s`, `AUTOINCREMENT` → `SERIAL`).

**Tech Stack:** psycopg3 (`psycopg[binary]`), postgres:16-alpine, existing FastAPI/pytest stack.

## Global Constraints

- Storage swap only — do not change `events` table shape or add columns.
- Existing 33 tests in `tests/backend/` must pass against real Postgres, not sqlite `:memory:`.
- Local docker-compose is the new full-stack dev/evidence environment. The live EC2 instance (free-tier t2.micro, 1GB RAM) keeps running its already-built SQLite-based image untouched — it cannot fit this stack. Do not `git pull && docker build` on EC2 until a follow-up plan addresses that split explicitly.
- No dual sqlite/postgres mode, no feature flags — full replacement per CLAUDE.md "no backwards-compat shims."

---

### Task 1: Postgres-backed EventStore

**Files:**
- Modify: `src/backend/store.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `get_connection(database_url: str) -> psycopg.Connection`, `EventStore(conn)` with unchanged public methods: `insert(...) -> int`, `all_events() -> list[dict]`, `timeline_for_customer(customer_id) -> list[dict]`, `unresolved_events() -> list[dict]`, `known_customer_ids() -> list[str]`.

- [ ] **Step 1: Add psycopg to requirements.txt**

```
psycopg[binary]>=3.2.0
```

- [ ] **Step 2: Rewrite store.py for Postgres**

```python
"""Append-only canonical event store. Raw psycopg3, no ORM."""
import psycopg
from psycopg.rows import dict_row


def get_connection(database_url: str) -> psycopg.Connection:
    conn = psycopg.connect(database_url, row_factory=dict_row, autocommit=False)
    return conn


def init_db(conn: psycopg.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            customer_id TEXT,
            channel TEXT NOT NULL,
            action TEXT,
            timestamp DOUBLE PRECISION NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            method TEXT NOT NULL,
            raw_ref TEXT NOT NULL,
            detail TEXT
        )
    """)
    conn.commit()


class EventStore:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
        init_db(self.conn)

    def insert(self, customer_id, channel, action, timestamp, confidence, method, raw_ref, detail) -> int:
        cur = self.conn.execute(
            "INSERT INTO events (customer_id, channel, action, timestamp, confidence, method, raw_ref, detail) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (customer_id, channel, action, timestamp, confidence, method, raw_ref, detail),
        )
        row = cur.fetchone()
        self.conn.commit()
        assert row is not None
        return row["id"]

    def all_events(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM events ORDER BY timestamp ASC").fetchall()
        return [dict(r) for r in rows]

    def timeline_for_customer(self, customer_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE customer_id = %s ORDER BY timestamp ASC", (customer_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def unresolved_events(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE customer_id IS NULL ORDER BY timestamp ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def known_customer_ids(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT customer_id FROM events WHERE customer_id IS NOT NULL ORDER BY customer_id"
        ).fetchall()
        return [r["customer_id"] for r in rows]
```

- [ ] **Step 3: Commit**

```bash
git add src/backend/store.py requirements.txt
git commit -m "Swap SQLite for Postgres in event store"
```

---

### Task 2: Wire DATABASE_URL through main.py and Dockerfile

**Files:**
- Modify: `src/backend/main.py:44-45`
- Modify: `Dockerfile:11-18`

**Interfaces:**
- Consumes: `get_connection(database_url)` from Task 1.
- Produces: `create_app(db_path: str | None = None)` unchanged signature (param name kept for test-call-site compatibility — it's now a DSN, not a file path, but renaming it would touch `test_main.py`'s keyword arg for no behavioral gain).

- [ ] **Step 1: Update main.py's store construction**

In `src/backend/main.py`, change:
```python
def create_app(db_path: str | None = None) -> FastAPI:
    store = EventStore(get_connection(db_path or os.environ.get("DB_PATH", "throughline.db")))
```
to:
```python
def create_app(db_path: str | None = None) -> FastAPI:
    store = EventStore(get_connection(db_path or os.environ["DATABASE_URL"]))
```

- [ ] **Step 2: Update Dockerfile**

Change:
```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn[standard] websockets

COPY src/backend ./src/backend
COPY --from=frontend-build /app/src/frontend/dist ./src/frontend/dist

RUN mkdir -p /data
ENV DB_PATH=/data/throughline.db
EXPOSE 8000
```
to:
```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" websockets "psycopg[binary]"

COPY src/backend ./src/backend
COPY --from=frontend-build /app/src/frontend/dist ./src/frontend/dist

EXPOSE 8000
```
(Drop the `/data` mkdir and `DB_PATH` — Postgres persistence lives in its own container's volume now, `DATABASE_URL` comes from docker-compose's environment, not baked into the image.)

- [ ] **Step 3: Commit**

```bash
git add src/backend/main.py Dockerfile
git commit -m "Wire DATABASE_URL through app and Dockerfile"
```

---

### Task 3: Migrate test suite to Postgres

**Files:**
- Create: `tests/backend/conftest.py`
- Modify: `tests/backend/test_store.py`
- Modify: `tests/backend/test_pipeline.py`
- Modify: `tests/backend/test_analytics.py`
- Modify: `tests/backend/test_main.py`

**Interfaces:**
- Produces: `TEST_DATABASE_URL` constant, importable from `tests.backend.conftest`, and an autouse fixture that truncates `events` before every test (replaces sqlite `:memory:`'s implicit fresh-DB-per-test behavior).

- [ ] **Step 1: Create conftest.py**

```python
import os

import pytest

from src.backend.store import get_connection

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://throughline:throughline@localhost:5432/throughline_test"
)


@pytest.fixture(autouse=True)
def _clean_events_table():
    conn = get_connection(TEST_DATABASE_URL)
    conn.execute("CREATE TABLE IF NOT EXISTS events (id SERIAL PRIMARY KEY)")  # no-op if EventStore already ran
    conn.execute("TRUNCATE TABLE events RESTART IDENTITY")
    conn.commit()
    conn.close()
    yield
```

- [ ] **Step 2: Replace `:memory:` call sites**

In `tests/backend/test_store.py`, `tests/backend/test_pipeline.py`, `tests/backend/test_analytics.py`, add the import:
```python
from tests.backend.conftest import TEST_DATABASE_URL
```
and replace every `get_connection(":memory:")` with `get_connection(TEST_DATABASE_URL)`.

In `tests/backend/test_main.py`, add the same import and replace:
```python
app = create_app(db_path=":memory:")
```
with:
```python
app = create_app(db_path=TEST_DATABASE_URL)
```

- [ ] **Step 3: Start a local Postgres for the test run**

```bash
docker run -d --name throughline-test-pg -e POSTGRES_USER=throughline -e POSTGRES_PASSWORD=throughline -e POSTGRES_DB=throughline_test -p 5432:5432 postgres:16-alpine
```

- [ ] **Step 4: Run the full suite**

```bash
pytest tests/backend -v
```
Expected: 33 passed (same count as before the migration — this confirms the storage swap changed nothing observable).

- [ ] **Step 5: Tear down the throwaway Postgres**

```bash
docker rm -f throughline-test-pg
```

- [ ] **Step 6: Commit**

```bash
git add tests/backend/conftest.py tests/backend/test_store.py tests/backend/test_pipeline.py tests/backend/test_analytics.py tests/backend/test_main.py
git commit -m "Migrate test suite from sqlite :memory: to Postgres"
```

---

### Task 4: docker-compose stack (app, postgres, prometheus, grafana)

**Files:**
- Create: `docker-compose.yml`
- Create: `docker/postgres/init.sql`
- Create: `docker/prometheus/prometheus.yml`
- Create: `docker/grafana/provisioning/datasources/prometheus.yml`
- Create: `.env.example`

**Interfaces:**
- Consumes: `Dockerfile` (Task 2), `DATABASE_URL` env var (Task 2).
- Produces: `docker-compose up` starts all four services; `app` reachable at `localhost:8000`, `grafana` at `localhost:3000`, `prometheus` at `localhost:9090`.

- [ ] **Step 1: Postgres init script (creates the test database alongside the app one)**

```sql
CREATE DATABASE throughline_test;
```

- [ ] **Step 2: Prometheus scrape config (target wired now, `/metrics` endpoint itself lands in the observability plan)**

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: throughline-backend
    static_configs:
      - targets: ["app:8000"]
```

- [ ] **Step 3: Grafana datasource provisioning**

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

- [ ] **Step 4: docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: throughline
      POSTGRES_PASSWORD: throughline
      POSTGRES_DB: throughline
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U throughline"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: .
    environment:
      DATABASE_URL: postgresql://throughline:throughline@postgres:5432/throughline
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy

  prometheus:
    image: prom/prometheus:v2.55.1
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:11.3.0
    environment:
      GF_SECURITY_ADMIN_PASSWORD: throughline
    volumes:
      - ./docker/grafana/provisioning:/etc/grafana/provisioning
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

volumes:
  postgres_data:
  grafana_data:
```

- [ ] **Step 5: .env.example (documents what a fresh clone needs, nothing secret committed)**

```
DATABASE_URL=postgresql://throughline:throughline@postgres:5432/throughline
```

- [ ] **Step 6: Bring the stack up and verify**

```bash
docker-compose up -d --build
docker-compose ps
curl http://localhost:8000/health
curl -X POST http://localhost:8000/seed
curl http://localhost:8000/customers
```
Expected: `/health` returns `{"status":"ok"}`, `/seed` succeeds, `/customers` returns the seeded 14 customers.

- [ ] **Step 7: Verify Postgres persistence across a restart**

```bash
docker-compose restart app
curl http://localhost:8000/customers
```
Expected: same customer data as before the restart (proves Postgres, not an in-memory or ephemeral store, is backing it).

- [ ] **Step 8: Commit**

```bash
git add docker-compose.yml docker/ .env.example
git commit -m "Add docker-compose stack: app, postgres, prometheus, grafana"
```

---

### Task 5: Document the new dev/deploy split

**Files:**
- Modify: `README.md`
- Modify: `docs/DEPLOY_EC2.md`

**Interfaces:**
- None (docs only).

- [ ] **Step 1: Add a "Local full-stack dev" section to README.md, above "## Deploying"**

```markdown
## Local full-stack dev (Postgres, Prometheus, Grafana)

```bash
docker-compose up -d --build
```

Brings up the app (`localhost:8000`), Postgres, Prometheus (`localhost:9090`), and
Grafana (`localhost:3000`, admin/throughline). This is the full stack described in
the architecture diagram — the EC2 deploy below is intentionally lighter (single
container, SQLite-free-tier-sized) and doesn't run Postgres/Prometheus/Grafana.
```

- [ ] **Step 2: Add a note at the top of docs/DEPLOY_EC2.md**

```markdown
> **Note:** this document describes the original single-container SQLite deploy,
> still what the live instance runs. The app now requires Postgres
> (`DATABASE_URL`), so don't `git pull && docker build` on this instance without
> also standing up Postgres there — see `docker-compose.yml` for the full stack,
> which needs more RAM than this instance's free-tier t2.micro has. Redeploying
> the current stack to EC2 is a follow-up decision, not yet done.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/DEPLOY_EC2.md
git commit -m "Document docker-compose dev stack and EC2 deploy-freeze note"
```

---

## Self-Review

**Spec coverage:** Item 1 (containerization) → Task 4. Item 2 (Postgres migration, keep schema, 33 tests pass) → Tasks 1-3. Deployment-continuity concern (don't build in isolation from AWS work) → Task 5 + Global Constraints.

**Placeholder scan:** none found — every step has real code/commands.

**Type consistency:** `get_connection(database_url: str)` and `EventStore(conn)` signatures match across Tasks 1-3. `TEST_DATABASE_URL` name matches between its definition (Task 3 Step 1) and every import site (Task 3 Step 2).
