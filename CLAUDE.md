# CLAUDE.md

## Project Context

AI motorsport coaching platform (Python + Next.js/FastAPI). Primary lang: Python.

## Communication Style

Ask clarifying Qs before implementing. Concise, action-oriented.

## Workflow

1. **Plan first** — Plan mode for any non-trivial task (3+ steps/arch). Sideways → STOP & re-plan.
2. **Subagents** — One task per agent. Match type to task (see Playbook).
3. **Self-improve** — After any correction: `tasks/lessons.md`. **Rule-writing standard**: CLAUDE.md entries = action only, no "why" prose, use symbols (→ · ≥ ≠), abbreviate freely, merge related bullets. lessons.md = Pattern+Why+Error triplet, tight sentences, no padding. Never duplicate info between files. If a rule needs more than 2 lines in CLAUDE.md, the "why" belongs in lessons.md only.
4. **Verify** — Proof before done (tests/logs). Always `superpowers:code-reviewer` post-impl.
5. **Elegance** — Non-trivial: "simpler way?" Skip for quick fixes.
6. **Bugs** — Fix autonomously. Complex → `debugging-toolkit:debugger`.
7. **No hedging** — Never say "ambitious." Implement everything.
8. **Domain research** — Physics/coaching feature: WebSearch first (SAE, MoTeC, YourDataDriven, TrailBrake, Driver61). Never invent algorithms from coding intuition.
9. **Task tracking** — Plan → `tasks/todo.md`, mark complete, capture lessons.
10. **Commit immediately** — After every change. Push `staging`. NEVER push `main` unless user says "deploy to prod."
12. **Temp branch lifecycle** — After merging `temp/<feature>` → staging, NEVER delete the temp branch. User must approve deletion manually (rollback safety).
11. **Images** — `curl -sL -o /tmp/f.ext "URL"`, Read tool, delete.

## Core Principles

Simplicity (minimal impact) · No shortcuts (root causes, senior standards) · Minimal blast radius · **Pattern propagation**: when fixing a bug, grep for the same pattern elsewhere and fix all instances in the same commit.

## Project Overview

Ingests RaceChrono CSV v3, processes in distance domain, detects corners, generates AI coaching via Claude API. Next.js + FastAPI on Railway (`main` branch).

Arch → `docs/architecture.md` | Setup → `docs/developer-guide.md` | **Always activate venv**: `source .venv/bin/activate`

## Code Conventions

- Python 3.11+, all fns typed (`mypy disallow_untyped_defs`), line len 100, rules: E F W I N UP B SIM
- All files: `from __future__ import annotations`
- Constants: UPPER_SNAKE_CASE · Structured data: dataclasses not dicts
- DB `user_id` columns: plain `String`, NEVER `ForeignKey("users.id")` — OAuth/JWT users may lack rows in `users` table. Removing a FK → also remove its `relationship()` (orphan poisons ALL mappers).

## Quality Gates

All must pass before commit:

1. **Ruff**: `ruff format cataclysm/ tests/ backend/` → `ruff check cataclysm/ tests/ backend/`
2. **Mypy**: `dmypy run -- cataclysm/ backend/` (~4s warm)
3. **Tests**: `pytest tests/ backend/tests/ -v -n auto`. New module → `tests/test_<module>.py`. Synthetic fixtures, mock external APIs.
4. **Code review**: `superpowers:code-reviewer` (mandatory)
5. **Frontend TS**: `cd frontend && npx tsc --noEmit` before every push. Incremental cache hides errors Railway's clean build catches; `vitest` alone insufficient.
6. **Frontend QA**: ANY frontend change → Playwright visual verify on staging post-deploy. **BLOCKING.** Wait ~2-3 min.
7. **Deploy verify**: `list-deployments --service <svc>` → get ID → `get-logs <id>`. Specify service explicitly (default = linked svc only).

**CRITICAL: Fix ALL errors incl. pre-existing. Zero means zero.**

