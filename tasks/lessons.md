# Lessons Learned

## Playwright `browser_evaluate` Requires `function` Parameter (2026-03-08)

**Pattern**: When calling `browser_evaluate` in Playwright MCP, always use the `function` parameter with the format `"() => { ... }"`. Do NOT use a `script` parameter — it doesn't exist.

**Why**: Using `script` causes `"expected string, received undefined"` silently. The tool only accepts `function` as the parameter name, and the value must be a zero-argument arrow function string.

**Error signature**: `"expected string, received undefined"` when passing `script:` instead of `function:`

## Playwright Click on Off-Screen Element Times Out — Use Escape Key (2026-03-08)

**Pattern**: If a `browser_click` times out because the button is outside the viewport (e.g., a modal close button scrolled above the visible area), use `browser_press_key` with `"Escape"` instead. Never retry the same off-screen click.

**Why**: Playwright's `click` requires the element to be interactable/in viewport. Close buttons and dismiss actions always have keyboard equivalents. `browser_press_key` with `"Escape"` closes virtually all dialogs/modals/drawers.

## React Query 3-Retry Default Delays Public Error State ~5s (2026-03-08)

**Pattern**: Public pages using React Query (e.g., `/share/[token]`) show a loading spinner for ~5 seconds before displaying 404/not-found error state. This is NOT a bug — it's React Query's default retry behavior (3 retries with exponential backoff). When testing public 404 routes with Playwright, wait 5-6 seconds before asserting error state.

**Why**: React Query retries failed queries 3 times by default. On a 404 this takes ~5s total. Using `browser_evaluate` with a `setTimeout(resolve, 5000)` promise is the reliable way to wait before asserting.

## Playwright Modal Scroll: Target `[role="dialog"]` Not Inner Overflow Divs (2026-03-08)

**Pattern**: To scroll a modal's content via `browser_evaluate`, target `document.querySelector('[role="dialog"]')` and set `element.scrollTop = N` directly. Do NOT try to find inner `.overflow-y-auto` divs — they may not be the actual scroll container.

**Why**: Shadcn/Radix `Dialog` makes the `[role="dialog"]` element itself the scroll container. Inner divs with `overflow-y-auto` class exist for styling but setting `scrollTop` on them is a no-op. The dialog element's `scrollHeight > clientHeight` confirms it's scrollable.

## Playwright Accessibility Snapshot ≠ Visual Render During Hydration (2026-03-08)

**Pattern**: `browser_snapshot` taken before React hydration completes shows SSR/pre-hydration content (e.g., WelcomeScreen skeleton) even if `browser_take_screenshot` shows the correct post-hydration state. Always use `browser_take_screenshot` for visual verification, and `browser_snapshot` only after confirming hydration is complete.

**Why**: The accessibility tree is built from the DOM at snapshot time. SSR renders the initial state; Next.js hydration then updates state from client stores/hooks. During this window, the snapshot and visual render diverge.

## MagicMock Fails Python Format Specs (2026-03-08)

**Pattern**: When mocked functions return objects whose attributes get f-string formatted (e.g., `f"{result.mu:.2f}"`), return real dataclass instances — not `MagicMock()`. MagicMock doesn't implement `__format__` with spec strings.

**Why**: `apply_calibration_to_params` mock returned `MagicMock()`. The refactored `get_optimal_profile_data` used `f"{vehicle_params.mu:.2f}"` for the cache key, causing `TypeError: unsupported format string passed to MagicMock.__format__`. Fixed by returning `VehicleParams(mu=1.15, max_accel_g=0.42, max_decel_g=1.05, max_lateral_g=1.15, calibrated=True)`.

**Error signature**: `TypeError: unsupported format string passed to MagicMock.__format__`

## asyncio.ensure_future Fails in Threadpool (2026-03-08)

**Pattern**: Code running inside `asyncio.to_thread()` has no event loop. `asyncio.ensure_future()` raises `RuntimeError`. For best-effort async fire-and-forget from threadpool code, use `contextlib.suppress(RuntimeError)`.

**Why**: `_run_pipeline_sync` called `invalidate_track_physics_cache(slug)` which used `asyncio.ensure_future(db_invalidate_track(...))`. Since `_run_pipeline_sync` runs in `asyncio.to_thread()`, no event loop exists → `RuntimeError`. The in-memory invalidation still works; DB entries self-correct via code_version on next read.

**Error signature**: `RuntimeError: There is no current event loop in thread 'ThreadPoolExecutor-0_0'`

## Refactoring Delegation Breaks Mock Targets (2026-03-08)

**Pattern**: When refactoring function A to delegate to function B internally, update tests to mock B instead of A's former internals. The old mock targets are no longer called.

**Why**: `get_optimal_comparison_data` was refactored to call `get_optimal_profile_data` (which handles the velocity solver). Tests that mocked `apply_calibration_to_params` and `solve_velocity_profile` individually broke — those functions are no longer called in the comparison path. Fixed by mocking `get_optimal_profile_data` directly with a realistic result dict.

**Error signature**: Tests pass their mocked internal functions but the outer function returns unexpected results or calls unmocked code paths.

## Commit Before Reporting "Done" — Not After (2026-03-08)

**Pattern**: Commit+push to `staging` BEFORE sending the "Done" message to the user. The workflow is: edit → commit → push → then respond. Never respond first and commit later.

**Why**: Said "Done." after editing `help-content.ts`, user had to ask "did you merge to staging?" and then direct me to re-read the rules. The rule exists in CLAUDE.md and MEMORY.md but execution failed because task-completion reporting felt like the terminal step. Commit is the terminal step.

**Error signature**: Responding "Done." or summarising what was changed without having already run `git commit && git push`.

## Radix DropdownMenu Fails When Custom Overlays Coexist (2026-03-08)

**Pattern**: Don't refactor hand-rolled dropdowns to Radix `DropdownMenu` when the app has custom overlay components (like `SettingsPanel`) with their own document-level `keydown`/`mousedown` listeners and fixed z-index overlays. Radix's `DismissableLayer` doesn't reliably dismiss when a separate `z-40` overlay + Escape handler is active. Hand-rolled `useEffect` with document-level `mousedown` (click-outside) and `keydown` (Escape) listeners works universally regardless of overlay hierarchy.

