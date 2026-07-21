# CodeStreet 2026 Governance Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a control-plane prototype (mock agents -> policy gateway -> audit log -> Reflexion recovery -> FastAPI/WS -> React dashboard) plus the 4 hackathon deliverables (proposal, deck, architecture diagram, demo video).

**Architecture:** See `docs/superpowers/specs/2026-07-21-codestreet-governance-layer-design.md`. Backend is FastAPI + raw `sqlite3`, no ORM. Frontend is React + Vite, WebSocket-fed. Dashboard both monitors and configures policy (edit spend cap / toggle permission scope), per AmEx's Round 1 task list.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, sqlite3 (stdlib), pytest, React 18, Vite, python-pptx, Playwright (video capture), mermaid (diagram source).

## Global Constraints

- Raw `sqlite3`, no ORM, no Postgres/Redis (brief constraint).
- Policy engine is a plain dict of policies + a `check()` function — no OPA/rules DSL.
- All data mocked/synthetic — label as such everywhere it's user-visible (README, proposal, dashboard footer).
- Favor a working vertical slice over broad shallow features — build backend fully before frontend polish.
- No local Hecta/AlgoSentinel Reflexion code exists (checked) — recovery loop below is the from-scratch implementation, documented as such in the proposal.
- Decision latency (`perf_counter` diff around `PolicyGateway.check`) must be stamped on every audit row — feeds the "sub-5ms policy decision" success metric.

---

## File Structure

```
src/backend/
  __init__.py
  gateway.py      PolicyGateway, Action, Decision, DEFAULT_POLICIES
  audit.py        AuditLog, get_connection, init_db
  agents.py       ScriptedAction, {dispute,benefit,servicing}_agent_actions, all_scripted_actions
  recovery.py     Recovery (retry-once / escalate)
  main.py         FastAPI app, REST routes, WebSocket /ws, ConnectionManager
  demo.py         Phase 6 demo sequence, runs against a live server via HTTP
tests/backend/
  test_gateway.py
  test_audit.py
  test_agents.py
  test_recovery.py
  test_main.py
src/frontend/
  package.json, vite.config.js, index.html
  src/main.jsx, src/App.jsx, src/api.js, src/styles.css
  src/components/LiveFeed.jsx
  src/components/SpendMeter.jsx
  src/components/AgentControls.jsx   (revoke + policy config form)
  src/components/EmergencyStop.jsx
docs/
  architecture.mmd, architecture.svg
  proposal.md
deck/
  generate_deck.py -> CodeStreet_Governance_Deck.pptx
video/
  record_demo.py -> demo.webm
README.md
.gitignore
```

---

## Task 1: Repo scaffold + .gitignore + baseline commit

**Files:**
- Create: `.gitignore`
- Create: `src/backend/__init__.py` (empty)
- Create: `requirements.txt`

**Interfaces:**
- Produces: `requirements.txt` pins used by every later backend task.

- [ ] **Step 1: Write `.gitignore`**

```
__pycache__/
*.pyc
.venv/
venv/
node_modules/
dist/
*.db
.pytest_cache/
video/*.webm
video/*.mp4
```

- [ ] **Step 2: Write `requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
pytest==8.3.3
httpx==0.27.2
python-pptx==1.0.2
playwright==1.47.0
websockets==13.1
```

- [ ] **Step 3: Create `src/backend/__init__.py`** (empty file, makes `src.backend` a package)

- [ ] **Step 4: Install deps and verify**

Run: `pip install -r requirements.txt`
Expected: installs without error.

- [ ] **Step 5: Commit**

```bash
git add .gitignore requirements.txt src/backend/__init__.py CLAUDE.md
git commit -m "chore: scaffold backend package, deps, gitignore"
```

---

## Task 2: Audit log module

**Files:**
- Create: `src/backend/audit.py`
- Test: `tests/backend/test_audit.py`