**Mobile viewports** (CSS px): S24 360×780 | iPhone14 390×844 | Pixel9 412×915 | iPhone16PM 440×956
Check: text clip, horiz overflow, touch targets ≥44px, chart scale.
**Fixed-position rule**: Before adding any `position:fixed` element, grep for ALL existing `fixed` elements → verify no overlap at every breakpoint.
**Tooltip rule**: Never use Radix `Tooltip` (hover-only) for interactive content. Always use `Popover` — tap-to-open stays open until dismissed. `Tooltip` fires enter+leave in rapid succession on touch → immediately disappears.

## Deployment

| Env | Branch | Frontend | Backend |
|-----|--------|----------|---------|
| prod | `main` | cataclysm.up.railway.app | backend-production-4c97.up.railway.app |
| staging | `staging` | cataclysm-staging.up.railway.app | backend-staging-0dbd.up.railway.app |

- Hetzner: `main-hetzner` via GH Actions. Dev: `hetzner-migration`.
- GitHub remote: github.com (not github.intuit.com). Full guide: `docs/deployment.md`.
- **NEVER `DEV_AUTH_BYPASS=true` on staging.** Bypasses ALL auth → every req as `dev-user` → real sessions hidden. Fix: `railway variables delete DEV_AUTH_BYPASS --service backend` + `railway redeploy --service backend --yes`.

## Agent Playbook

### Tier 1 — Routine

| Scenario | `subagent_type` |
|----------|----------------|
| Code review (mandatory post-impl) | `superpowers:code-reviewer` |
| Bug investigation | `debugging-toolkit:debugger` |
| Codebase exploration | `Explore` |
| Python backend (`cataclysm/`, pipeline) | `python-development:python-pro` |
| FastAPI (`backend/` routes, Pydantic) | `python-development:fastapi-pro` |
| Frontend (React, Next.js, Tailwind, D3) | `frontend-mobile-development:frontend-developer` |
| Tests | `backend-development:test-automator` |

**Frontend rules** (pass to frontend agent):
- Contrast: min `text-secondary` (never `text.muted`) for lines/borders/indicators
- Canvas: lines ≥1.5px, dashes ≥[6,3]
- Canvas events: use React props (`onClick`, `onMouseMove`) on `<canvas>` — not `addEventListener` in `useEffect` (ref never changes in deps → effect fires once, misses conditional-mount canvas)
- Loading state: use `isPending` (not `isLoading`) in chart guards — `isLoading = isPending && isFetching` misses paused queries (mobile background/network blip). Guard order in chart early-returns: (1) prerequisites (e.g. `selectedLaps.length === 0`), (2) `isPending` spinner, (3) data validity (`!data?.available`).
- Touch tooltips: never Radix `Tooltip` for info icons (hover-only, vanishes ~100ms on mobile). Use Radix `Popover` with `className="bg-foreground text-background ..."` on `PopoverContent`.
- Overlay/floating UI: idle state = minimum footprint (small dot/pin, not wide bars). Expanded = dark glassmorphic (`bg-[var(--bg-surface)]/70 backdrop-blur-xl`), never opaque pastels. This is a dark-theme data-dense app.

### Tier 2 — Specific

| Scenario | `subagent_type` |
|----------|----------------|
| Architecture | `comprehensive-review:architect-review` |
| Security | `comprehensive-review:security-auditor` |
| Performance / caching | `application-performance:performance-engineer` |
| Coaching prompts | `llm-application-dev:prompt-engineer` |
| Error handling / fallbacks | `pr-review-toolkit:silent-failure-hunter` |
| Type design | `pr-review-toolkit:type-design-analyzer` |
| Visual UI / a11y | `accessibility-compliance:ui-visual-validator` |
| Test coverage | `pr-review-toolkit:pr-test-analyzer` |
| Code simplify | `pr-review-toolkit:code-simplifier` |
| Deploy issues | `cicd-automation:devops-troubleshooter` |
| DB optimize | `database-cloud-optimization:database-optimizer` |
| Docs | `code-documentation:docs-architect` |

### Parallel Patterns

- Full feature: `fastapi-pro` + `frontend-developer` → `code-reviewer`
- Bug hunt: `debugger` + `Explore`
- Pre-deploy: `security-auditor` + `performance-engineer` + `code-reviewer`
- New module: `python-pro` → `test-automator` → `code-reviewer`
