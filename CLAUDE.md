# Claude Code — Project Instructions

> **On first invocation in any project:** Read `.claude/STACK_MANIFEST.md` once, then follow
> the Onboarding Protocol in Section 11 of that file before doing any task work. This gives
> you the full picture of available tools, MCP servers, skills, agents, and orchestration
> patterns for this machine's stack.

## This is a template file
Every new project should append project-specific context below the `---` divider at the bottom of this file. Do not overwrite this file — add to it.

---

## Token and cost efficiency

I track Claude spend via `ccusage`. Work accordingly:

- On large codebases, prefer Serena's semantic tools (`serena_find_symbol`, `serena_get_definition`, `serena_search_symbols`) over re-reading whole files to locate a symbol.
- Enable only the MCP servers a given task actually needs. Check `mcp-profiles/README.md` before starting a session and activate the minimum required set.
- Do not speculatively read files. Read what you know you need.

## Communication style

- No em-dashes. Use commas, colons, or semicolons instead.
- Terse and direct. No filler, no throat-clearing, no recaps of what you just did.
- No trailing summaries unless explicitly asked.
- Code comments only when the WHY is non-obvious. No what-comments.

## Commit message discipline

Concise, imperative subject line (50 chars max). Body only if the why needs explaining. No fluff ("add support for", "implement the feature to"). Examples of bad: "Added the new authentication flow that handles OAuth tokens". Good: "Switch auth to OAuth2 PKCE flow".

## Before calling backend/service code done

Run `/productionize`. This is a standing requirement before any backend or service code is declared complete.

## Code defaults

- No backwards-compat shims for removed code.
- No defensive error handling for impossible inputs. Trust internal guarantees.
- No feature flags for net-new work unless the deployment story requires them.

## Context discipline

- One task per session where practical. Don't let one session sprawl across unrelated work -- open a new session instead.
- Run `/compact` proactively once a session has been going a while, rather than waiting until context degrades.
- When asked to look at something, prefer being pointed at specific files over scanning whole directories. Use Serena's symbol tools (`serena_find_symbol`, `serena_get_definition`, `serena_search_symbols`) rather than broad Read/Grep on large codebases.
- Don't enable more MCP servers in a session than the task actually needs. Check `mcp-profiles/README.md` and activate only the minimum required set.

## Agentic loop design

Default structure for any agent loop (Reflexion-style, self-healing, subagent isolation):

**State-check → Decision → Execution → Feedback → Verification**

Always with an explicit stop condition. Never open-ended retry logic.

- Keep the verifier/checker as a separate step from the step that did the work. Don't fold verification into the same pass as execution -- this matches the maker-checker pattern from superpowers skills. Stay consistent with that across projects rather than inventing a different pattern per project.
- For Hecta's Reflexion loop and AlgoSentinel's subagent isolation: apply this structure by default unless the task requires something different.
- Default mental model: Anthropic's "Building Effective Agents" -- evaluator-optimizer and orchestrator-workers patterns. Use these for new agent work unless specified otherwise.

## Per-task orchestration check

Before starting any non-trivial task (anything beyond a one-line fix), state in one line which orchestration pattern you're using for THIS task and why -- even if it matches the project default, say so explicitly rather than silently proceeding.

If the task as described would clearly benefit from a pattern different from the project default (e.g. it touches 3+ independent subtasks that could run in parallel, or it's a research/multi-source task suited to swarm, or it's agent/LangGraph code suited to evaluator-optimizer), flag this BEFORE starting work: "This looks like it'd benefit from [pattern] instead of the project default of [pattern], because [reason]. Want me to use that, or stick with default?" Wait for confirmation before switching.

Don't ask this for trivial tasks (typo fixes, single-line changes). Only when task complexity or shape genuinely suggests a different pattern would help. Err toward flagging rather than silently picking.

---
<!-- Project-specific context below this line -->

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