**Interfaces:**
- Produces: `get_connection(db_path=":memory:") -> sqlite3.Connection`, `init_db(conn)`,
  `class AuditLog: __init__(self, conn); record(agent_id, action_type, amount, target_account, decision, reason, latency_ms) -> int; list(limit=200) -> list[dict]`.
  Also creates `escalations` table (used by Task 5's `Recovery`).

- [ ] **Step 1: Write failing test**

```python
# tests/backend/test_audit.py
from src.backend.audit import get_connection, AuditLog

def test_record_and_list_roundtrip():
    conn = get_connection(":memory:")
    log = AuditLog(conn)
    row_id = log.record("dispute_agent", "issue_refund", 120.0, "acct-1", "allow", "ok", 0.42)
    assert row_id == 1
    rows = log.list()
    assert len(rows) == 1
    assert rows[0]["agent_id"] == "dispute_agent"
    assert rows[0]["decision"] == "allow"
    assert rows[0]["reason"] == "ok"
    assert rows[0]["latency_ms"] == 0.42

def test_list_orders_newest_first():
    conn = get_connection(":memory:")
    log = AuditLog(conn)
    log.record("a", "x", 1.0, "acct", "allow", "ok", 0.1)
    log.record("b", "y", 2.0, "acct", "block", "no", 0.2)
    rows = log.list()
    assert [r["agent_id"] for r in rows] == ["b", "a"]

def test_escalations_table_exists():
    conn = get_connection(":memory:")
    AuditLog(conn)
    conn.execute("INSERT INTO escalations (ts, agent_id, action_type, amount, target_account, reason, resolved) VALUES (0,'a','x',1.0,'acct','why',0)")
    row = conn.execute("SELECT * FROM escalations").fetchone()
    assert row["agent_id"] == "a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_audit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.backend.audit'`

- [ ] **Step 3: Implement**

```python
# src/backend/audit.py
import sqlite3
import time

def get_connection(db_path: str = "governance.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            agent_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            amount REAL,
            target_account TEXT,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            latency_ms REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            agent_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            amount REAL,
            target_account TEXT,
            reason TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()

class AuditLog:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        init_db(self.conn)

    def record(self, agent_id: str, action_type: str, amount: float, target_account: str,
               decision: str, reason: str, latency_ms: float) -> int:
        cur = self.conn.execute(
            "INSERT INTO audit_log (ts, agent_id, action_type, amount, target_account, decision, reason, latency_ms) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (time.time(), agent_id, action_type, amount, target_account, decision, reason, latency_ms),
        )
        self.conn.commit()
        return cur.lastrowid

    def list(self, limit: int = 200) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_audit.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/backend/audit.py tests/backend/test_audit.py
git commit -m "feat: add append-only SQLite audit log"
```

---

## Task 3: Policy gateway

**Files:**
- Create: `src/backend/gateway.py`
- Test: `tests/backend/test_gateway.py`

**Interfaces:**
- Consumes: nothing (pure in-memory, no DB dependency).
- Produces: `Action(agent_id, action_type, amount=0.0, target_account="")`,
  `Decision(allowed: bool, reason: str, latency_ms: float)`,
  `DEFAULT_POLICIES: dict`,
  `class PolicyGateway: check(action) -> Decision; revoke(agent_id); unrevoke(agent_id); halt_fleet(); resume_fleet(); set_spend_cap(agent_id, cap); toggle_permission(agent_id, action_type)`.
  `main.py` (Task 6) and `recovery.py` (Task 4) both depend on this exact surface.

- [ ] **Step 1: Write failing test**

```python
# tests/backend/test_gateway.py
from src.backend.gateway import PolicyGateway, Action

def test_allows_in_scope_in_cap_action():
    gw = PolicyGateway()
    d = gw.check(Action("dispute_agent", "issue_refund", 120.0, "acct-1"))
    assert d.allowed is True
    assert d.reason == "ok"
    assert d.latency_ms >= 0

def test_blocks_over_cap_with_specific_reason():
    gw = PolicyGateway()
    d = gw.check(Action("dispute_agent", "issue_refund", 9000.0, "acct-1"))
    assert d.allowed is False
    assert "spend_cap exceeded" in d.reason
    assert "9000" in d.reason

def test_blocks_wrong_scope_with_specific_reason():
    gw = PolicyGateway()
    d = gw.check(Action("benefit_agent", "raise_credit_limit", 100.0, "acct-1"))
    assert d.allowed is False
    assert "not in scope" in d.reason

def test_revoked_agent_blocked():
    gw = PolicyGateway()
    gw.revoke("servicing_agent")
    d = gw.check(Action("servicing_agent", "reissue_card", 0.0, "acct-1"))
    assert d.allowed is False
    assert "revoked" in d.reason

def test_fleet_halt_blocks_everyone():
    gw = PolicyGateway()
    gw.halt_fleet()
    d = gw.check(Action("dispute_agent", "issue_refund", 10.0, "acct-1"))
    assert d.allowed is False
    assert d.reason == "fleet halted"

def test_resume_after_halt():
    gw = PolicyGateway()
    gw.halt_fleet()
    gw.resume_fleet()
    d = gw.check(Action("dispute_agent", "issue_refund", 10.0, "acct-1"))
    assert d.allowed is True

def test_set_spend_cap_changes_future_decisions():
    gw = PolicyGateway()
    gw.set_spend_cap("dispute_agent", 50.0)
    d = gw.check(Action("dispute_agent", "issue_refund", 60.0, "acct-1"))
    assert d.allowed is False

def test_toggle_permission_adds_and_removes_scope():
    gw = PolicyGateway()
    gw.toggle_permission("benefit_agent", "raise_credit_limit")
    assert gw.check(Action("benefit_agent", "raise_credit_limit", 10.0, "acct-1")).allowed is True
    gw.toggle_permission("benefit_agent", "raise_credit_limit")
    assert gw.check(Action("benefit_agent", "raise_credit_limit", 10.0, "acct-1")).allowed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_gateway.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/backend/gateway.py
import time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Action:
    agent_id: str
    action_type: str
    amount: float = 0.0
    target_account: str = ""

@dataclass
class Decision:
    allowed: bool
    reason: str
    latency_ms: float

DEFAULT_POLICIES = {
    "dispute_agent": {"allowed_actions": {"issue_refund", "request_evidence"}, "spend_cap": 500.0, "revoked": False},
    "benefit_agent": {"allowed_actions": {"activate_benefit", "file_claim"}, "spend_cap": 1000.0, "revoked": False},
    "servicing_agent": {"allowed_actions": {"raise_credit_limit", "reverse_fee", "reissue_card"}, "spend_cap": 2000.0, "revoked": False},
}

class PolicyGateway:
    def __init__(self, policies: Optional[dict] = None):
        source = policies if policies is not None else DEFAULT_POLICIES
        self.policies = {
            agent_id: {
                "allowed_actions": set(p["allowed_actions"]),
                "spend_cap": p["spend_cap"],
                "revoked": p["revoked"],
            }
            for agent_id, p in source.items()
        }
        self.halted = False

    def check(self, action: Action) -> Decision:
        start = time.perf_counter()
        allowed, reason = True, "ok"

        if self.halted:
            allowed, reason = False, "fleet halted"
        else:
            policy = self.policies.get(action.agent_id)
            if policy is None:
                allowed, reason = False, f"unknown agent {action.agent_id}"
            elif policy["revoked"]:
                allowed, reason = False, f"agent {action.agent_id} revoked"
            elif action.action_type not in policy["allowed_actions"]:
                allowed, reason = False, f"action '{action.action_type}' not in scope for {action.agent_id}"
            elif action.amount and action.amount > policy["spend_cap"]:
                allowed, reason = False, (
                    f"spend_cap exceeded: requested ${action.amount:.2f} > cap ${policy['spend_cap']:.2f}"
                )

        latency_ms = (time.perf_counter() - start) * 1000
        return Decision(allowed=allowed, reason=reason, latency_ms=latency_ms)

    def revoke(self, agent_id: str) -> None:
        self.policies[agent_id]["revoked"] = True

    def unrevoke(self, agent_id: str) -> None:
        self.policies[agent_id]["revoked"] = False

    def halt_fleet(self) -> None:
        self.halted = True

    def resume_fleet(self) -> None:
        self.halted = False

    def set_spend_cap(self, agent_id: str, cap: float) -> None:
        self.policies[agent_id]["spend_cap"] = cap

    def toggle_permission(self, agent_id: str, action_type: str) -> None:
        allowed = self.policies[agent_id]["allowed_actions"]
        if action_type in allowed:
            allowed.remove(action_type)
        else:
            allowed.add(action_type)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_gateway.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/backend/gateway.py tests/backend/test_gateway.py
git commit -m "feat: add policy gateway with caps, scopes, revocation, fleet halt"
```

---

## Task 4: Mock agents

**Files:**
- Create: `src/backend/agents.py`
- Test: `tests/backend/test_agents.py`

**Interfaces:**
- Consumes: `Action` from `src.backend.gateway`.
- Produces: `ScriptedAction(action: Action, label: str)`,
  `dispute_agent_actions() -> list[ScriptedAction]`, `benefit_agent_actions()`,
  `servicing_agent_actions()`, `all_scripted_actions() -> list[ScriptedAction]`.
  `label` is `"in_policy"` or `"violation"`. Consumed by `demo.py` (Task 6) for
  narration and by `main.py`'s seed/replay endpoint.

- [ ] **Step 1: Write failing test**

```python
# tests/backend/test_agents.py
from src.backend.agents import all_scripted_actions, dispute_agent_actions

def test_all_scripted_actions_nonempty_and_labeled():
    actions = all_scripted_actions()
    assert len(actions) >= 6
    assert all(a.label in ("in_policy", "violation") for a in actions)

def test_dispute_agent_has_at_least_one_violation():
    actions = dispute_agent_actions()
    assert any(a.label == "violation" for a in actions)

def test_each_action_has_agent_id_matching_its_generator():
    actions = dispute_agent_actions()
    assert all(a.action.agent_id == "dispute_agent" for a in actions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_agents.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/backend/agents.py
from dataclasses import dataclass
from src.backend.gateway import Action

@dataclass
class ScriptedAction:
    action: Action
    label: str  # "in_policy" or "violation"

def dispute_agent_actions() -> list[ScriptedAction]:
    return [
        ScriptedAction(Action("dispute_agent", "issue_refund", 120.0, "acct-1001"), "in_policy"),
        ScriptedAction(Action("dispute_agent", "request_evidence", 0.0, "acct-1002"), "in_policy"),
        ScriptedAction(Action("dispute_agent", "issue_refund", 9000.0, "acct-1003"), "violation"),
    ]

def benefit_agent_actions() -> list[ScriptedAction]:
    return [
        ScriptedAction(Action("benefit_agent", "activate_benefit", 0.0, "acct-2001"), "in_policy"),
        ScriptedAction(Action("benefit_agent", "file_claim", 300.0, "acct-2002"), "in_policy"),
        ScriptedAction(Action("benefit_agent", "raise_credit_limit", 500.0, "acct-2003"), "violation"),
    ]

def servicing_agent_actions() -> list[ScriptedAction]:
    return [
        ScriptedAction(Action("servicing_agent", "reverse_fee", 25.0, "acct-3001"), "in_policy"),
        ScriptedAction(Action("servicing_agent", "reissue_card", 0.0, "acct-3002"), "in_policy"),
        ScriptedAction(Action("servicing_agent", "raise_credit_limit", 1500.0, "acct-3003"), "in_policy"),
    ]

def all_scripted_actions() -> list[ScriptedAction]:
    return dispute_agent_actions() + benefit_agent_actions() + servicing_agent_actions()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_agents.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/backend/agents.py tests/backend/test_agents.py
git commit -m "feat: add scripted mock agent actions"
```

---

## Task 5: Reflexion recovery loop

**Files:**
- Create: `src/backend/recovery.py`
- Test: `tests/backend/test_recovery.py`

**Interfaces:**
- Consumes: `PolicyGateway`, `Action` from `gateway.py`; `AuditLog` from `audit.py`.
- Produces: `class Recovery: __init__(self, gateway: PolicyGateway, audit: AuditLog); handle(action: Action) -> Decision`.
  `main.py` (Task 6) calls `Recovery.handle()` for every incoming action instead of
  calling the gateway directly.

- [ ] **Step 1: Write failing test**

```python
# tests/backend/test_recovery.py
from src.backend.gateway import PolicyGateway, Action
from src.backend.audit import get_connection, AuditLog
from src.backend.recovery import Recovery

def make_recovery():
    gw = PolicyGateway()
    conn = get_connection(":memory:")
    audit = AuditLog(conn)
    return Recovery(gw, audit), gw, audit

def test_in_policy_action_allowed_once_logged_once():
    rec, gw, audit = make_recovery()
    d = rec.handle(Action("dispute_agent", "issue_refund", 120.0, "acct-1"))
    assert d.allowed is True
    assert len(audit.list()) == 1

def test_over_cap_action_retries_clamped_amount_and_succeeds():
    rec, gw, audit = make_recovery()
    d = rec.handle(Action("dispute_agent", "issue_refund", 9000.0, "acct-1"))
    assert d.allowed is True  # retry succeeded at clamped cap amount
    rows = audit.list()
    assert len(rows) == 2  # original block + retry allow
    assert rows[0]["decision"] == "allow"
    assert rows[0]["reason"].startswith("retry:")
    assert rows[1]["decision"] == "block"

def test_wrong_scope_action_escalates_not_retries():
    rec, gw, audit = make_recovery()
    d = rec.handle(Action("benefit_agent", "raise_credit_limit", 100.0, "acct-1"))
    assert d.allowed is False
    rows = audit.list()
    assert len(rows) == 1  # no retry row, scope violations aren't retryable
    escalations = audit.conn.execute("SELECT * FROM escalations").fetchall()
    assert len(escalations) == 1
    assert escalations[0]["agent_id"] == "benefit_agent"

def test_revoked_agent_escalates():
    rec, gw, audit = make_recovery()
    gw.revoke("servicing_agent")
    d = rec.handle(Action("servicing_agent", "reissue_card", 0.0, "acct-1"))
    assert d.allowed is False
    escalations = audit.conn.execute("SELECT * FROM escalations").fetchall()
    assert len(escalations) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_recovery.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/backend/recovery.py
import time
from src.backend.gateway import PolicyGateway, Action, Decision
from src.backend.audit import AuditLog

class Recovery:
    def __init__(self, gateway: PolicyGateway, audit: AuditLog):
        self.gateway = gateway
        self.audit = audit

    def handle(self, action: Action) -> Decision:
        decision = self.gateway.check(action)
        self.audit.record(
            action.agent_id, action.action_type, action.amount, action.target_account,
            "allow" if decision.allowed else "block", decision.reason, decision.latency_ms,
        )
        if decision.allowed:
            return decision

        if decision.reason.startswith("spend_cap exceeded"):
            policy = self.gateway.policies.get(action.agent_id)
            if policy is not None:
                retry_action = Action(action.agent_id, action.action_type, policy["spend_cap"], action.target_account)
                retry_decision = self.gateway.check(retry_action)
                self.audit.record(
                    action.agent_id, action.action_type, retry_action.amount, action.target_account,
                    "allow" if retry_decision.allowed else "block",
                    f"retry: {retry_decision.reason}", retry_decision.latency_ms,
                )
                if retry_decision.allowed:
                    return retry_decision

        self._escalate(action, decision.reason)
        return decision

    def _escalate(self, action: Action, reason: str) -> None:
        self.audit.conn.execute(
            "INSERT INTO escalations (ts, agent_id, action_type, amount, target_account, reason, resolved) "
            "VALUES (?,?,?,?,?,?,0)",
            (time.time(), action.agent_id, action.action_type, action.amount, action.target_account, reason),
        )
        self.audit.conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_recovery.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/backend/recovery.py tests/backend/test_recovery.py
git commit -m "feat: add Reflexion-style block-log-retry-escalate recovery loop"
```

---

## Task 6: FastAPI app + WebSocket feed

**Files:**
- Create: `src/backend/main.py`
- Test: `tests/backend/test_main.py`

**Interfaces:**
- Consumes: `PolicyGateway`, `Action` (gateway.py); `get_connection`, `AuditLog` (audit.py);
  `Recovery` (recovery.py); `all_scripted_actions` (agents.py).
- Produces: FastAPI `app` object. Routes:
  - `POST /actions` body `{agent_id, action_type, amount, target_account}` -> runs through `Recovery.handle`, broadcasts result over WS, returns `{allowed, reason, latency_ms}`
  - `GET /policies` -> full policy dict incl. `halted`
  - `PATCH /policies/{agent_id}` body `{spend_cap?: float, toggle_action_type?: str}` -> applies change, returns updated policy
  - `POST /agents/{agent_id}/revoke` / `POST /agents/{agent_id}/unrevoke`
  - `POST /fleet/halt` / `POST /fleet/resume`
  - `GET /audit?limit=200` -> `AuditLog.list()`
  - `POST /seed` -> runs `all_scripted_actions()` through `Recovery.handle` (used by `demo.py`)
  - `WS /ws` -> broadcasts every decision event as JSON: `{type: "decision", agent_id, action_type, amount, decision, reason, latency_ms, ts}`

- [ ] **Step 1: Write failing test**

```python
# tests/backend/test_main.py
from fastapi.testclient import TestClient
from src.backend.main import create_app

def make_client():
    app = create_app(db_path=":memory:")
    return TestClient(app)

def test_action_allowed_returns_200_and_decision():
    client = make_client()
    resp = client.post("/actions", json={
        "agent_id": "dispute_agent", "action_type": "issue_refund",
        "amount": 100.0, "target_account": "acct-1",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is True

def test_over_cap_action_blocked_reason_returned():
    client = make_client()
    resp = client.post("/actions", json={
        "agent_id": "dispute_agent", "action_type": "issue_refund",
        "amount": 9000.0, "target_account": "acct-1",
    })
    body = resp.json()
    assert "spend_cap exceeded" in body["reason"]

def test_patch_policy_updates_spend_cap():
    client = make_client()
    resp = client.patch("/policies/dispute_agent", json={"spend_cap": 10.0})
    assert resp.status_code == 200
    resp2 = client.post("/actions", json={
        "agent_id": "dispute_agent", "action_type": "issue_refund",
        "amount": 20.0, "target_account": "acct-1",
    })
    assert resp2.json()["allowed"] is False

def test_fleet_halt_blocks_all_agents():
    client = make_client()
    client.post("/fleet/halt")
    resp = client.post("/actions", json={
        "agent_id": "servicing_agent", "action_type": "reissue_card",
        "amount": 0.0, "target_account": "acct-1",
    })
    assert resp.json()["reason"] == "fleet halted"

def test_audit_endpoint_returns_recorded_rows():
    client = make_client()
    client.post("/actions", json={
        "agent_id": "dispute_agent", "action_type": "issue_refund",
        "amount": 10.0, "target_account": "acct-1",
    })
    resp = client.get("/audit")
    assert len(resp.json()) == 1

def test_websocket_receives_decision_event():
    client = make_client()
    with client.websocket_connect("/ws") as ws:
        client.post("/actions", json={
            "agent_id": "dispute_agent", "action_type": "issue_refund",
            "amount": 10.0, "target_account": "acct-1",
        })
        msg = ws.receive_json()
        assert msg["type"] == "decision"
        assert msg["agent_id"] == "dispute_agent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/backend/main.py
import asyncio
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional

from src.backend.gateway import PolicyGateway, Action
from src.backend.audit import get_connection, AuditLog
from src.backend.recovery import Recovery
from src.backend.agents import all_scripted_actions

class ActionIn(BaseModel):
    agent_id: str
    action_type: str
    amount: float = 0.0
    target_account: str = ""

class PolicyPatch(BaseModel):
    spend_cap: Optional[float] = None
    toggle_action_type: Optional[str] = None

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)

def create_app(db_path: str = "governance.db") -> FastAPI:
    app = FastAPI(title="CodeStreet Governance Layer")
    conn = get_connection(db_path)
    audit = AuditLog(conn)
    gateway = PolicyGateway()
    recovery = Recovery(gateway, audit)
    manager = ConnectionManager()

    async def broadcast_decision(action: Action, decision):
        await manager.broadcast({
            "type": "decision",
            "agent_id": action.agent_id,
            "action_type": action.action_type,
            "amount": action.amount,
            "target_account": action.target_account,
            "decision": "allow" if decision.allowed else "block",
            "reason": decision.reason,
            "latency_ms": decision.latency_ms,
            "ts": time.time(),
        })

    @app.post("/actions")
    async def post_action(payload: ActionIn):
        action = Action(payload.agent_id, payload.action_type, payload.amount, payload.target_account)
        decision = recovery.handle(action)
        await broadcast_decision(action, decision)
        return {"allowed": decision.allowed, "reason": decision.reason, "latency_ms": decision.latency_ms}

    @app.get("/policies")
    def get_policies():
        return {
            "halted": gateway.halted,
            "agents": {
                agent_id: {
                    "allowed_actions": sorted(p["allowed_actions"]),
                    "spend_cap": p["spend_cap"],
                    "revoked": p["revoked"],
                }
                for agent_id, p in gateway.policies.items()
            },
        }

    @app.patch("/policies/{agent_id}")
    def patch_policy(agent_id: str, patch: PolicyPatch):
        if patch.spend_cap is not None:
            gateway.set_spend_cap(agent_id, patch.spend_cap)
        if patch.toggle_action_type is not None:
            gateway.toggle_permission(agent_id, patch.toggle_action_type)
        p = gateway.policies[agent_id]
        return {"allowed_actions": sorted(p["allowed_actions"]), "spend_cap": p["spend_cap"], "revoked": p["revoked"]}

    @app.post("/agents/{agent_id}/revoke")
    def revoke_agent(agent_id: str):
        gateway.revoke(agent_id)
        return {"agent_id": agent_id, "revoked": True}

    @app.post("/agents/{agent_id}/unrevoke")
    def unrevoke_agent(agent_id: str):
        gateway.unrevoke(agent_id)
        return {"agent_id": agent_id, "revoked": False}

    @app.post("/fleet/halt")
    def fleet_halt():
        gateway.halt_fleet()
        return {"halted": True}

    @app.post("/fleet/resume")
    def fleet_resume():
        gateway.resume_fleet()
        return {"halted": False}

    @app.get("/audit")
    def get_audit(limit: int = 200):
        return audit.list(limit)

    @app.post("/seed")
    async def seed():
        results = []
        for scripted in all_scripted_actions():
            decision = recovery.handle(scripted.action)
            await broadcast_decision(scripted.action, decision)
            results.append({"agent_id": scripted.action.agent_id, "allowed": decision.allowed})
        return {"seeded": len(results), "results": results}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app

app = create_app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_main.py -v`
Expected: 6 passed

- [ ] **Step 5: Manual smoke test**

Run: `uvicorn src.backend.main:app --reload --port 8000` then `curl -X POST localhost:8000/seed`
Expected: JSON with `"seeded": 9` and a mix of `allowed: true/false`.

- [ ] **Step 6: Commit**

```bash
git add src/backend/main.py tests/backend/test_main.py
git commit -m "feat: add FastAPI app with policy config, revoke, fleet halt, WS feed"
```

---

## Task 7: Frontend scaffold, live feed, spend meters

**Files:**
- Create: `src/frontend/package.json`, `vite.config.js`, `index.html`
- Create: `src/frontend/src/main.jsx`, `src/frontend/src/App.jsx`, `src/frontend/src/api.js`, `src/frontend/src/styles.css`
- Create: `src/frontend/src/components/LiveFeed.jsx`, `src/frontend/src/components/SpendMeter.jsx`

**Interfaces:**
- Consumes: backend `GET /policies`, `GET /audit`, `WS /ws` (Task 6).
- Produces: `App.jsx` renders `<LiveFeed events={events} />` and
  `<SpendMeter agentId policy spent />` per agent — `AgentControls.jsx` (Task 8)
  is added as a sibling in the same `App.jsx` agent-card loop.

- [ ] **Step 1: `package.json`**

```json
{
  "name": "governance-dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: `vite.config.js`**

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
})
```

- [ ] **Step 3: `index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>CodeStreet Governance Layer</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 4: `src/main.jsx`**

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(<App />)
```

- [ ] **Step 5: `src/api.js`**

```javascript
const BASE = 'http://localhost:8000'

export async function getPolicies() {
  const res = await fetch(`${BASE}/policies`)
  return res.json()
}

export async function getAudit(limit = 200) {
  const res = await fetch(`${BASE}/audit?limit=${limit}`)
  return res.json()
}

export async function patchPolicy(agentId, body) {
  const res = await fetch(`${BASE}/policies/${agentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

export async function revokeAgent(agentId, revoked) {
  const path = revoked ? 'revoke' : 'unrevoke'
  const res = await fetch(`${BASE}/agents/${agentId}/${path}`, { method: 'POST' })
  return res.json()
}

export async function fleetHalt() {
  const res = await fetch(`${BASE}/fleet/halt`, { method: 'POST' })
  return res.json()
}

export async function fleetResume() {
  const res = await fetch(`${BASE}/fleet/resume`, { method: 'POST' })
  return res.json()
}

export function connectFeed(onEvent) {
  const ws = new WebSocket('ws://localhost:8000/ws')
  ws.onmessage = (msg) => onEvent(JSON.parse(msg.data))
  return ws
}
```

- [ ] **Step 6: `src/components/LiveFeed.jsx`**

```jsx
export default function LiveFeed({ events }) {
  return (
    <div className="live-feed">
      <h2>Live Feed</h2>
      <ul>
        {events.map((e, i) => (
          <li key={i} className={e.decision === 'allow' ? 'row-allow' : 'row-block'}>
            <span className="agent">{e.agent_id}</span>
            <span className="action">{e.action_type}</span>
            <span className="amount">${e.amount.toFixed(2)}</span>
            <span className="decision">{e.decision.toUpperCase()}</span>
            <span className="reason">{e.reason}</span>
            <span className="latency">{e.latency_ms.toFixed(2)}ms</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 7: `src/components/SpendMeter.jsx`**

```jsx
export default function SpendMeter({ agentId, cap, spent }) {
  const pct = cap > 0 ? Math.min(100, (spent / cap) * 100) : 0
  return (
    <div className="spend-meter">
      <div className="spend-meter-label">{agentId}: ${spent.toFixed(2)} / ${cap.toFixed(2)}</div>
      <div className="spend-meter-bar">
        <div className="spend-meter-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
```

- [ ] **Step 8: `src/App.jsx`** (minimal wiring; `AgentControls` slot filled in Task 8)

```jsx
import { useEffect, useState } from 'react'
import { getPolicies, connectFeed } from './api'
import LiveFeed from './components/LiveFeed'
import SpendMeter from './components/SpendMeter'

export default function App() {
  const [policies, setPolicies] = useState({ halted: false, agents: {} })
  const [events, setEvents] = useState([])
  const [spent, setSpent] = useState({})

  useEffect(() => {
    getPolicies().then(setPolicies)
    const ws = connectFeed((evt) => {
      setEvents((prev) => [evt, ...prev].slice(0, 100))
      if (evt.decision === 'allow') {
        setSpent((prev) => ({ ...prev, [evt.agent_id]: (prev[evt.agent_id] || 0) + evt.amount }))
      }
    })
    return () => ws.close()
  }, [])

  return (
    <div className="app">
      <h1>CodeStreet Governance Layer</h1>
      <p className="mock-label">All data mocked/synthetic — hackathon prototype</p>
      <div className="agent-cards">
        {Object.entries(policies.agents).map(([agentId, policy]) => (
          <SpendMeter key={agentId} agentId={agentId} cap={policy.spend_cap} spent={spent[agentId] || 0} />
        ))}
      </div>
      <LiveFeed events={events} />
    </div>
  )
}
```

- [ ] **Step 9: `src/styles.css`**

```css
body { font-family: system-ui, sans-serif; background: #0b0f14; color: #e6e6e6; margin: 0; padding: 24px; }
.mock-label { color: #f5a623; font-size: 12px; text-transform: uppercase; }
.agent-cards { display: flex; gap: 16px; margin-bottom: 24px; }
.spend-meter { flex: 1; background: #151b23; padding: 12px; border-radius: 8px; }
.spend-meter-bar { background: #263042; height: 8px; border-radius: 4px; margin-top: 6px; }
.spend-meter-fill { background: #4ade80; height: 8px; border-radius: 4px; }
.live-feed ul { list-style: none; padding: 0; }
.live-feed li { display: flex; gap: 12px; padding: 6px 8px; border-bottom: 1px solid #1f2937; font-size: 13px; }
.row-allow { border-left: 3px solid #4ade80; }
.row-block { border-left: 3px solid #f87171; }
```

- [ ] **Step 10: Install and smoke test**

Run: `cd src/frontend && npm install && npm run dev`
Expected: Vite dev server starts on :5173, page loads (backend must also be running on :8000 for data).

- [ ] **Step 11: Commit**

```bash
git add src/frontend/package.json src/frontend/vite.config.js src/frontend/index.html src/frontend/src
git commit -m "feat: scaffold React dashboard with live feed and spend meters"
```

---

## Task 8: Revoke button, fleet E-STOP, policy config form

**Files:**
- Create: `src/frontend/src/components/AgentControls.jsx`
- Create: `src/frontend/src/components/EmergencyStop.jsx`
- Modify: `src/frontend/src/App.jsx` (render both, wire handlers)
- Modify: `src/frontend/src/styles.css` (append E-STOP + form styles)

**Interfaces:**
- Consumes: `patchPolicy`, `revokeAgent`, `fleetHalt`, `fleetResume` from `api.js` (Task 7).

- [ ] **Step 1: `src/components/AgentControls.jsx`**

```jsx
import { useState } from 'react'
import { patchPolicy, revokeAgent } from '../api'

export default function AgentControls({ agentId, policy, onUpdate }) {
  const [capInput, setCapInput] = useState(policy.spend_cap)
  const [scopeInput, setScopeInput] = useState('')

  async function handleRevokeToggle() {
    const updated = await revokeAgent(agentId, !policy.revoked)
    onUpdate(agentId, { ...policy, revoked: updated.revoked })
  }

  async function handleCapSubmit(e) {
    e.preventDefault()
    const updated = await patchPolicy(agentId, { spend_cap: parseFloat(capInput) })
    onUpdate(agentId, updated)
  }

  async function handleScopeToggle(e) {
    e.preventDefault()
    if (!scopeInput) return
    const updated = await patchPolicy(agentId, { toggle_action_type: scopeInput })
    onUpdate(agentId, updated)
    setScopeInput('')
  }

  return (
    <div className="agent-controls">
      <button className={policy.revoked ? 'btn-revoked' : 'btn-revoke'} onClick={handleRevokeToggle}>
        {policy.revoked ? 'Un-revoke' : 'Revoke'} {agentId}
      </button>
      <form onSubmit={handleCapSubmit} className="policy-form">
        <label>
          Spend cap
          <input type="number" value={capInput} onChange={(e) => setCapInput(e.target.value)} />
        </label>
        <button type="submit">Update cap</button>
      </form>
      <form onSubmit={handleScopeToggle} className="policy-form">
        <label>
          Toggle scope
          <input type="text" placeholder="e.g. issue_refund" value={scopeInput} onChange={(e) => setScopeInput(e.target.value)} />
        </label>
        <button type="submit">Toggle</button>
      </form>
      <div className="current-scopes">Scopes: {policy.allowed_actions.join(', ')}</div>
    </div>
  )
}
```

- [ ] **Step 2: `src/components/EmergencyStop.jsx`**

```jsx
import { fleetHalt, fleetResume } from '../api'

export default function EmergencyStop({ halted, onToggle }) {
  async function handleClick() {
    const result = halted ? await fleetResume() : await fleetHalt()
    onToggle(result.halted)
  }

  return (
    <button className={halted ? 'btn-estop-active' : 'btn-estop'} onClick={handleClick}>
      {halted ? 'RESUME FLEET' : 'EMERGENCY STOP — HALT FLEET'}
    </button>
  )
}
```

- [ ] **Step 3: Update `src/App.jsx`** — add imports, state handlers, render controls + E-STOP

```jsx
import { useEffect, useState } from 'react'
import { getPolicies, connectFeed } from './api'
import LiveFeed from './components/LiveFeed'
import SpendMeter from './components/SpendMeter'
import AgentControls from './components/AgentControls'
import EmergencyStop from './components/EmergencyStop'

export default function App() {
  const [policies, setPolicies] = useState({ halted: false, agents: {} })
  const [events, setEvents] = useState([])
  const [spent, setSpent] = useState({})

  useEffect(() => {
    getPolicies().then(setPolicies)
    const ws = connectFeed((evt) => {
      setEvents((prev) => [evt, ...prev].slice(0, 100))
      if (evt.decision === 'allow') {
        setSpent((prev) => ({ ...prev, [evt.agent_id]: (prev[evt.agent_id] || 0) + evt.amount }))
      }
    })
    return () => ws.close()
  }, [])

  function updateAgentPolicy(agentId, patch) {
    setPolicies((prev) => ({ ...prev, agents: { ...prev.agents, [agentId]: { ...prev.agents[agentId], ...patch } } }))
  }

  return (
    <div className="app">
      <h1>CodeStreet Governance Layer</h1>
      <p className="mock-label">All data mocked/synthetic — hackathon prototype</p>
      <EmergencyStop halted={policies.halted} onToggle={(h) => setPolicies((p) => ({ ...p, halted: h }))} />
      <div className="agent-cards">
        {Object.entries(policies.agents).map(([agentId, policy]) => (
          <div key={agentId} className="agent-card">
            <SpendMeter agentId={agentId} cap={policy.spend_cap} spent={spent[agentId] || 0} />
            <AgentControls agentId={agentId} policy={policy} onUpdate={updateAgentPolicy} />
          </div>
        ))}
      </div>
      <LiveFeed events={events} />
    </div>
  )
}
```

- [ ] **Step 4: Append to `src/styles.css`**

```css
.btn-estop { background: #dc2626; color: white; font-weight: bold; padding: 16px 24px; font-size: 16px; border: none; border-radius: 8px; cursor: pointer; margin-bottom: 16px; }
.btn-estop-active { background: #16a34a; color: white; font-weight: bold; padding: 16px 24px; font-size: 16px; border: none; border-radius: 8px; cursor: pointer; margin-bottom: 16px; }
.agent-card { display: flex; flex-direction: column; gap: 8px; background: #10151c; padding: 12px; border-radius: 8px; }
.agent-controls { display: flex; flex-direction: column; gap: 6px; font-size: 12px; }
.policy-form { display: flex; gap: 6px; align-items: center; }
.policy-form input { width: 80px; }
.btn-revoke { background: #f59e0b; border: none; padding: 6px; border-radius: 4px; cursor: pointer; }
.btn-revoked { background: #6b7280; border: none; padding: 6px; border-radius: 4px; cursor: pointer; }
```

- [ ] **Step 5: Manual smoke test**

Run backend (`uvicorn src.backend.main:app --port 8000`) and frontend (`npm run dev` in `src/frontend`). Open `localhost:5173`.
Expected: agent cards show cap-edit form and revoke button; clicking EMERGENCY STOP turns it green ("RESUME FLEET") and a subsequent `/seed` POST (via curl) shows all actions blocked with reason "fleet halted" in the feed.

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src
git commit -m "feat: add policy config form, revoke button, fleet emergency stop to dashboard"
```

---

## Task 9: Demo script (Phase 6 sequence)

**Files:**
- Create: `src/backend/demo.py`

**Interfaces:**
- Consumes: running server at `http://localhost:8000` (Task 6 routes) via `httpx`.
- Produces: CLI script, no importable interface needed by other tasks.

- [ ] **Step 1: Implement**

```python
# src/backend/demo.py
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
```

- [ ] **Step 2: Manual run**

Run: `uvicorn src.backend.main:app --port 8000` (separate terminal), then `python -m src.backend.demo`
Expected: 5 labeled steps print JSON responses; step 2 shows `"allowed": false` with spend_cap reason; step 3b shows `"reason": "fleet halted"`.

- [ ] **Step 3: Commit**

```bash
git add src/backend/demo.py
git commit -m "feat: add Phase 6 demo sequence script"
```

---

## Task 10: Architecture diagram

**Files:**
- Create: `docs/architecture.mmd`
- Create: `docs/architecture.svg` (rendered)

- [ ] **Step 1: Write `docs/architecture.mmd`**

```
flowchart TB
    A1[dispute_agent] --> GW
    A2[benefit_agent] --> GW
    A3[servicing_agent] --> GW
    GW[Policy Gateway<br/>dict policies + check fn] -->|allow| EX[Execute mock action]
    GW -->|block| REC[Recovery<br/>retry-once / escalate]
    EX --> AL[(Audit Log<br/>SQLite)]
    REC --> AL
    AL --> API[FastAPI REST + WebSocket]
    API --> DASH[React Dashboard]
    DASH -->|revoke / caps / scopes| API
    DASH -->|EMERGENCY STOP| API
```

- [ ] **Step 2: Render to SVG**

Run: `npx -y @mermaid-js/mermaid-cli -i docs/architecture.mmd -o docs/architecture.svg`
Expected: `docs/architecture.svg` created. If `npx` unavailable, use the Mermaid Live Editor (https://mermaid.live) manually and export SVG to the same path.

- [ ] **Step 3: Commit**

```bash
git add docs/architecture.mmd docs/architecture.svg
git commit -m "docs: add architecture diagram"
```

---

## Task 11: Round 1 proposal.md

**Files:**
- Create: `docs/proposal.md`

- [ ] **Step 1: Write proposal, structured to the AmEx Round 1 checklist**

Sections required (fill using the design doc + measured latency from Task 6's manual smoke test /
the demo run's audit rows): Problem statement selected (quote theme overview from brief), Proposed
solution (expand one-liner into 2-3 paragraphs), Expected business/societal impact, Success metrics
(policy enforcement accuracy, time-to-detect, latency overhead — pull actual p50/p95 `latency_ms`
from a `GET /audit` after running `demo.py`), Implementation approach, Technical details (stack,
architecture diagram embed via `![architecture](architecture.svg)`, flowchart, assumptions/constraints,
scalability notes referencing swapping SQLite for Postgres and the dict-policy engine for a real
rules service as the fleet grows).

- [ ] **Step 2: Convert to PDF**

Run: `pandoc docs/proposal.md -o docs/proposal.pdf` (or docx: `pandoc docs/proposal.md -o docs/proposal.docx`)
Expected: file created. If `pandoc` unavailable, note in README that the markdown is submission-ready as-is.

- [ ] **Step 3: Commit**

```bash
git add docs/proposal.md docs/proposal.pdf
git commit -m "docs: add Round 1 proposal"
```

---

## Task 12: Deck generation

**Files:**
- Create: `deck/generate_deck.py`
- Output: `deck/CodeStreet_Governance_Deck.pptx`

- [ ] **Step 1: Implement `deck/generate_deck.py`**

```python
"""Generates the pitch deck. Run: python deck/generate_deck.py
Requires docs/architecture.svg (or a .png export of it) and any demo screenshots
in deck/screenshots/ to be present first.
"""
from pptx import Presentation
from pptx.util import Inches, Pt

def add_title_slide(prs, title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title
    slide.placeholders[1].text = subtitle
    return slide

def add_bullet_slide(prs, title, bullets):
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = title
    body = slide.placeholders[1].text_frame
    body.clear()
    for i, b in enumerate(bullets):
        p = body.paragraphs[0] if i == 0 else body.add_paragraph()
        p.text = b
        p.font.size = Pt(20)
    return slide

def add_image_slide(prs, title, image_path):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = title
    slide.shapes.add_picture(image_path, Inches(0.5), Inches(1.5), width=Inches(9))
    return slide

def main():
    prs = Presentation()
    add_title_slide(prs, "Governance Layer for Financial Agents",
                     "The safety layer every other AmEx agent theme needs before deployment")
    add_bullet_slide(prs, "The Problem", [
        "2026: an autonomous airline booking agent misrouted 1,000+ passengers",
        "nothing checked its actions before it executed them",
        "the same failure mode applies to card & payments agents",
    ])
    add_bullet_slide(prs, "Why This Theme", [
        "not a 7th agent competing with the other 6 themes",
        "it's the control plane the other 6 need to be deployable at all",
    ])
    add_image_slide(prs, "Architecture", "docs/architecture.svg")
    add_bullet_slide(prs, "Live Demo", [
        "agents flow through the policy gateway in real time",
        "over-cap action blocked live, exact reason shown inline",
        "fleet-wide EMERGENCY STOP halts every agent instantly",
    ])
    add_bullet_slide(prs, "Business Impact", [
        "prevents a misrouted-agent incident before it reaches a customer",
        "full audit trail for every agent decision, allow or block",
        "operator can reconfigure policy live, no redeploy needed",
    ])
    add_bullet_slide(prs, "Scalability & What's Next", [
        "SQLite -> Postgres, dict-policy engine -> rules service as fleet grows",
        "add per-action-type risk scoring on top of static caps/scopes",
        "pluggable connectors for real agent frameworks",
    ])
    prs.save("deck/CodeStreet_Governance_Deck.pptx")
    print("Saved deck/CodeStreet_Governance_Deck.pptx")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run**

Run: `python deck/generate_deck.py`
Expected: `deck/CodeStreet_Governance_Deck.pptx` created, 7 slides. Note: if `docs/architecture.svg`
can't be embedded directly (pptx needs raster for some renderers), export a PNG of it first and
point `add_image_slide` at that path instead.

- [ ] **Step 3: Commit**

```bash
git add deck/generate_deck.py deck/CodeStreet_Governance_Deck.pptx
git commit -m "feat: generate pitch deck via python-pptx"
```

---

## Task 13: Demo video (Playwright recording)

**Files:**
- Create: `video/record_demo.py`
- Output: `video/demo.webm`

- [ ] **Step 1: Implement**

```python
"""Records the Phase 6 demo as a real browser session. Requires both servers running:
    uvicorn src.backend.main:app --port 8000
    (cd src/frontend && npm run dev)
Then: python video/record_demo.py
"""
import time
from playwright.sync_api import sync_playwright
import httpx

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
```

- [ ] **Step 2: Install Playwright browser + run**

Run: `playwright install chromium && python video/record_demo.py`
Expected: a `.webm` file appears in `video/`. Rename to `video/demo.webm` if Playwright names it by hash.

- [ ] **Step 3: Commit**

```bash
git add video/record_demo.py
git commit -m "feat: add Playwright demo recording script"
```

(video output itself is gitignored — attach separately to the submission per the packaging step)

---

## Task 14: README + packaging check

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`** covering: one-liner, setup (`pip install -r requirements.txt`,
  `npm install` in `src/frontend`), run instructions (backend `uvicorn` command, frontend `npm run dev`,
  `python -m src.backend.demo` for the scripted sequence), how to regenerate deck/diagram/video, and an
  explicit "all data mocked/synthetic, not connected to any real AmEx system" line.

- [ ] **Step 2: Verify packaging layout**

Run: `ls docs deck video src` (or `find . -maxdepth 2`)
Expected: `/docs` (proposal.md, proposal.pdf, architecture.mmd/svg), `/deck` (generate_deck.py, .pptx),
`/video` (record_demo.py), `/src` (backend, frontend) all present per brief packaging requirement.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and demo instructions"
```

---

## Self-Review Notes

- **Spec coverage:** Phases 1-6 -> Tasks 4,3+9,2,5,7+8,9. Deliverables 1-4 -> Tasks 11,12,10,13.
  Policy config addition -> Task 8. Latency stamping -> Task 3 (`Decision.latency_ms`), surfaced in
  Task 2 (audit column), Task 6 (API/WS), Task 11 (proposal metrics).
- **Placeholder scan:** none — every step has real code or an exact runnable command.
- **Type consistency:** `Action`/`Decision` defined once in `gateway.py` (Task 3), reused verbatim by
  `agents.py` (Task 4), `recovery.py` (Task 5), `main.py` (Task 6) — no renamed fields across tasks.
