# CLAUDE.md

## Project Context

Motorsport telemetry analysis and AI coaching platform (Python + Next.js/FastAPI). Primary language is Python. Use Python idioms and tooling by default.

## Communication Style

Before implementing changes, ask clarifying questions rather than writing long inline markdown plans. Be concise and action-oriented.

## Workflow Orchestration

1. **Plan Mode Default** — Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions). If something goes sideways, STOP and re-plan.
2. **Subagent Strategy** — Use subagents liberally. One task per subagent. Match agent type to task (see Agent Playbook).
3. **Self-Improvement** — After ANY correction: update `tasks/lessons.md`. Write rules to prevent repeat mistakes.
4. **Verification** — Never mark complete without proving it works. Run tests, check logs, demonstrate correctness. Always run `superpowers:code-reviewer` after implementation.
5. **Elegance** — For non-trivial changes: "is there a more elegant way?" Skip for simple fixes.
6. **Autonomous Bugs** — Just fix bugs. Don't ask for hand-holding. Use `debugging-toolkit:debugger` for complex bugs.
7. **No Hedging** — NEVER say "ambitious" or hedge about scope. Implement everything requested.
8. **Domain Research** — Before any feature involving domain knowledge (vehicle dynamics, G-force analysis, coaching methodology), WebSearch first. Research iteratively (broad → specific → authoritative: SAE papers, MoTeC docs, YourDataDriven, TrailBrake, Driver61). Cite sources. Never invent domain algorithms from coding intuition alone.
9. **Task Tracking** — Write plan to `tasks/todo.md`, check in before implementing, mark items complete, capture lessons.
10. **Commit Immediately** — Always commit and push after making changes. Do not wait to be asked. Push to `staging` branch by default. NEVER push to `main` (production) unless the user explicitly says to deploy to prod.
11. **Image Viewing** — Download locally (`curl -sL -o /tmp/filename.ext "URL"`), view with Read tool, then delete.

## Core Principles

- *Simplicity First*: Make every change as simple as possible. Impact minimal code.
- *No Laziness*: Find root causes. No temporary fixes. Senior developer standards.
- *Minimal Impact*: Changes should only touch what's necessary. Avoid introducing bugs.

## Project Overview

Cataclysm is an AI-powered motorsport telemetry analysis and coaching platform for track day drivers. It ingests RaceChrono CSV v3 exports, processes them in the distance domain, detects corners, and generates AI coaching reports via the Claude API. Next.js + FastAPI, deployed on Railway from `main` branch.

For full architecture details: read `docs/architecture.md`. For setup/commands: read `docs/developer-guide.md`.

**Always work inside the project venv.** Run `source .venv/bin/activate` before any Python command.

## Code Conventions

- Python 3.11+, type hints required on all functions (mypy `disallow_untyped_defs`)
- Line length: 100 chars (ruff). Rules: E, F, W, I, N, UP, B, SIM
- All files start with `from __future__ import annotations`
- Module-level constants in UPPER_SNAKE_CASE
- Dataclasses for structured data, not dicts

## Quality Gates

All must pass before committing:

1. **Ruff**: `ruff format cataclysm/ tests/ backend/` then `ruff check cataclysm/ tests/ backend/`
2. **Mypy**: `dmypy run -- cataclysm/ backend/` (daemon mode, ~4s warm)
3. **Tests**: `pytest tests/ backend/tests/ -v` (parallel via `-n auto`, skips `@pytest.mark.slow`). Every new module needs `tests/test_<module>.py`. Use synthetic data fixtures, mock external APIs.
4. **Code review**: Dispatch `superpowers:code-reviewer` after implementation (mandatory).
5. **Frontend TypeScript**: Run `npx tsc --noEmit` from `frontend/` before every push. Local incremental cache hides missed symbol references that Railway's clean build catches. `vitest` alone is insufficient — it only typechecks imported files.
6. **Frontend QA**: If ANY frontend files changed, use Playwright MCP to visually verify every affected component on staging BEFORE promoting to prod. **BLOCKING gate.** Wait for Railway deploy (~2-3 min) before QA — don't test stale code.
7. **Railway deploy verification**: After every push, immediately call `list-deployments` to get the deployment ID, then `get-logs` with that ID to confirm success. `get-logs` without an ID returns the latest *successful* build — useless for debugging failures.

**CRITICAL: Fix ALL errors, including pre-existing ones.** Zero errors means zero errors.

**Mobile testing** — real CSS viewport sizes (not physical resolutions):
- Samsung Galaxy S24 (360x780) | iPhone 14 (390x844) | Pixel 9 (412x915) | iPhone 16 Pro Max (440x956)
- Check: text clipping, horizontal overflow, touch targets (44x44px min), chart scaling.

