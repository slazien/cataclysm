# Lessons Learned

## ⛔ QA Frontend Changes BEFORE Merging — #1 PRIORITY RULE
- **When**: After implementing ANY frontend changes, BEFORE merging to main
- **Rule**: Use Playwright MCP to visually verify every affected tab/component BEFORE merging to main. The mandatory sequence is:
  1. Implement on feature branch
  2. Run quality gates (ruff, mypy, tests, build)
  3. **QA with Playwright MCP** — verify every affected component
  4. Fix any issues found
  5. THEN merge to main
- **Anti-pattern**: Implement → merge to main → "Ready for feedback" → user asks "did you QA?" — This has happened TWICE (Batch 1 and Batch 2). NEVER AGAIN.
- **What to verify**: New components render with actual data, interactive elements work (click, hover, expand), new charts show data points, badges/labels display correct values, mobile layout doesn't break.
- **Why**: User called this out TWICE. This is a BLOCKING workflow step. CLAUDE.md Quality Gates item 7 now enforces this.

## Always Use Venv
- **When**: Every session, before any pip install or running any Python command
- **Rule**: `source .venv/bin/activate` before doing anything. Never install packages globally.
- **Why**: User explicitly requested this. CLAUDE.md now documents the venv requirement.

## API Response Envelope Double-Unwrapping
- **When**: Whenever frontend code accesses data from API hooks (useGains, useCorners, useConsistency, etc.)
- **Rule**: The `api.ts` functions already unwrap the backend envelope (extracting `.data` or `.corners` from `{session_id, data: {...}}`). Frontend components must NEVER access `.data` again on the result. The hook returns the inner payload directly.
- **Pattern**: If `api.ts` does `return resp.data`, then the component gets the inner object. Accessing `result.data.consistency` is WRONG — use `result.consistency` directly.
- **Why**: This bug caused gain analysis metrics to show "--" in the Coaching tab. The same pattern existed in multiple places (getCorners, getAllLapCorners, getConsistency, getGains, getGrip).

## QA Testing Must Verify Data Values, Not Just Rendering
- **When**: After any frontend change, especially API integration work
- **Rule**: QA testing must go beyond "does the tab render without crashing". It must verify:
  1. Every metric card shows actual numbers, not "--" or "No data"
  2. Every chart has visible data points/lines/bars
  3. Interactive elements work (hover, click, drag, zoom)
  4. Data values are plausible (not NaN, not 0 when data exists)
- **Why**: Surface-level QA ("tab doesn't crash") missed the gain analysis "--" bug and other data display failures. The user rightfully called this out as inadequate.

## Always Check Frontend/Backend Contract After api.ts Changes
- **When**: After modifying any function in api.ts (especially envelope unwrapping)
- **Rule**: Grep ALL consumers of the modified API function and verify they access data at the correct nesting level. A change in api.ts ripples through every component that uses that hook.
- **Command**: `grep -rn "useGains\|useCorners\|useConsistency" frontend/src/components/`

## Commit and Push After Every Logical Change — CRITICAL, REPEATED FAILURE
- **When**: IMMEDIATELY after ANY file edit — before doing QA, before doing verification, before moving to the next task. This is the #1 most violated rule.
- **Rule**: The moment you finish editing file(s) and the change is complete, run `git add <files> && git commit && git push`. Do NOT continue to other work first. Do NOT "verify first then commit". Commit first, verify second.
- **Enforcement checklist** (run after every edit):
  1. `git diff --stat` — are there uncommitted changes? If yes, STOP and commit+push NOW.
  2. `git status` — is branch ahead of remote? If yes, STOP and push NOW.
- **Why**: User has called this out MULTIPLE TIMES across sessions. CLAUDE.md explicitly says "Always commit and push after making changes." This is a blocking requirement, not a suggestion. The app is deployed from the remote branch — unpushed changes don't exist to the user.
- **Anti-pattern**: "I'll commit after QA" or "I'll batch these changes" or "Let me verify first" — NO. Commit and push immediately after each logical change, then QA.

## NEVER Ignore Pre-existing Errors — Fix Them Immediately
- **When**: Any time you run quality gates (mypy, ruff, tests) and see errors — even if they pre-date your changes
- **Rule**: Fix ALL errors, not just the ones you introduced. Pre-existing errors are not "someone else's problem" — they are YOUR problem. Saying "those are pre-existing" and moving on is sloppy and unacceptable.
- **Why**: The user explicitly called this out: "fix the pre existing errors too, don't just leave them, this is sloppy." Leaving known broken things is unprofessional. A staff engineer would never ship code while ignoring known failures in the same codebase.
- **Pattern**: When mypy/ruff/pytest shows errors, triage them ALL. If they're in code you touched, fix them. If they're in adjacent code, fix them too. Zero errors means zero errors.

