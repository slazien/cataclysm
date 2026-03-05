# CLAUDE.md

## Project Context

Motorsport telemetry analysis and AI coaching platform (Python + Next.js/FastAPI). Primary language is Python. Use Python idioms and tooling by default.

## Communication Style

Before implementing changes, ask clarifying questions rather than writing long inline markdown plans. Be concise and action-oriented.

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution
- **Match agent type to task** — see Agent Playbook section below

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness
- **Always run a code review agent** after finishing implementation — mandatory, not optional

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- Skip this for simple, obvious fixes — don't over-engineer

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests then resolve them
- **Use `debugging-toolkit:debugger` agent** for complex bugs

### 7. Never Underestimate Your Own Speed
- NEVER say "this is ambitious" or hedge about scope. You implement in hours, not weeks.
- Implement everything requested. No sandbagging, no "stretch goals".

## Task Management

1. *Plan First*: Write plan to tasks/todo.md with checkable items
2. *Verify Plan*: Check in before starting implementation
3. *Track Progress*: Mark items complete as you go
4. *Explain Changes*: High-level summary at each step
5. *Document Results*: Add review section to tasks/todo.md
6. *Capture Lessons*: Update tasks/lessons.md after corrections

## Core Principles

- *Simplicity First*: Make every change as simple as possible. Impact minimal code.
- *No Laziness*: Find root causes. No temporary fixes. Senior developer standards.
- *Minimal Impact*: Changes should only touch what's necessary. Avoid introducing bugs.

## Project Overview

Cataclysm is an AI-powered motorsport telemetry analysis and coaching platform for track day drivers. It ingests RaceChrono CSV v3 exports, processes them in the distance domain, detects corners, and generates AI coaching reports via the Claude API. Next.js + FastAPI, deployed on Railway from `main` branch.

For full architecture details, data flow diagrams, and module descriptions: read `docs/architecture.md`.

## Setup and Commands

**Always work inside the project venv.** Run `source .venv/bin/activate` before any Python command.

For setup instructions, command reference, and project structure: read `docs/developer-guide.md`.

## Code Conventions

- Python 3.11+, type hints required on all functions (mypy `disallow_untyped_defs`)
- Line length: 100 chars (ruff). Rules: E, F, W, I, N, UP, B, SIM
- All files start with `from __future__ import annotations`
- Module-level constants in UPPER_SNAKE_CASE
- Dataclasses for structured data, not dicts

## Quality Gates

All must pass before committing:

1. **Ruff check** — zero lint errors: `ruff check cataclysm/ tests/ backend/`
2. **Ruff format** — auto-format first: `ruff format cataclysm/ tests/ backend/`
3. **Mypy** — zero type errors: `dmypy run -- cataclysm/ backend/` (daemon mode, ~4s warm vs 30s cold)
4. **Tests** — all pass: `pytest tests/ backend/tests/ -v`
5. **Coverage** — target near-100%. Every new module needs `tests/test_<module>.py`. Test edge cases, error paths, boundary conditions.
6. **Code review** — ALWAYS dispatch `superpowers:code-reviewer` after implementation. Catches logic errors, architecture issues, and subtle bugs that linters miss.
7. **Frontend QA** — If ANY frontend files changed, use Playwright MCP to visually verify every affected component BEFORE merging to main. This is a BLOCKING gate — do NOT merge without QA.

**CRITICAL: Fix ALL errors, including pre-existing ones.** Zero errors means zero errors, no exceptions.

**CRITICAL: Frontend QA before merge.** Implement → quality gates → QA via Playwright → fix issues → THEN merge to main. Never skip QA.

## Testing Philosophy

- Every new module gets a `tests/test_<module>.py` companion
- Use synthetic data fixtures in `conftest.py` — never depend on real session files
- Mock external APIs (Claude API) to keep tests fast and deterministic
- **Use `backend-development:test-automator` agent** for creating comprehensive test suites

## Frontend QA Testing

**Always QA test frontend changes before marking them done.**

- Use Playwright MCP to verify every affected tab and interaction
- Check actual data values render (not just "doesn't crash") — numbers not "--", charts not empty
- Common failure: API envelope double-unwrapping (see `tasks/lessons.md`)
- **Use `accessibility-compliance:ui-visual-validator` agent** after layout changes
- **Mobile testing**: Test with real CSS viewport sizes (not physical resolutions). Use this research-verified device matrix covering 360px–440px width range (85%+ of mobile traffic):
  - **Samsung Galaxy S24** (360×780, DPR 3) — smallest common flagship, budget Android width
  - **iPhone 14** (390×844, DPR 3) — most popular iPhone form factor
  - **Pixel 9** (412×915, DPR 2.625) — standard Android reference
  - **iPhone 16 Pro Max** (440×956, DPR 3) — largest common viewport
  - Sources: blisk.io, yesviz.com, webmobilefirst.com, viewport-tester.com
  - Check: text clipping, horizontal overflow, touch targets (44x44px min), chart scaling, control bar fitting.

