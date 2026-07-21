# CodeStreet 2026: Governance Layer for Financial Agents

A control plane that sits in front of a fleet of financial AI agents (dispute
resolution, benefit activation, servicing), enforces per-agent permissions and
spend caps in real time, keeps a full audit trail of every decision, and can
revoke a single agent or halt the entire fleet instantly.

**All data in this prototype is mocked/synthetic.** No real AmEx systems,
accounts, or transactions are involved anywhere in this codebase.

Built for AmEx CodeStreet 2026, theme: Governance Layer for Financial Agents
(cards & payments). See `docs/proposal.md` for the full Round 1 submission and
`docs/architecture.svg` / `docs/architecture.png` for the architecture diagram.

## Stack

- Backend: FastAPI + raw `sqlite3` (no ORM, no Postgres/Redis)
- Policy engine: plain dict of policies + a `check()` function (no OPA/rules DSL)
- Frontend: React 18 + Vite, WebSocket-fed live dashboard
- Recovery loop: from-scratch Reflexion-style block → log → retry-once → escalate

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

Two processes, in separate terminals, from the repo root:

```bash
# Terminal 1: backend (FastAPI + WebSocket), port 8000
uvicorn src.backend.main:app --port 8000

# Terminal 2: frontend dashboard, port 5173
cd src/frontend
npm run dev
```

Open `http://localhost:5173`.

## Run the tests

```bash
pytest tests/backend -v
```

24 tests covering the audit log, policy gateway, mock agents, recovery loop,
and the FastAPI/WebSocket integration.

## Run the Phase 6 demo sequence

With both servers running:

```bash
python -m src.backend.demo
```

This scripts the exact sequence used for the pitch: agents running normally
and getting approved → one agent fires an over-cap action and gets blocked
live with the specific reason → fleet-wide EMERGENCY STOP halts everything.
Watch the dashboard at `localhost:5173` while it runs.

You can also trigger the seeded scenario directly:

```bash
curl -X POST http://localhost:8000/seed
```

## Regenerating the deliverables

**Architecture diagram** (`docs/architecture.mmd` → `.svg`/`.png`):

```bash
npx -y @mermaid-js/mermaid-cli -i docs/architecture.mmd -o docs/architecture.svg
npx -y @mermaid-js/mermaid-cli -i docs/architecture.mmd -o docs/architecture.png
```

**Pitch deck** (`deck/CodeStreet_Governance_Deck.pptx`):

```bash
python deck/generate_deck.py
```

**Demo video** (`video/`), with both servers already running:

```bash
playwright install chromium   # once
python video/record_demo.py
```

## Repo layout

```
/docs   proposal.md (Round 1 submission), architecture.mmd/.svg/.png
/deck   generate_deck.py, CodeStreet_Governance_Deck.pptx
/video  record_demo.py (Playwright recording script)
/src
  /backend   FastAPI app, policy gateway, audit log, recovery loop, mock agents
  /frontend  React + Vite dashboard
/tests/backend   pytest suite (24 tests)
```

## Design notes

- Decision latency is stamped on every gateway check (`perf_counter` diff) and
  stored in the audit log — measured around 0.002ms per decision in local
  smoke testing, far under any reasonable "low-latency" bar.
- The Reflexion recovery loop is a fresh implementation, not adapted from an
  existing project — no local Hecta/AlgoSentinel Reflexion code was found to
  reuse for this build.
- The dashboard both monitors AND configures policy (edit an agent's spend
  cap, toggle a permission scope) — not just a read-only view.
