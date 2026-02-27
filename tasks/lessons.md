# Lessons Learned

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

## Use Real Device Emulators for Mobile Testing
- **When**: Testing responsive/mobile layouts with Playwright MCP or any browser automation
- **Rule**: Use real device emulation profiles (e.g. Playwright's `devices['Pixel 7']`, `devices['iPhone 14']`) that set viewport, deviceScaleFactor, userAgent, and hasTouch — not just `page.setViewportSize()`. A resized desktop viewport misses touch events, device pixel ratio differences, and mobile browser chrome behavior.
- **Minimum coverage**: Test on at least one Android profile and one iOS profile.
- **Check for**: text clipping/overflow, horizontal scroll, touch targets < 44x44px, bottom nav overlapping content, chart/SVG scaling, fixed positioning issues.
- **Why**: User explicitly requested this. A plain viewport resize misses real mobile rendering differences.

## False Brake Attribution from Overlapping Search Windows
- **When**: Working on brake point detection or corner KPI extraction
- **Rule**: When searching for a brake point before a corner, the search window must not extend into the previous corner's zone. Use `prev_exit_idx` parameter in `_find_brake_point` to clamp the search start. Without this, closely-spaced corners (e.g. T9→T10 at Barber, ~350m apart) will attribute the previous corner's trail braking to the next corner.
- **Pattern**: `_find_brake_point(..., prev_exit_idx=prev_exit)` — callers must track the previous corner's exit index and pass it through.
- **Companion fix**: Flat-out corners need explicit `character="flat"` annotations in `track_db.py` OfficialCorner definitions, which suppress brake recommendations in `CornerRecommendation` and signal the LLM not to coach braking. Even with correct brake detection, the LLM will fixate on tiny deceleration events without this hint.