## Deployment

Two deployment targets (both active, independent branches):

- **Railway** (PaaS): Auto-deploys from `main` branch. Dev branch: `nextjs-rewrite`.
- **Hetzner VPS** (self-managed): Auto-deploys from `main-hetzner` via GitHub Actions. Dev branch: `hetzner-migration`.

For full deployment guide (Railway + Hetzner): read `docs/deployment.md`.

**Railway URLs**: Frontend `https://cataclysm.up.railway.app` | Backend `https://backend-production-4c97.up.railway.app`

**Hetzner**: `http://<VPS_IP>` (Caddy reverse proxy, auto-TLS when domain added)

## Workflow

- Always ask all clarifying questions before making assumptions
- Use agent teams wherever possible for parallel work
- Always commit and push after making changes. Do not wait to be asked.
- Dev branch: `nextjs-rewrite`. Production: `main` (Railway), `main-hetzner` (Hetzner VPS).
- When pushing to GitHub, confirm remote URL — personal repo is github.com, NOT github.intuit.com.
- **Image viewing**: When a URL points to an image that WebFetch can't render, download it locally (`curl -sL -o /tmp/filename.ext "URL"`), view with the Read tool, then delete when done. Never give up on viewing an image — always try the download approach.

## Agent Playbook

Use specialized agents (via the `Agent` tool with `subagent_type`) instead of doing everything in main context.

### Tier 1 — Use Routinely

| Scenario | Agent `subagent_type` | When |
|---|---|---|
| **Code review** | `superpowers:code-reviewer` | After every implementation (mandatory) |
| **Bug investigation** | `debugging-toolkit:debugger` | Any bug report, test failure, or unexpected behavior |
| **Codebase exploration** | `Explore` | Finding files, tracing code paths, understanding architecture |
| **Python backend work** | `python-development:python-pro` | Editing `cataclysm/` modules, data pipeline, dataclasses |
| **FastAPI work** | `python-development:fastapi-pro` | Editing `backend/` routes, services, Pydantic models |
| **Frontend work** | `frontend-mobile-development:frontend-developer` | React components, Next.js pages, Tailwind, D3 charts |
| **Writing tests** | `backend-development:test-automator` | Creating or expanding test suites, TDD workflows |

### Tier 2 — Use for Specific Scenarios

| Scenario | Agent `subagent_type` | When |
|---|---|---|
| **Architecture review** | `comprehensive-review:architect-review` | New features, major refactors, design decisions |
| **Security audit** | `comprehensive-review:security-auditor` | Auth changes, API endpoints, OWASP checks, pre-deployment |
| **Performance optimization** | `application-performance:performance-engineer` | Slow queries, response time issues, caching strategy |
| **Coaching prompt tuning** | `llm-application-dev:prompt-engineer` | Changes to `coaching.py` prompts or Claude API integration |
| **Error handling review** | `pr-review-toolkit:silent-failure-hunter` | After adding try/catch, fallback logic, or error handling code |
| **Type design review** | `pr-review-toolkit:type-design-analyzer` | New dataclasses, Pydantic models, or TypeScript types |
| **Visual UI validation** | `accessibility-compliance:ui-visual-validator` | After frontend layout changes, verify with screenshots |

### Tier 3 — Occasional Use

| Scenario | Agent `subagent_type` | When |
|---|---|---|
| **Test coverage analysis** | `pr-review-toolkit:pr-test-analyzer` | Before PRs, verify test adequacy |
| **Code simplification** | `pr-review-toolkit:code-simplifier` | After large features, clean up for maintainability |
| **Deployment issues** | `cicd-automation:devops-troubleshooter` | Railway failures, Docker build issues, CI problems |
| **Database optimization** | `database-cloud-optimization:database-optimizer` | PostgreSQL query tuning, migration planning |
| **Technical documentation** | `code-documentation:docs-architect` | Architecture docs, module documentation |
| **Comment quality** | `pr-review-toolkit:comment-analyzer` | After adding docstrings or documentation comments |

### Parallel Agent Patterns

For complex tasks, dispatch multiple agents simultaneously:
- **Full feature**: `fastapi-pro` (backend) + `frontend-developer` (frontend) in parallel, then `code-reviewer`
- **Bug hunt**: `debugger` (investigate) + `Explore` (search for similar patterns)
- **Pre-deploy review**: `security-auditor` + `performance-engineer` + `code-reviewer` all in parallel
- **New module**: `python-pro` (implement) → `test-automator` (write tests) → `code-reviewer` (review)