## Create .env File for Docker Compose Secrets
- **When**: Setting up Docker Compose with API keys or secrets
- **Rule**: Create a `.env` file (gitignored) in the project root with secrets like ANTHROPIC_API_KEY. docker-compose.yml uses `${ANTHROPIC_API_KEY:-}` syntax to read from environment/`.env`.

## Never Underestimate Your Own Speed
- **When**: Scoping work, estimating effort, or discussing timelines with the user
- **Rule**: NEVER say things like "this is ambitious for 3 weeks" or hedge about scope being too large. You are Claude Code with parallel agents — you implement features in hours, not days or weeks. A human's 3-week deadline gives you massive runway. Implement everything requested without sandbagging.
- **Anti-pattern**: "That's ambitious", "we might run out of time", "let's prioritize in case we can't finish", "stretch goal". These phrases signal a human pace mindset. Delete them from your vocabulary.
- **Why**: User called this out directly. Claude Code with subagents can parallelize massively. A 6-feature scope that would take a human team weeks is hours of agent work.

## Use Research-Verified CSS Viewport Sizes for Mobile Testing ([2026-03-05])

**Pattern**: Always use real, research-verified CSS viewport sizes for mobile testing — never guess or estimate. Cite the source (blisk.io, yesviz.com). Always clarify "CSS viewport" vs "physical resolution" when discussing sizes with the user.

**Why**: User pushed back TWICE when I listed viewport sizes without sources — they thought I was making up numbers. CSS viewport (what the browser reports) differs from physical resolution (actual pixels). E.g., Galaxy S24 is 1080×2340 physical but 360×780 CSS viewport at DPR 3. Without citing sources, the user can't verify correctness.

**Device matrix** (see CLAUDE.md for full table):
- Samsung Galaxy S24: 360×780 (DPR 3)
- iPhone 14: 390×844 (DPR 3)
- Pixel 9: 412×915 (DPR 2.625)
- iPhone 16 Pro Max: 440×956 (DPR 3)

**Anti-pattern**: Guessing viewport sizes from physical specs, or listing devices without research. ALWAYS web-search for "[device name] CSS viewport size" from yesviz.com or blisk.io before testing.

## Canvas Charts Need Explicit Height, Not min-height
- **When**: Changing mobile layout for D3 canvas chart containers (SpeedTrace, DeltaT, BrakeThrottle, CornerSpeedOverlay, BrakeConsistency)
- **Rule**: Canvas charts use `h-full` which resolves against the parent's `height` property, NOT `min-height`. If you remove `flex-1` from a chart container on mobile, you MUST replace `min-h-[16rem]` with `h-[16rem]` (explicit height). On desktop, use `lg:h-auto` so `lg:flex-1` can take over.
- **Why**: `min-height` does not establish a computable height for `height: 100%` children. The `useCanvasChart` hook's `ResizeObserver` sees 0 height → canvas never initializes → charts disappear entirely. This caused a regression where Speed Trace and Delta-T went completely missing on mobile.
- **Pattern**: `h-[16rem] lg:h-auto lg:flex-1` (mobile: fixed height, desktop: flex-proportional)

## Build-Verify Before Every Push
- **When**: EVERY time before `git push`, for frontend and/or backend changes
- **Rule**: Run `cd frontend && npx next build` (for frontend changes) and/or `pytest` (for backend changes) BEFORE pushing. Commit first (per the commit-immediately rule), but verify the build before pushing to remote.
- **Sequence**: Edit → `git add` + `git commit` → `next build` / `pytest` → fix if broken → amend or new commit → `git push`
- **Why**: User called this out ("did you test before pushing?"). Pushing broken code to remote is worse than a slightly delayed push. The build verification takes ~30s and catches TypeScript errors, import issues, and compilation failures.

## False Brake Attribution from Overlapping Search Windows
- **When**: Working on brake point detection or corner KPI extraction
- **Rule**: When searching for a brake point before a corner, the search window must not extend into the previous corner's zone. Use `prev_exit_idx` parameter in `_find_brake_point` to clamp the search start. Without this, closely-spaced corners (e.g. T9→T10 at Barber, ~350m apart) will attribute the previous corner's trail braking to the next corner.
- **Pattern**: `_find_brake_point(..., prev_exit_idx=prev_exit)` — callers must track the previous corner's exit index and pass it through.
- **Companion fix**: Flat-out corners need explicit `character="flat"` annotations in `track_db.py` OfficialCorner definitions, which suppress brake recommendations in `CornerRecommendation` and signal the LLM not to coach braking. Even with correct brake detection, the LLM will fixate on tiny deceleration events without this hint.

