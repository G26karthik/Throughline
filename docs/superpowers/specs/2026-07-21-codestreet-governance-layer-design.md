# CodeStreet 2026: Governance Layer for Financial Agents — Design

**Status:** Approved (chat, 2026-07-21)
**Source:** `CLAUDE_CODE_PROJECT_BRIEF.md`

## Problem

Fleet of financial AI agents (dispute, benefit, servicing) needs a control plane in front
of it: per-agent permission scopes, spend caps, revocation (per-agent + fleet-wide kill
switch), full audit trail, self-healing retry/escalate on block, and an operator dashboard
that both monitors and configures policy live.

## Architecture

```
[dispute_agent]  [benefit_agent]  [servicing_agent]   (scripted mock agents)
        \               |               /
         v               v             v
                 PolicyGateway.check(action)
              (dict-of-policies + check fn, raw sqlite3)
                 |                          |
          ALLOW  |                   BLOCK  |
                 v                          v
           execute (mock)          Recovery (Reflexion loop):
                 |                    retry-in-policy once
                 v                    else escalate to human queue
              AuditLog (SQLite, append-only, latency-stamped)
                 |
                 v
        FastAPI REST + WebSocket feed
                 |
                 v
   React dashboard: live feed, spend meters, revoke, fleet
   E-STOP, POLICY CONFIG FORM (edit cap / toggle scope), inline
   block reasons
```

## Components

- **Mock agents** (`src/backend/agents.py`): 3 scripted agents emitting actions
  (agent_id, action_type, amount, target_account). Mix of in-policy and
  deliberately-violating actions (over cap, wrong scope, revoked agent) so the
  demo has real blocks.
- **Policy gateway** (`src/backend/gateway.py`): plain dict of policies per agent
  (`allowed_actions`, `spend_cap`, `revoked`) + fleet-wide `halted` flag. `check(action)`
  returns `Decision(allowed, reason, latency_ms)`. Decision latency = perf_counter diff
  around the check, stamped on every decision (success metric: "sub-5ms policy decision").
- **Audit log** (`src/backend/audit.py`): raw `sqlite3`, one `audit_log` table, append-only.
  Columns: id, ts, agent_id, action_type, amount, target_account, decision, reason,
  latency_ms.
- **Recovery / Reflexion loop** (`src/backend/recovery.py`): on BLOCK, log it, then:
  retry once with an amount clamped inside the cap if the block reason was
  over-cap; otherwise (wrong scope, revoked, fleet halted) push to an
  `escalations` table for a human queue. No external Reflexion library reused —
  no local Hecta/AlgoSentinel Reflexion code found (checked); this is a fresh,
  small implementation, documented as such.
- **API** (`src/backend/main.py`): FastAPI. REST for policy read/write
  (`GET/PATCH /policies/{agent_id}`), agent revoke (`POST /agents/{id}/revoke`),
  fleet stop (`POST /fleet/halt`, `POST /fleet/resume`), audit read
  (`GET /audit`). WebSocket `/ws` broadcasts every decision event live.
- **Dashboard** (`src/frontend/`): React + Vite. Live feed (WS), per-agent spend
  meter vs cap, per-agent revoke button, fleet E-STOP button, inline block
  reason on the feed row, and a **policy config form** per agent (edit spend
  cap, toggle a permission scope) that PATCHes the gateway directly — this is
  the operator-facing "configure policies" requirement from AmEx's task list,
  not just monitoring.

## Data flow for the Phase 6 demo script

1. Agents run on a loop, actions flow through gateway → allowed → audit logged →
   pushed over WS → dashboard feed updates green.
2. One agent fires an over-cap action → gateway blocks with exact reason
   ("spend_cap exceeded: requested $X > cap $Y") → recovery retries in-policy
   → dashboard shows the block + reason inline, then the retry succeeding.
3. Operator hits fleet-wide EMERGENCy STOP → `halted=true` → every subsequent
   action from any agent blocked with reason "fleet halted" → dashboard shows
   all agents going red live.

## Success metrics (for proposal doc)

- Policy enforcement accuracy: % of seeded violating actions correctly blocked
  (target 100% on the scripted set).
- Time-to-detect a violation: effectively instant (synchronous check), backed
  by the latency stat below.
- Latency overhead per agent action: measured `latency_ms` per gateway check,
  reported as p50/p95 across the demo run (target sub-5ms).

## Out of scope / deferred

- No OPA/rules DSL — plain dict + function per brief constraint.
- No Postgres/Redis — SQLite only.
- No auth/login on the dashboard (hackathon prototype, mocked data only).
- Deck and video are separate deliverables built after the working prototype
  exists (Phase 6 demo script is scripted first, then recorded).

## File layout (final)

```
/src/backend    FastAPI + SQLite service (agents, gateway, audit, recovery, WS)
/src/frontend   React + Vite dashboard
/docs           proposal.md, architecture.mmd (+rendered .svg)
/deck           generate_deck.py, output .pptx
/video          record_demo.py (Playwright), output recording
/README.md      setup + demo instructions
```