**Why**: Attempted to refactor the TopBar user menu to Radix DropdownMenu for better accessibility. Menu rendered correctly with ARIA roles but Escape and click-outside dismissal failed when SettingsPanel was open (its overlay and Escape handler intercepted events before Radix's DismissableLayer). Wasted significant time debugging and had to revert. The hand-rolled approach with `e.stopPropagation()` on Escape prevents bubbling to SettingsPanel's handler.

**Error signature**: Radix DropdownMenu opens correctly, shows proper ARIA roles (`menu`, `menuitem`), but pressing Escape or clicking outside doesn't close it when another panel/overlay is visible.

## Radix Tooltip Breaks on Mobile Touch — Use Popover Instead (2026-03-08)

**Pattern**: Never use Radix `Tooltip` for info icons that must work on mobile. Tooltip is hover-only: on touch, `pointerdown` opens it and `blur`/`pointerleave` (~100ms later) closes it immediately. Use Radix `Popover` instead — it opens on click and stays open until the user taps outside or presses Escape.

**Why**: `InfoTooltip.tsx` used `<Tooltip>` and all `?` help icons were effectively invisible on mobile (text disappeared almost immediately after tapping). Swapping to `<Popover>` with identical visual styling (inline `bg-foreground text-background` on `PopoverContent`) fixed it for all charts at once.

**Error signature**: Mobile user taps `?` icon → tooltip appears for ~100ms → vanishes. No JS error; purely a pointer-event semantic mismatch.

## ⛔ NEVER Push to Main — Not Even Hotfixes (2026-03-07)

**Pattern**: NEVER push to `main` directly. Always fix on `staging`, verify, then wait for the user to explicitly say "push to main" or "merge staging into prod." Asking "should I push to main?" and getting "yes" is leading the witness — the user must initiate it.

**Why**: User corrected me harshly. Even when prod is crash-looping, the fix goes to staging first. "Fix prod" ≠ "push to main." CLAUDE.md is unambiguous: "NEVER push to `main` unless the user explicitly says to deploy to prod."

**Error signature**: Any thought pattern like "prod is broken, I should push directly to main to fix it fast."

## Verify Both Sides of API Changes Before Merging (2026-03-07)

**Pattern**: When changing a function's call site (adding new kwargs), always verify the function definition also has those parameters on the TARGET branch. Never assume companion changes from a feature branch are present.

**Why**: `pipeline.py` on `main` was updated to pass `resampled_laps` and `coaching_laps` to `analyze_corner_lines()`, but the function in `corner_line.py` still only accepted 3 args. This caused a production crash loop (`TypeError: unexpected keyword argument`) that prevented all session loading.

**Error signature**: `TypeError: func() got an unexpected keyword argument 'X'` after a partial merge.

## LLM Prompt Context Values Bypass the Speed Marker System (2026-03-08)

**Pattern**: When fixing unit bugs in AI coaching text, fix BOTH layers: (1) the backend prompt context (give values in the primary unit so the LLM quotes the right unit) AND (2) a frontend legacy fallback in `resolveSpeedMarkers` for old cached reports. The `{{speed:N}}` marker system only works for values the LLM generates in its *output* — values given in the *input context* are echoed verbatim by the LLM.

**Why**: `_format_weather_context` passed `wind_speed_kmh` as "20 km/h". The LLM echoed "20 km/h" into coaching text. Imperial users saw km/h. Fixing only the prompt would leave existing cached reports broken; fixing only the frontend would leave the LLM generating wrong units for new reports. The two-layer defense (backend unit + frontend fallback) is the correct pattern.

**Error signature**: Imperial users see "km/h", "°C", or "mm" in AI coaching text despite having imperial units selected.

## Check git branch Before Committing in Any Session With Temp Branches (2026-03-08)

**Pattern**: Always run `git branch --show-current` immediately before `git commit` in any session where temp branches may exist from previous work. Never assume you're on staging.

**Why**: Committed the weather-units fix to `temp/velocity-model-fix` (a leftover branch from a previous session) instead of `staging`. Required a manual merge to staging and branch cleanup. Wasted time; could have contaminated the commit with unrelated in-progress changes on that branch.

**Error signature**: `git commit` succeeds but `git push origin staging` fails with "non-fast-forward" — you're not on staging.

## Docker pip-install Changes __file__ Resolution (2026-03-07)

**Pattern**: Never use `Path(__file__).parent.parent / "data"` for writable data dirs in packages that get pip-installed. In Docker, `__file__` resolves to `site-packages/` which is read-only. Use an env var with a fallback.

**Why**: `track_reference.py` used `Path(__file__).parent.parent / "data" / "track_reference"` which worked locally but resolved to `/usr/local/lib/python3.12/site-packages/data/track_reference` in Docker — read-only, causing `PermissionError` on every upload.

**Error signature**: `PermissionError: [Errno 13] Permission denied: '/usr/local/lib/python3.12/site-packages/data'`

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

## Read Repository Instructions First ([2026-03-05])
- **When**: At the start of any substantive task in this repo, before planning, environment changes, or implementation.
- **Rule**: Read `CLAUDE.md` first and follow its workflow constraints before touching code.
- **Why**: I started fixing the numerical trust issues before re-reading the repo instructions. That created avoidable churn around task tracking, verification flow, and environment handling.

## Check For An Existing Project Venv Before Creating Anything New ([2026-03-05])
- **When**: Any time Python tooling or missing dependencies become relevant.
- **Rule**: Check for `./.venv` and use it before creating a new environment. If it exists, verify it with a quick import check instead of assuming it is unusable.
- **Why**: I created a throwaway `.venv-codex` even though the repo already had a working `./.venv`. The user corrected this, and it was unnecessary environment churn.

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

## Canvas Chart Scales Calibrated on a Data Subset Must Use ctx.clip() (2026-03-08)

**Pattern**: Any canvas chart section whose axis scale domain is computed from a **subset** of the data (e.g., only data within the corner's distance window) MUST wrap its draw loop in `ctx.save()` / `ctx.beginPath()` + `ctx.rect(...)` / `ctx.clip()` / `ctx.restore()`. Without it, data points outside the calibration window map to pixel values outside the chart area and the lines visibly escape the bounds.

**Why**: `CornerSpeedOverlay.tsx` builds `yScale` from speeds in `[xMin, xMax]`, but the draw loop iterates all points in each lap array. Points outside the corner window have very different speeds → `yScale()` maps them to y values above `margins.top` or below `margins.top + speedAreaHeight`. The g-strip section in the same file already used `ctx.clip()` correctly; the speed section was missing it.

**Error signature**: Chart lines bleed outside the chart area, crossing axis labels or adjacent UI elements.

**Check**: Any time a new canvas chart filters data to compute scale domains — grep for `xMin`/`xMax` filtering in scale setup but absence of `ctx.clip()` in the draw loop.

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

## Examine All Evidence Before Diagnosing Root Cause ([2026-03-05])

**Pattern**: When investigating a data discrepancy, read ALL the evidence (screenshots, labels, values) before proposing a root cause. Don't assume the first plausible explanation is correct — verify it against the evidence.

**Why**: User reported T10 showing 76 mph in the corner card vs ~92 mph in the speed trace. First diagnosis was "lap-data mismatch" (card using best-lap, trace using selected lap). But the user's screenshot clearly showed "L18" labeled in BOTH places — same lap, different speed. Actual root cause was a corner boundary artifact where `np.argmin(corner_speed)` found a local minimum in the adjacent corner's deceleration zone, not the true apex. A careful look at the evidence would have caught this immediately.

**Error signature**: Component shows a data label (e.g., "L18") matching the selected state, but the value doesn't match what the chart shows for that same data.

**Anti-pattern**: "The card shows a different value → must be using wrong data source." This is a plausible guess but skips checking whether the label confirms the same data source. Always ask: "Does the evidence SUPPORT or CONTRADICT my hypothesis?"

## CSS Sticky Containers Need Overflow + Max-Height Together ([2026-03-05])

**Pattern**: When a container uses `lg:sticky lg:top-0`, it MUST also have `lg:max-h-[calc(100vh-Xrem)]` and `lg:overflow-y-auto` if its content might exceed viewport height. Removing ANY of these three properties breaks the layout:
- No `max-h` → content clips at viewport bottom with no way to scroll
- No `overflow-y-auto` → same clipping, no scrollbar
- No `sticky` → column scrolls away with the page

**Why**: Removed `overflow-y-auto` and `max-h` from SpeedAnalysis right column thinking the user wanted "no scroll." This made the corner card bottom completely unreachable — worse than the original. The correct fix was to keep the overflow/max-h but adjust the height calculation to give more space.

**Anti-pattern**: "User says 'no scroll needed' → remove overflow constraints." Instead, maximize available space (reduce max-h deduction, let card flex-grow) while keeping the scroll mechanism as a fallback.

## Verify Subagent Commits After Each Task ([2026-03-05])

**Pattern**: After a subagent completes a task, ALWAYS run `git log --oneline -3` and `git diff --stat` to verify the subagent actually committed its work. If uncommitted changes exist, stage and commit them manually before proceeding to the next task.

**Why**: Task 5 subagent (LIDAR elevation service) completed implementation and tests but didn't finish committing. The changes were left unstaged. Had to manually verify ruff/tests passed and commit. In subagent-driven development, each task's commit is a prerequisite for the next task — an uncommitted task silently breaks the chain.

**Error signature**: `git diff --stat` shows changes after a subagent reports "done". Or the next subagent can't find symbols/imports from the previous task.

## np.savez_compressed Appends .npz to Non-.npz Paths ([2026-03-06])

**Pattern**: When using `np.savez_compressed(path, ...)`, the path MUST already end with `.npz` — otherwise numpy silently appends `.npz`, creating a file at a different path than expected. If you then `os.replace(path, target)`, you rename the empty original file, not the actual `.npz` file numpy wrote.

**Why**: Used `.npz.tmp` suffix for atomic writes. numpy created `.npz.tmp.npz` (the real file) while the original `.npz.tmp` remained empty. `os.replace` then renamed the empty file, producing a corrupt 0-byte reference. Fix: use `.tmp.npz` suffix so numpy sees it already ends with `.npz` and doesn't append.

**Error signature**: `EOFError` or empty/corrupt `.npz` files after `np.load()`. Or `os.replace` succeeds but the target file is 0 bytes.

## Verify Plan Column Names Against Actual Code ([2026-03-05])

**Pattern**: Before dispatching subagents from an implementation plan, spot-check that column names, variable names, and API field names in the plan match the actual codebase. Plans written from memory may use plausible-but-wrong names.

**Why**: Plan referenced `latitude`/`longitude` columns but actual DataFrames use `lat`/`lon`. The Task 6 subagent caught and corrected this during implementation, but it would have been faster to catch it during plan review. Column name mismatches cause silent bugs or runtime KeyErrors.

**Verification**: For each code snippet in the plan, grep the codebase for the column/field names used: `grep -rn "latitude\|lat" cataclysm/` to confirm which variant is actually used.

## Flat vs Lift Corner Characters Have Different Physical Meanings ([2026-03-05])

**Pattern**: When building algorithms that reason about corner `character` types, treat `"flat"` and `"lift"` as fundamentally different. Flat-out corners require zero braking/steering input — the car stays at full throttle. Lift corners require brief deceleration and steering input. In gap/straight calculations, flat-out corners don't interrupt the acceleration zone (skip them), but lift corners DO terminate a "straight" because the driver must slow down.

**Why**: First implementation of `_effective_gap_m()` skipped both flat AND lift corners when calculating the straight after a key corner. This inflated Barber T9's gap from ~450m to 879m (it was looking through T10-lift, T11-flat, all the way to T12). The fix: only skip `character="flat"` in gap calculation, while still excluding both flat and lift from being *candidates* for key corners (since neither requires significant technique).

**Error signature**: A corner's "straight_after" gap is suspiciously large (>500m on a 3.7km track), or a low-speed corner ranks below a fast sweeper despite having a longer actual straight.

## Cross-Cutting Concern Fixes Require Multi-Pass Sweeps ([2026-03-05])

**Pattern**: When fixing a cross-cutting concern (e.g., unit conversion, theming, accessibility), a single grep pass will miss instances. Use at least 3 search patterns and expect multiple rounds:
1. **Direct string match**: `grep "mph" *.tsx` — catches literal hardcoded values
2. **Pattern match**: `grep "Distance (m)" *.tsx` — catches axis labels, headers
3. **Negative match**: `grep -L "useUnits" *.tsx | xargs grep "speed\|distance"` — find files that reference units WITHOUT importing the hook
4. **Code review**: Dispatch the code reviewer agent to catch anything the greps missed

**Why**: Imperial/metric unit conversion fix required 4 rounds of fixes across 20+ components. Initial fix caught 11, code reviewer found 3 more, manual sweep found 2 more (SpeedGauge, WeatherPanel), then axis label sweep found 9 more. Each round exposed a new category of missed instances. A single grep for "mph" would have missed "Distance (m)" axis labels, canvas drawing functions, and weather wind speed (stored as km/h, not mph).

**Anti-pattern**: "I grepped for mph and fixed everything" — this catches <50% of unit issues. You also need to search for hardcoded unit LABELS ("(m)", "(km/h)"), hardcoded CONVERSIONS (inline `* 3.28084`), and files that display numeric values WITHOUT the useUnits hook.

## Rate Limiting Must Be Atomic — Separate Check/Record Creates TOCTOU Races ([2026-03-05])

**Pattern**: Never split rate limiting into separate `check()` and `record()` functions called at different points in a request handler. The gap between check and record (e.g., CSV processing time of 5-30s) allows concurrent requests to all pass the check before any records the slot.

**Why**: Anonymous upload rate limiting used `check_anon_rate_limit()` at request start and `record_anon_upload()` after processing. During the processing window, 4+ concurrent uploads from the same IP could all pass the check (seeing count=0) because none had recorded yet. Code reviewer caught this as a Critical security issue.

**Fix pattern**: Combine into a single atomic `check_and_record()` that reserves the slot at check time:
```python
# GOOD — atomic check-and-record
def check_and_record(ip: str) -> tuple[bool, str]:
    if over_limit(ip):
        return False, "Rate limited"
    record_slot(ip)  # Reserve immediately
    return True, ""

# BAD — separate check and record with processing in between
if not check_limit(ip):  # 4 requests all pass here
    return 429
result = await slow_processing()  # 5-30 seconds
record_upload(ip)  # Too late — slots already bypassed
```

**Error signature**: Rate limit allows more uploads than configured maximum when requests arrive concurrently. Difficult to detect in single-request testing.

## MagicMock Boolean Attributes Are Truthy — Set Explicitly in Tests ([2026-03-05])

**Pattern**: When adding boolean field guards (e.g., `if not obj.is_anonymous:`) to code that's tested with `MagicMock()`, the mock's auto-generated attribute returns a truthy `MagicMock` object — not `False`. You must explicitly set `mock.is_anonymous = False` in the test.

**Why**: Adding `if not sd.is_anonymous:` to the startup auto-coaching loop broke `test_lifespan_auto_coaching_triggered_for_each_session` because `MagicMock().is_anonymous` is truthy, so the guard skipped all mock sessions. The fix was a single line: `fake_session.is_anonymous = False`.

**Error signature**: Test that previously passed starts failing after adding a boolean guard. The mock object silently skips the guarded code path because `MagicMock().any_attribute` evaluates to `True`.

**Anti-pattern**: Assuming `MagicMock()` attributes behave like `None` or `False`. They don't — they're `MagicMock` objects which are truthy. Always set boolean attributes explicitly on mocks.

## Verify Multi-Step Flows Are Fully Wired End-to-End ([2026-03-05])

**Pattern**: When implementing a multi-step user flow (e.g., upload → auth → claim), verify that EVERY step is actually connected. Export a function in `api.ts` ≠ it's called somewhere. Store a value in localStorage ≠ something reads it. Each link in the chain must be verified with grep.

**Why**: The session claiming flow had `claimSession()` exported in `api.ts` but never imported or called from any React component. The upload saved to localStorage but nothing read it on auth transition. Code reviewer caught this as a Critical issue — the entire claiming flow was dead code.

**Verification checklist for multi-step flows**:
1. For each API function: `grep -rn "claimSession" frontend/src/` — is it called?
2. For each localStorage key: `grep -rn "cataclysm_anon_session_id" frontend/src/` — is it both set AND read?
3. For each backend endpoint: Is there a frontend caller? Is there a test?
4. Walk the flow manually: Step 1 produces X → Step 2 consumes X → Step 3 produces Y → ...

**Anti-pattern**: Implementing each step in isolation ("backend claim endpoint ✓, api.ts function ✓, localStorage save ✓") without verifying the connections between steps. Each step works alone but the flow is broken because nothing triggers the next step.

## Always Run Code Reviewer After Implementation
- **When**: After finishing ANY implementation task — features, bug fixes, refactors
- **Rule**: Dispatch the code reviewer agent (`superpowers:code-reviewer` or `code-review:code-review`) to review all changed files. This is in ADDITION to automated checks (ruff, mypy, tests), not a replacement.
- **Why**: User explicitly requested this. Code reviewers catch logic errors, architectural issues, and subtle bugs that linters and tests miss. Added to CLAUDE.md Quality Gates (item 6) and Verification Before Done section.

## Local Data Files May Be Stale vs Deployed State ([2026-03-06])

**Pattern**: Never trust local data files (JSON profiles, cached configs) as the authoritative source for what a user currently has on the deployed server. When the user contradicts what a local file says, the user is correct — the local file is likely a stale snapshot.

**Why**: Read local `data/equipment/profiles/eq_7451a89092cb.json` which showed Falken RT660 tires. Told the user they had RT660s. User corrected: "I have RS4 tires, not rt660 where did u get that from." The local file was outdated relative to the deployed database. Presenting stale data as fact erodes trust.

**Anti-pattern**: "The JSON file says X, so the user has X." Local files are snapshots, not live state. If the user says differently, believe the user. When local data contradicts user statements, flag the discrepancy rather than asserting the file is correct.

## Backend Endpoints Without Frontend Consumers Are Invisible Features ([2026-03-06])

**Pattern**: When reviewing or QAing a feature, verify that every backend endpoint has a corresponding frontend consumer. A fully working backend API with no frontend UI is an invisible feature — the user can never access it.

**Why**: The vehicle selection backend was complete (`GET /vehicles/search`, `GET /vehicles/{make}/{model}`, profile create/update accepting `vehicle` field) but `EquipmentSetupModal.tsx` never rendered a vehicle section. The backend was built, tested, and deployed — but completely invisible to users. User discovered this and was justifiably frustrated: "How the fuck did you QA this if its not visible."

**Verification**: After implementing any backend feature, grep the frontend for consumers: `grep -rn "/api/equipment/vehicles" frontend/src/`. If zero results, the feature has no UI. For each backend endpoint, there should be: (1) an `api.ts` function, (2) a hook in `useXxx.ts`, (3) a component that calls the hook.

**Anti-pattern**: "Backend is done, frontend will come later" without tracking the gap. If the gap isn't tracked, it becomes permanent. Either implement both together or create a TODO that blocks the feature from being marked complete.

## Sentinel Values That Collide With Domain Values Need Metadata Disambiguation ([2026-03-06])

**Pattern**: When a sentinel/default value (e.g., mu=1.0 for "uncalibrated") can also be a legitimate domain value (e.g., Hankook RS4 endurance tire mu=1.0), never use value-based checks alone. Use accompanying metadata (e.g., `mu_source`) to distinguish "I don't know" from "this is the real value."

**Why**: Grip calibration fallback needed to detect uncalibrated equipment. First attempt: `mu > 1.0` — broke street tires (mu=0.85 is valid). Second attempt: `mu != 1.0` — broke RS4/endurance tires (mu=1.0 is a real curated value). Correct fix: `mu_source == FORMULA_ESTIMATE and mu == 1.0` — only the specific combination of "computed from no data" AND "got the default" is the sentinel case.

**Error signature**: Physics model produces invalid results for some tire categories but not others, or grip calibration unexpectedly runs/skips for specific tire selections.

**Anti-pattern**: `if value == DEFAULT:` when the default can also be a legitimate value. Instead, check `if source == UNCALIBRATED and value == DEFAULT:` using metadata that tracks HOW the value was obtained.

## Query Key + queryFn Must Stay In Sync When Using Cache-Busters ([2026-03-06, corrected 2026-03-07])

**Pattern**: When a backend response depends on state the user can change (like equipment profile), you need BOTH:
1. The dependent value in the React Query key (for distinct cache entries)
2. The dependent value in the queryFn's URL (as a cache-buster, to avoid browser HTTP cache collisions)

If you put the value in the key but NOT the URL, the browser HTTP cache (`Cache-Control: max-age=60`) serves the old response to the new key. If you put it in the URL but NOT the key, React Query overwrites the old entry.

```typescript
// CORRECT — key and URL both include profileId
queryKey: ["optimal-comparison", sessionId, profileId],
queryFn: () => getOptimalComparison(sessionId!, profileId), // appends ?_eq=profileId

// WRONG — key includes profileId but URL doesn't → browser HTTP cache collision
queryKey: ["optimal-comparison", sessionId, profileId],
queryFn: () => getOptimalComparison(sessionId!), // same URL for all profiles!

// WRONG — URL includes profileId but key doesn't → overwrites previous profile's cache
queryKey: ["optimal-comparison", sessionId],
queryFn: () => getOptimalComparison(sessionId!, profileId),
```

**Why**: This bug took 4+ commits across 2 sessions. First attempt put profileId in key only → browser served stale HTTP response. Second attempt removed profileId from key → invalidation-only approach was fragile. Correct fix: put in both key AND URL. Use `keepPreviousData` for smooth transitions and `isPlaceholderData` for loading animation.

**Error signature**: Equipment switch updates the equipment name but the optimal target value stays the same, or returns different values for the same equipment on A→B→A cycles.

## Verify User State Before Making Assumptions ([2026-03-06])

**Pattern**: Before assuming a user lacks something (equipment profile, vehicle setup, etc.), check the data directory or API. Don't assume absence without evidence.

**Why**: Assumed the user had no equipment profile and started explaining why optimal times were off without one. User corrected: "i actually have an equipment profile, you can check it yourself." A simple `ls data/equipment/profiles/` or `grep` would have revealed it instantly. The assumption wasted time and made the analysis less useful.

**Anti-pattern**: "Since you don't have an equipment profile..." without first checking. Always verify: `ls data/equipment/profiles/` or grep for the user's profile before reasoning about their setup.

## Update ALL Doc References When a Value Changes ([2026-03-06])

**Pattern**: When a URL, branch name, or other value referenced in multiple files changes, immediately update ALL occurrences across CLAUDE.md, docs/*.md, and memory/*.md in a single batch. Don't wait to be reminded.

**Why**: Changed staging frontend domain from `frontend-staging-b78c` to `cataclysm-staging` but only updated Railway env vars. User had to say "update your docs" before I updated the 3 doc files. Each doc file that references a URL/config value is a maintenance liability — update them all atomically.

**Verification**: After changing any referenced value, run `grep -rn "old_value" CLAUDE.md docs/ tasks/` and the memory directory to find all occurrences.

## TOCTOU Fixes Must Capture ALL Mutable State Reads Atomically ([2026-03-07])

**Pattern**: When fixing a TOCTOU (Time-of-Check-Time-of-Use) race by capturing state before a boundary (thread pool, async task, network call), capture ALL reads from the mutable source — not just the cache key. If you capture `profile_id` but still call `resolve_vehicle_params(session_id)` inside the boundary, you've only fixed half the race.

**Why**: First TOCTOU fix captured `profile_id` before `asyncio.to_thread()` for the cache key, but `_compute()` still called `resolve_vehicle_params(session_id)` and `_has_meaningful_grip(session_id)` inside the thread — both re-read the equipment store. If equipment changed between capture and thread execution, the computation used profile B's params but the result was cached under profile A's key.

**Checklist for TOCTOU fixes**:
1. Identify the mutable state source (e.g., equipment store)
2. List ALL reads from that source in the protected region
3. Move ALL reads before the boundary
4. Pass captured values into the protected region via closure/args
5. Use `nonlocal` in Python closures if captured values may be reassigned

**Error signature**: Values look correct on first computation but A→B→A switching produces inconsistent results. The cache key is correct but the cached data belongs to a different state.

## Multi-Layer Cache Bugs Need Layer-by-Layer Diagnosis ([2026-03-07])

**Pattern**: When a caching bug manifests (stale data, inconsistent values on toggle), enumerate ALL caching layers between the user and the data source, then test each independently. Don't assume the bug is in the most obvious layer.

**Methodology**:
1. **Enumerate layers**: For this codebase: Browser HTTP cache (`Cache-Control`), React Query cache (in-memory), Backend physics cache (in-memory dict)
2. **Test each layer**: Browser → Network tab shows 304/cached vs 200; React Query → devtools show query key + data; Backend → server logs show cache hit/miss
3. **Fix bottom-up**: Fix the deepest layer first (backend), then middle (React Query), then shallowest (browser HTTP)
4. **Verify after each fix**: Deploy, test A→B→A cycle, confirm values change

**Why**: Equipment switching bug appeared as "values don't change" — initially attributed to React Query invalidation. Real root cause was browser HTTP cache serving stale responses for the same URL. Took 2 sessions because the browser cache layer was invisible (React Query appeared to work correctly since it fired fetches — but the fetches got browser-cached responses).

**Caching layers in Cataclysm**:
| Layer | Cache Key | TTL | Fix |
|-------|-----------|-----|-----|
| Browser HTTP | URL | `max-age=60` | `_eq=profileId` param |
| React Query | `[endpoint, sessionId, profileId]` | `Infinity` | profileId in key + `keepPreviousData` |
| Backend physics | `(session_id:endpoint, profile_id)` | 30 min | Atomic state capture before thread |

**Error signature**: Values that seem to update "sometimes" — because whether the browser cache is hit depends on timing (within 60s = stale, after 60s = fresh).

## Gate Dependent Queries on Parent Query Settlement ([2026-03-07])

**Pattern**: When query B's cache key depends on query A's result (e.g., optimal-comparison key includes profileId from session-equipment), gate B with `enabled: A.isFetched`. Without this, B fires with a default/null key while A is loading, triggering a wasted computation that gets discarded when A resolves.

```typescript
// GOOD — waits for equipment to settle
const { data: equipment, isFetched: equipmentSettled } = useSessionEquipment(sessionId);
const profileId = equipment?.profile_id ?? null;
return useQuery({
  queryKey: ["optimal-comparison", sessionId, profileId],
  enabled: !!sessionId && equipmentSettled,  // gates on parent
});

// BAD — fires immediately with null profileId
const { data: equipment } = useSessionEquipment(sessionId);
const profileId = equipment?.profile_id ?? null;
return useQuery({
  queryKey: ["optimal-comparison", sessionId, profileId],  // null while loading
  enabled: !!sessionId,  // fires with wrong key
});
```

**Why**: Without gating, optimal-comparison fires with `profileId=null` (equipment still loading), triggers an 8-second backend computation with default vehicle params, then throws it away when equipment resolves and profileId changes. The `~200ms` wait for equipment to settle saves `~8s` of wasted backend compute.

**Error signature**: Backend logs show TWO optimal-comparison computations for the same session on page load — one with `profile_id=None` and one with the actual profile ID.

## Cache/Store Cleanup Must Cover ALL Lifecycle Endpoints ([2026-03-06])

**Pattern**: When an entity has dependent subsystems (caches, stores, side data), ALL lifecycle operations (create, update, delete, bulk-delete) must clean up ALL dependent subsystems. Enumerate both axes: (1) all mutation endpoints, and (2) all subsystems that hold entity-scoped data.

**Why**: Two instances found:
1. `delete_profile()` missing `invalidate_profile_cache()` — stale physics cache for 30 min.
2. `delete_session()` and `delete_all_sessions()` missing `equipment_store.delete_session_equipment()` AND `invalidate_physics_cache()` — orphaned equipment data on disk + stale cache entries for deleted sessions.

**Verification**: After adding any new subsystem that stores per-entity data, grep for ALL delete/mutation endpoints of that entity and add cleanup. Also: when reviewing a delete endpoint, check if ALL subsystems are cleaned up.

**Anti-pattern**: "I added cleanup to the PUT, that covers it." No — delete (single + bulk), create-that-replaces, and any bulk operations also need cleanup for ALL dependent subsystems.

## Nullish Coalescing (`??`) Does Not Catch Zero — Use `||` for Numeric Fallbacks ([2026-03-07])

**Pattern**: When a numeric value of `0` should trigger a fallback (e.g., physics returns 0 meaning "no useful estimate"), use `||` instead of `??`. `??` only catches `null`/`undefined`, so `0 ?? fallback` returns `0`.

```typescript
// WRONG — 0 passes through, formatBadge(0) shows "Estimate unavailable"
const timeCost = liveValue ?? fallbackValue;

// CORRECT — 0 is falsy, triggers fallback to coaching report value
const timeCost = liveValue || undefined;  // then: timeCost ?? fallbackValue
```

**Why**: Removing the `is_valid` gate on `corner_opportunities` exposed this: physics caps negative `time_cost_s` at 0 when the model is slower than the driver. `0 ?? p.time_cost_s` = `0`, and `formatPriorityBadge(0)` = "Estimate unavailable". Two corners (T5, T9) regressed from showing "Up to 0.2s" to "Estimate unavailable" after the fix.

**Error signature**: A badge/label shows a "no data" state despite having a valid fallback value. The intermediate value is `0`, not `null`.

## React Query `isLoading` Is False for SSR and Paused Queries — Use `isPending` ([2026-03-07])

**Pattern**: In React Query v5, `isLoading = isPending && isFetching`. Two scenarios make `isFetching=false` while there is still no data: (1) SSR — no network request runs server-side, (2) paused queries — mobile OS suspends network activity (background tab, WiFi→cellular switch). In both cases `isLoading=false` even though `data` is `undefined`. Use `isPending` everywhere for loading gates.

```typescript
// WRONG — isLoading=false during SSR and mobile pause, so chart renders blank
const { data, isLoading } = useQuery({ queryKey: ['x'], queryFn: fetchX });
if (isLoading) return <Spinner />;   // misses paused state → blank canvas

// CORRECT — isPending=true whenever there is no data, regardless of cause
const { data, isPending: isLoading } = useQuery({ queryKey: ['x'], queryFn: fetchX });
if (isLoading) return <Spinner />;   // catches SSR, pause, and normal loading
```

**Why**: Deep Dive charts (SpeedTrace, DeltaT, LateralOffsetChart) used `isLoading`. On mobile, iOS/Android suspend background network requests, putting queries into paused state (`isPending=true, isFetching=false → isLoading=false`). Charts passed the spinner gate with `data=undefined`, rendered blank canvases, and in one case showed a false "GPS quality too low" error.

**Error signature**: Charts appear empty (no spinner, no data) after selecting laps. Hard refresh fixes it. Happens more on mobile and iPad than desktop. Or: "no data" flash on SSR with data appearing after ~500ms.

## Conditional Render Guard Order: Prerequisites Before Data Validity (2026-03-08)

**Pattern**: In chart components, check prerequisite conditions (empty selection, missing session) BEFORE checking data validity (`!data?.available`, empty array). When data is `undefined` (loading or paused), validity checks produce false error states instead of spinners.

Correct order: (1) prerequisite check → (2) `isPending` spinner → (3) data validity.

**Why**: `LateralOffsetChart` checked `!lineData?.available` before `selectedLaps.length === 0`. With a paused query `lineData=undefined`, `!undefined?.available` is `true` → showed "GPS quality too low" error even when data would load fine on refresh.

**Error signature**: Chart shows a data-validity error ("GPS quality too low", "No laps") when the real issue is that no laps are selected or data is still loading. Refresh fixes it.

## Browser-First Debugging for Frontend Issues ([2026-03-07])

**Pattern**: For ANY frontend bug involving data display, state, or timing: open the browser FIRST, check network requests and console, reproduce the issue visually. Only read code AFTER you've observed the actual behavior. Never hypothesize from code alone.

**Methodology**:
1. Navigate to the page in the browser
2. Check Network tab — did the API calls succeed? What data was returned?
3. Check Console — any errors or warnings?
4. Reproduce the issue — click, switch, interact
5. THEN read the code with specific hypotheses informed by what you observed

**Why**: User explicitly corrected this approach: "always use the browser for such debugging instead of hypothesizing based on just looking at the code." Reading 5+ files and forming theories without browser evidence wastes time and often leads to wrong hypotheses. The browser tells you what's ACTUALLY happening vs what you THINK should happen.

**Anti-pattern**: Reading PriorityCardsSection.tsx → SessionReport.tsx → useAnalysis.ts → api.ts → Providers.tsx → forming a theory → THEN opening the browser. Instead: browser → observe → targeted code reading → fix.

## Avoid Order-Dependent Assertions in Tests ([2026-03-07])

**Pattern**: When asserting on collections (lists of corners, priority items, etc.), use set-based or `any()`-based assertions instead of asserting on specific indices. Serialization/deserialization, dict ordering, and sorting can change element order.

**Why**: `test_generate_report` broke with `assert data["priority_corners"][0]["corner"] == 3` because the coaching store returned corners in a different order than the mock's input order. Fixed by asserting `{pc["corner"] for pc in data["priority_corners"]} == {3, 5}`.

## Coverage.py + Python 3.12 Async Router Artifact ([2026-03-07])

**Pattern**: When running `--cov` on FastAPI routers with Python 3.12, expect artificially low coverage on async endpoint bodies. coverage.py 7.x uses `sys.monitoring` (PEP 669) which doesn't correctly attribute execution inside async coroutines — the `def` line is covered but body lines aren't, even when test assertions prove they ran.

**Why**: Backend overall shows 96% but services layer is 100%. The ~4% gap is entirely async router bodies. Don't chase these lines with more tests — they're already tested. Test synchronous helpers directly and call async functions with patched dependencies instead of routing through ASGI client when possible.

## New FastAPI Dependencies Must Be Added to Test Conftest Overrides ([2026-03-07])

**Pattern**: When creating a new FastAPI `Depends()` function (e.g., `get_user_or_anon`), you MUST add it to `conftest.py` `_mock_auth` fixture's `app.dependency_overrides` dict AND the cleanup `pop()` calls. Tests will fail with 401/403 or ownership mismatches if the new dependency isn't overridden.

**Why**: Added `get_user_or_anon` to 20+ endpoints but forgot the conftest override. Test `test_get_corners` failed because the sentinel anonymous user (`user_id="anon"`) couldn't access sessions owned by `test-user-123`. The fix was one line in conftest: `app.dependency_overrides[get_user_or_anon] = lambda: _TEST_USER`.

**Error signature**: Tests that previously passed start returning 401/403 or "session not found" after switching endpoints to a new auth dependency.

## Use build_synthetic_csv() for Staging QA When Real CSVs Fail ([2026-03-07])

**Pattern**: When Playwright QA on staging is blocked because a real CSV lacks lap detection (empty `lap_number` columns, no track reference data on staging), generate a synthetic CSV using `build_synthetic_csv()` from `backend/tests/conftest.py` and `curl` upload it to the staging backend.

**Why**: The sample RaceChrono CSV had empty `lap_number` columns and needed track reference data for lap detection. Staging backend didn't have this data, so upload returned `session_ids: []`. Using `build_synthetic_csv(n_laps=5, points_per_lap=300)` generates a CSV with pre-assigned lap numbers that always works.

**Command**: `python -c "from backend.tests.conftest import build_synthetic_csv; open('/tmp/test.csv','wb').write(build_synthetic_csv(n_laps=5))"` then `curl -X POST .../upload -F "files=@/tmp/test.csv"`


## Bulk Refactor Leaves Stale Symbol References — Always Run `tsc --noEmit` (2026-03-08)

**Pattern**: After any bulk rename/replace across many files (e.g., `MARGINS` → `dimensions.margins`), run `npx tsc --noEmit` from `frontend/` before committing. Local incremental TypeScript cache reuses compiled output for unchanged files, hiding missed references. Railway's clean build catches them — causing failed deploys.

**Why**: Phase 2 chart margin refactor renamed `MARGINS` usages to `dimensions.margins` across 16 files, but 4 occurrences across 3 files were missed (`BrakeConsistency.tsx` ×2, `CornerSpeedOverlay.tsx`, `LateralOffsetChart.tsx`). Local build showed no errors (cache). Railway failed with `Cannot find name 'MARGINS'` on 3 consecutive deploys.

**Error signature**: Railway build: `Type error: Cannot find name 'X'` in a file you thought you already updated. Local `next dev` / `vitest` shows no errors because incremental cache masked it.

**Rule**: `npx tsc --noEmit` is **mandatory** before every frontend push — not optional. Tests alone are insufficient because they only typecheck files they import.

## Railway `get-logs` Returns Latest Success, Not Latest Deployment (2026-03-08)

**Pattern**: When a Railway deploy fails, `get-logs` without a `deploymentId` returns logs from the most recent **successful** deployment — which looks fine. To debug a failure:
1. Call `list-deployments` first to get the failed deployment ID (status: FAILED)
2. Call `get-logs` with `deploymentId: <that ID>`

**Why**: After three failed deploys, checking `get-logs` without an ID returned a clean successful build log, making it look like everything was fine. User had to explicitly tell me to check the logs — I was looking at the wrong deployment.

**Error signature**: `get-logs` output shows `✓ Compiled successfully` but Railway dashboard shows FAILED status. You're reading old logs.

## Radix ScrollArea `display:table` Causes Mobile Horizontal Overflow (2026-03-08)

**Pattern**: When a Radix `ScrollArea` is used as a full-page scroll container and content overflows its expected width on mobile, the culprit is likely the Radix Viewport inner div: Radix sets `style="display:table; min-width:100%"` via inline JS. On mobile this creates a circular width dependency — table width expands to content's intrinsic width, content expands to table width — breaking any `max-width` CSS constraint.

Fix: Add a CSS class (`.no-hscroll`) to the ScrollArea root and target the inner div with `!important`:
```css
.no-hscroll > [data-slot="scroll-area-viewport"] > div {
  display: block !important;
  min-width: 0 !important;
}
```
Apply only to vertical-scroll areas (NOT horizontal-scroll areas like LapPillBar).

**Why**: `max-width: 100vw` doesn't work on `display:table` — table layout uses a two-pass column algorithm that ignores `max-width`. Only changing `display` to `block` restores normal flow where width is bounded by the parent viewport. `!important` is required because Radix sets the style as an inline attribute (higher specificity than class-based CSS).

**Error signature**: Content on mobile is laid out wider than the viewport (e.g., 439px on a 360px viewport). `overflow-x-hidden` clips the content visually but the layout is still wrong. JS confirms: `innerDisplay: "table"`, `innerW: 439` when `window.innerWidth: 360`.

## React Ref Object in useEffect Deps Silently Breaks Conditionally-Rendered Canvas Listeners (2026-03-08)

**Pattern**: NEVER put a React ref object (`useRef` result) in a `useEffect` dependency array to detect when the referenced DOM element mounts. The ref object is stable (same identity across all renders) — React never sees it as "changed", so the effect only runs once. If the element is conditionally rendered (behind a loading state), the first run finds `.current === null`, returns early, and listeners are NEVER attached.

**Fix**: Use **React event props** (`onClick`, `onMouseMove`, `onMouseLeave`) directly on the element instead of imperative `addEventListener`. React event props are always in sync with the element lifecycle — no timing window.

```tsx
// ❌ BROKEN — effect runs once during isLoading, finds canvas=null, never re-runs
useEffect(() => {
  const canvas = dataCanvasRef.current;
  if (!canvas) return;          // ← returns early, effect never re-runs
  canvas.addEventListener('click', handleClick);
}, [onCornerClick, dataCanvasRef]);  // dataCanvasRef object never changes

// ✅ CORRECT — React attaches handlers whenever the element exists
<canvas
  ref={dataCanvasRef}
  onClick={(e) => { const hit = getHitCorner(e); if (hit) onAction(hit.id); }}
  onMouseMove={(e) => { e.currentTarget.style.cursor = getHitCorner(e) ? 'pointer' : 'default'; }}
  onMouseLeave={(e) => { e.currentTarget.style.cursor = 'default'; }}
/>
```

**Why**: This silently ships broken interactivity. The CTA hint (e.g., "Click any bar to explore →") is visible in JSX, but the canvas never responds to clicks or cursor changes because the native listeners were never registered. The bug is invisible in code review because the effect body looks correct.

**Error signature**: UI shows an interactive hint ("Click to do X") but clicks do nothing. Hover cursor never changes. Feature worked in initial testing but fails consistently — because the initial test was done before data loaded (when the skeleton was shown) or within a narrow timing window.

## Use `docScrollWidth` — Not BoundingClientRect — for Overflow Detection (2026-03-08)

**Pattern**: When verifying that a page has no horizontal overflow, use `document.documentElement.scrollWidth > window.innerWidth` as the authoritative test. Do NOT sweep `getBoundingClientRect().right > window.innerWidth` on all elements — this produces false positives from off-screen `position:fixed` elements (like closed drawers/modals rendered outside the viewport).

```js
// CORRECT
document.documentElement.scrollWidth > window.innerWidth  // true = overflow

// MISLEADING — returns false positives from off-screen fixed elements
el.getBoundingClientRect().right > window.innerWidth
```

**Why**: `scrollWidth` measures whether the document can be scrolled horizontally. Fixed-position elements outside the viewport do NOT contribute to `scrollWidth`, but their `getBoundingClientRect()` can show `right: 680` on a 360px viewport, making it look like overflow exists when none does.

## NEVER Enable DEV_AUTH_BYPASS on Staging (2026-03-08)

**Pattern**: `DEV_AUTH_BYPASS=true` must NEVER be set in Railway staging env vars. It overrides ALL authentication globally — every HTTP request (including the real user's browser) authenticates as `dev-user`. This silently hides all real user sessions and data. Remove it with `railway variables delete DEV_AUTH_BYPASS --service backend` then `railway redeploy --service backend --yes`.

**Why**: User flagged this as an explicit mistake. A QA agent set `DEV_AUTH_BYPASS=true` to simplify anonymous testing, which caused the real user's sessions to disappear from the UI. The correct approach for QA agents that need unauthenticated access: use the `get_user_or_anon` backend dependency (already in place) — it allows anonymous reads without bypassing all auth.

**Error signature**: Real user sees 0 sessions in the app after a backend restart. Backend logs show: `DEV_AUTH_BYPASS is ENABLED` and `list_sessions: user_id=dev-user → 0 session(s)` for every request.

## QA Agents Run Unauthenticated — Expect False Failures on Session-Owned Endpoints (2026-03-08)

**Pattern**: When a Playwright QA agent tests session-specific endpoints (e.g., `/api/sessions/{id}/laps/{n}/data`, `/optimal-comparison`), it will get 404/403/500 because it has no auth cookie and the session is owned by a specific user. These are **not real bugs** — the app is working correctly. Do not file these as failures unless the endpoint is supposed to be publicly accessible.

**Why**: Confused 2 legitimate backend failures with QA artifacts. The distinction: if the real authenticated user can access the data (confirmed in browser), the QA agent failure is an artifact. Document this expectation when writing QA agent prompts.

**Error signature**: QA agent reports `500`/`404` on `/laps/{id}/data` or similar session-scoped endpoints, while the real user sees data fine in their browser.