## Visual Verification of Track Corner Directions Is Mandatory
- **When**: Creating or modifying corner directions in `track_db.py`
- **Rule**: NEVER trust algorithm-derived directions (heading-rate sign analysis) as the sole source. Always visually compare against a reference track map image (e.g., racingcircuits.info). Download the image locally if WebFetch can't render it. Compare EVERY corner's direction against the map — not just the ones you think are ambiguous.
- **Pattern**: After setting directions, print the corner table (`T#, Name, Direction`) and visually walk around the reference map corner by corner. Does T1 go right on the map? Check. Does T2 go right? Check. All 9 corners.
- **Why**: Roebling Road had 4 of 9 corners with wrong directions (T4, T5, T6, T7). The heading-rate algorithm got the sign wrong at complex curves where approach curvature differs from the main arc. A single visual comparison against the reference map would have caught all four errors immediately. The first "fix" only caught T7 because it didn't verify the other corners against the image.
- **Anti-pattern**: "I'll just fix the one corner that was reported wrong" — NO. When one direction is wrong, assume others might be too and verify ALL of them.

## Never Use Time Estimates in Plans
- **When**: Writing implementation plans, scoping work, describing waves/phases
- **Rule**: NEVER use day/week/time estimates (e.g., "~2 days", "1-2 weeks") in plans or task descriptions. You are Claude Code with parallel agents — you implement in hours, not days or weeks. Instead, note which tasks are parallelizable so agents can be dispatched concurrently.
- **Anti-pattern**: "Wave 1 (~1-2 weeks)", "Effort: ~2 days", "This phase takes 3 weeks". Replace with file counts and parallelization notes.
- **Why**: User caught this directly. CLAUDE.md says: "NEVER say 'this is ambitious' or hedge about scope. You implement in hours, not weeks." Time estimates signal a human-pace mindset that contradicts the agent-parallel reality.

## Keep Dockerfile Dependencies in Sync with pyproject.toml — CRITICAL
- **When**: Adding ANY new Python dependency to `backend/pyproject.toml`
- **Rule**: ALWAYS also add the dependency to `Dockerfile.backend` line 11 (the explicit `pip install` list). The Dockerfile does NOT auto-read `backend/pyproject.toml` — it installs the root `pyproject.toml` (cataclysm core) and then manually lists backend deps.
- **Verification**: After adding a dep to pyproject.toml, immediately `grep` the Dockerfile to confirm it's there.
- **Why**: Adding `slowapi` to pyproject.toml without updating `Dockerfile.backend` caused a production crash (`ModuleNotFoundError: No module named 'slowapi'`) that took down the backend completely. The backend crash-looped for multiple deploy cycles.
- **Future improvement**: Consider switching Dockerfile to `pip install -e ./backend` or `pip install --no-cache-dir -r requirements.txt` to avoid maintaining two dependency lists.

## Raw SQL Must Include ALL NOT NULL Columns — ORM Defaults Don't Apply
- **When**: Writing raw SQL INSERT statements that bypass the ORM (e.g. `text("INSERT INTO ...")`)
- **Rule**: Check the ORM model for ALL `Mapped[str]` / `Mapped[bool]` (non-Optional) columns with `default=`. Raw SQL bypasses ORM `default=` values. You must explicitly include those columns with their default values in the INSERT statement.
- **Pattern**: Compare `text("INSERT INTO users (id, email, name, avatar_url)")` against `class User` model — if `skill_level`, `role` are NOT NULL with ORM defaults, they MUST be in the raw SQL.
- **Why**: Hit this TWICE in `ensure_user_exists` migration path. First: FK violation (UPDATE FKs before new user row existed). Second: NOT NULL violation on `skill_level` because raw INSERT didn't include it. Both caused production 500 errors on CSV upload.

## Research Before Guessing — Don't Present Unverified Facts ([2026-03-05])

**Pattern**: When presenting technical specifications (device sizes, API versions, library features), ALWAYS research first. Never present estimated or assumed values as fact. If the user asks for something you don't know, say "let me research that" and use WebSearch — don't guess.