## Deployment

- **Railway** (PaaS): Two environments — **production** (branch `main`) and **staging** (branch `staging`).
- **Hetzner VPS**: Auto-deploys from `main-hetzner` via GitHub Actions. Dev branch: `hetzner-migration`.
- **Production URLs**: Frontend `https://cataclysm.up.railway.app` | Backend `https://backend-production-4c97.up.railway.app`
- **Staging URLs**: Frontend `https://cataclysm-staging.up.railway.app` | Backend `https://backend-staging-0dbd.up.railway.app`
- When pushing to GitHub, confirm remote URL — personal repo is github.com, NOT github.intuit.com.
- For full deployment guide: read `docs/deployment.md`.
- **`list-deployments` only shows the linked service.** Always check both services: pass `--service frontend` and `--service backend` explicitly when verifying a push that touches both.
- **NEVER set `DEV_AUTH_BYPASS=true` on staging.** It overrides ALL authentication — every request (including the real user's browser) authenticates as `dev-user`, hiding all real sessions. Remove: `railway variables delete DEV_AUTH_BYPASS --service backend` then `railway redeploy --service backend --yes`.

## Agent Playbook

Use specialized agents (via `Agent` tool with `subagent_type`) instead of doing everything in main context.

### Tier 1 — Use Routinely

| Scenario | Agent `subagent_type` | When |
|---|---|---|
| **Code review** | `superpowers:code-reviewer` | After every implementation (mandatory) |
| **Bug investigation** | `debugging-toolkit:debugger` | Any bug report, test failure, unexpected behavior |
| **Codebase exploration** | `Explore` | Finding files, tracing code paths, understanding architecture |
| **Python backend** | `python-development:python-pro` | Editing `cataclysm/` modules, data pipeline, dataclasses |
| **FastAPI** | `python-development:fastapi-pro` | Editing `backend/` routes, services, Pydantic models |
| **Frontend** | `frontend-mobile-development:frontend-developer` | React, Next.js, Tailwind, D3 charts. **Contrast rule**: Never use `colors.text.muted` for lines/borders/indicators — use `colors.text.secondary` min. Canvas lines >=1.5px, dash segments >=[6,3]. **Canvas events**: Use React event props (`onClick`, `onMouseMove`) directly on `<canvas>` — never `addEventListener` in `useEffect` when the canvas is conditionally rendered (e.g., behind a loading state). The ref object in deps never changes, so the effect only runs once, missing the canvas if it isn't mounted yet. **Touch tooltips**: Never use Radix `Tooltip` for info icons — hover-only, breaks on mobile (content vanishes in ~100ms). Use Radix `Popover` instead; keep visual parity with inline `className="bg-foreground text-background ..."` on `PopoverContent`. |
| **Writing tests** | `backend-development:test-automator` | Creating or expanding test suites |

### Tier 2 — Specific Scenarios

| Scenario | Agent `subagent_type` | When |
|---|---|---|
| **Architecture** | `comprehensive-review:architect-review` | New features, major refactors |
| **Security** | `comprehensive-review:security-auditor` | Auth changes, API endpoints, pre-deployment |
| **Performance** | `application-performance:performance-engineer` | Slow queries, caching strategy |
| **Coaching prompts** | `llm-application-dev:prompt-engineer` | Changes to `coaching.py` prompts |
| **Error handling** | `pr-review-toolkit:silent-failure-hunter` | After adding try/catch or fallback logic |
| **Type design** | `pr-review-toolkit:type-design-analyzer` | New dataclasses, Pydantic models, TS types |
| **Visual UI** | `accessibility-compliance:ui-visual-validator` | After layout changes. Flag `colors.text.muted` on functional elements. |

### Tier 3 — Occasional

| Scenario | Agent `subagent_type` |
|---|---|
| **Test coverage** | `pr-review-toolkit:pr-test-analyzer` |
| **Code simplification** | `pr-review-toolkit:code-simplifier` |
| **Deploy issues** | `cicd-automation:devops-troubleshooter` |
| **DB optimization** | `database-cloud-optimization:database-optimizer` |
| **Documentation** | `code-documentation:docs-architect` |

### Parallel Patterns

- **Full feature**: `fastapi-pro` + `frontend-developer` in parallel, then `code-reviewer`
- **Bug hunt**: `debugger` + `Explore` in parallel
- **Pre-deploy**: `security-auditor` + `performance-engineer` + `code-reviewer` in parallel
- **New module**: `python-pro` -> `test-automator` -> `code-reviewer`
