# CodeStreet 2026: Governance Layer for Financial Agents
## Build brief for Claude Code

## Role
You are building a hackathon submission end to end: working code, the Round 1 proposal document, a presentation deck, and a demo video. Work autonomously and make reasonable defaults where something isn't specified. Only stop to ask if you're genuinely blocked (missing credentials, ambiguous business logic that changes the demo's outcome). Do not ask about things you can reasonably invent, like mock transaction amounts or agent names.

## Project
**Theme:** Governance Layer for Financial Agents, one of 7 AmEx CodeStreet 2026 themes (cards & payments).

**One-liner:** A control plane that sits in front of a fleet of financial AI agents (dispute resolution, benefit activation, servicing) and enforces per-agent permissions and spend caps in real time, keeps a full audit trail of every decision, and can revoke a single agent or halt the entire fleet instantly.

**Positioning for the pitch:** This isn't a 7th agent competing with the other themes, it's the safety layer the other six themes would need before AmEx could actually deploy any of them. Open with a real 2026 incident: an autonomous airline booking agent misrouted over a thousand passengers because nothing checked its actions before it executed them. This project is that missing check, applied to card and payments agents instead of travel agents.

## What "done" means
1. A working prototype, not just slides
2. A Round 1 idea proposal document
3. A presentation deck
4. A short demo video of the live prototype

## Build order

### Phase 1: Mock agents
Three small scripted agents simulating realistic AmEx agent behavior:
- `dispute_agent`: actions like "issue refund $X", "request evidence"
- `benefit_agent`: actions like "activate benefit", "file claim $X"
- `servicing_agent`: actions like "raise credit limit $X", "reverse fee $X", "reissue card"

Each action carries: agent ID, action type, dollar amount where relevant, target account. Include some actions that are clearly within policy and some that clearly aren't (over spend cap, wrong scope, agent revoked), so the demo has real blocks to show, not just green checkmarks.

### Phase 2: Policy gateway
Every mocked action routes through this before "executing":
- Per-agent permission scopes: which action types each agent may take
- Per-agent spend caps: reject or flag actions over threshold
- Revocation state: per-agent kill switch, plus a fleet-wide kill switch
- On block, return the specific rule that caused it, not a generic "denied"

Hand-roll the rule engine as a plain dict of policies plus a check function. Do not reach for OPA or a rules DSL, it costs more setup time than it returns in this window.

### Phase 3: Audit log
Append-only log of every attempted action: timestamp, agent, action, amount, decision, reason. SQLite is enough, don't stand up Postgres or Redis for a prototype.

### Phase 4: Self-healing / recovery
When an action is blocked, don't just fail it silently. Log the block, then have the agent either retry within policy (e.g., request an amount inside the cap) or escalate to a human queue. This is a Reflexion-style detect-log-retry loop. If Hecta Auction Scraper or AlgoSentinel are available locally, adapt their existing Reflexion/subagent-isolation logic rather than designing this from scratch.

### Phase 5: Dashboard
React frontend, live view (WebSocket or polling, either is fine):
- Real-time feed of agent actions and their allow/block decisions
- Spend meter per agent against its cap
- Per-agent revoke button
- One prominent fleet-wide EMERGENCY STOP button
- When something is blocked, show the reason inline, not buried in a log tab

### Phase 6: Demo script
Script and wire up this exact sequence, it's the centerpiece of both the video and any live demo:
1. Agents running normally, actions flowing through and getting approved
2. One agent attempts an over-cap action, gets blocked live, dashboard shows the specific reason
3. Hit the fleet-wide emergency stop, everything halts on screen

## Deliverables to generate

### 1. Round 1 idea proposal
Structure it exactly to match AmEx's own Round 1 checklist:
- Problem statement selected (quote the theme overview)
- Proposed solution (expand the one-liner above into 2-3 paragraphs)
- Expected business/societal impact
- Success metrics (e.g. policy enforcement accuracy, time-to-detect a violation, latency overhead added per agent action)
- Implementation approach
- Technical details: stack, frameworks, architecture diagram, flowcharts, assumptions/constraints, scalability notes

Write as clean markdown, then convert to PDF or docx.

### 2. Presentation deck
Build with python-pptx or an available pptx skill. Cover: the problem, why this theme was chosen, architecture diagram, live demo screenshots, business impact, and a scalability/what's-next slide. Minimal text per slide, prioritize visuals.

### 3. Architecture diagram
An actual rendered diagram (mermaid or SVG), not a text description: agents feeding into the policy gateway, gateway feeding the audit log and dashboard, dashboard exposing the emergency stop.

### 4. Demo video
Use Playwright to script and record a real browser session running the Phase 6 scenario against the actual running prototype. This should be a genuine recording of working software, not a mockup. Keep on-screen actions clear and well-paced since narration gets added afterward.

## Constraints
- All data is mocked and synthetic. Label it as such, never imply real AmEx systems or data.
- Keep the stack boring and fast: FastAPI + SQLite backend, React + Vite frontend. No new frameworks mid-build.
- Time budget is real. Favor a working vertical slice over a broad, shallow feature set.
- Package for submission: `/docs` (proposal, architecture diagram), `/deck` (pptx), `/video`, `/src` (working code), a README with setup and demo instructions, ready to zip or push as a public GitHub repo.