**Why**: User had to tell me THREE times: (1) "perhaps some online research would be needed", (2) "use real resolutions, 17 pro max doesn't have 440x956 resolution cmon" (it actually does — but I hadn't cited sources), (3) "where did you get those from?!?!" Each correction was friction that could have been avoided by researching upfront and citing sources.

**Anti-pattern**: "iPhone 17 Pro Max is probably around 440×956" or "I'll estimate OnePlus 11 Pro as 412×915". NEVER estimate device specs — always look them up.

## Research Domain Knowledge Before Implementing ([2026-03-05])

**Pattern**: Before implementing any feature involving motorsport domain knowledge (vehicle dynamics, tire physics, G-force analysis, coaching methodology, signal processing thresholds), do iterative online research. Start broad, then probe deeper with technical terms from initial results. 2-3 rounds minimum for non-trivial domain topics. Cite sources.

**Why**: Used a symmetric traction circle for G-G diagram grip utilization when the entire motorsport engineering community uses friction ellipses or observed-envelope methods. A car with 0.3G acceleration and 1.0G braking was being unfairly scored because the circle radius was set by braking. Online research immediately revealed the correct approach (angular sector envelope comparison). Coding intuition alone is insufficient for domain-specific algorithms.

**Anti-pattern**: "I'll just use a circle because it's simpler" or "This formula seems reasonable" without checking what professional telemetry tools (MoTeC, AiM) or racing engineering resources (YourDataDriven, TrailBrake, SAE papers) actually use.

## Verify Components Are Actually Imported Before Wiring Into Them ([2026-03-05])

**Pattern**: Before adding features to a component, `grep -rn "import.*ComponentName"` to confirm it's actually used in the app. Exported-but-never-imported components are dead code — your feature will be invisible.

**Why**: Wired the `SkillLevelMismatchBanner` into `ReportSummary` (inside `CoachPanel`), which is exported from its file but never imported anywhere in the app. The actual active component is `SessionReport`. Only caught this via Playwright QA when the banner didn't appear. Wasted a full implementation cycle on dead code.

**Verification command**: `grep -rn "import.*ComponentName\|from.*ComponentName" frontend/src/` — if zero results outside the component's own file, it's dead code.

**Anti-pattern**: Seeing a component that looks like the right place (e.g. `ReportSummary` for coaching reports) and wiring into it without checking if it's actually rendered. Always trace the import chain back to a page or layout.

## Verify ALL Files Are Committed After Multi-File Changes ([2026-03-05])

**Pattern**: After any commit that touches imports or cross-file references, run `git status` and verify that ALL modified files were included. Pay special attention when file A imports a new symbol from file B — both files must be committed together.

**Why**: Commit `cc8d9dd` added `from backend.api.schemas.coaching import SkillLevel` to the coaching router but forgot to commit the schema file that actually defines `SkillLevel`. This crashed the **entire backend** in production with `ImportError`. Every request failed. The fix was trivial (commit the missing file) but the outage was total.

**Error signature**: `ImportError: cannot import name 'X' from 'module.Y'` in Railway deploy logs.

**Verification**: After `git commit`, immediately run `git diff --stat` to check for remaining unstaged changes in related files. If your commit added an import, grep the imported module to see if it has uncommitted changes: `git diff -- <imported_file>`.

**Anti-pattern**: Staging only the file you were "working in" without checking if dependent files also changed. Partial commits that break cross-file contracts are production killers.

## Use Polling Loops for Async Background Task Completion in Tests ([2026-03-05])

**Pattern**: When testing endpoints that spawn background tasks via `asyncio.create_task()` or `BackgroundTasks`, use a polling loop — not a fixed sleep. Fixed sleeps (`sleep(0)`, `sleep(0.01)`, even `sleep(0.2)`) are all unreliable because task completion time varies with system load.

```python
# GOOD — polling loop, fast and reliable
for _ in range(50):
    await asyncio.sleep(0.05)
    if not is_generating(session_id, "intermediate"):
        break
assert not is_generating(session_id, "intermediate")

# BAD — fixed sleep, flaky
await asyncio.sleep(0.01)
assert not is_generating(session_id, "intermediate")
```

**Why**: `sleep(0)` yields once (insufficient for Starlette's task runner). `sleep(0.01)` works most of the time but is flaky under load — caused `test_run_generation_unmarks_generating_on_error` to fail intermittently. The polling loop converges in ~50-100ms on average but tolerates up to 2.5s, making it both fast and reliable.

**Error signature**: Tests that POST to trigger generation then GET/assert the result fail intermittently with 404, `status != "ready"`, or stale `is_generating` flags.

## Always Run Code Reviewer After Implementation
- **When**: After finishing ANY implementation task — features, bug fixes, refactors
- **Rule**: Dispatch the code reviewer agent (`superpowers:code-reviewer` or `code-review:code-review`) to review all changed files. This is in ADDITION to automated checks (ruff, mypy, tests), not a replacement.
- **Why**: User explicitly requested this. Code reviewers catch logic errors, architectural issues, and subtle bugs that linters and tests miss. Added to CLAUDE.md Quality Gates (item 6) and Verification Before Done section.

