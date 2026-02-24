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

## Commit and Push After Every Logical Change
- **When**: After completing any phase, feature, or fix — not at the end of a long session
- **Rule**: The app is deployed on Streamlit Cloud from the remote branch. Every completed change must be committed and pushed immediately. Do NOT batch up multiple phases into one big commit at the end.
- **Why**: User called this out. CLAUDE.md explicitly says "Always commit and push after making changes." Batching delays deployment and risks losing work. When using subagents that make their own commits, verify they pushed too, and commit any remaining unstaged work yourself immediately.
- **Cadence**: After each phase/feature completes → commit + push. After a small follow-up change (like adding trendlines) → commit + push right away.

## Create .env File for Docker Compose Secrets
- **When**: Setting up Docker Compose with API keys or secrets
- **Rule**: Create a `.env` file (gitignored) in the project root with secrets like ANTHROPIC_API_KEY. docker-compose.yml uses `${ANTHROPIC_API_KEY:-}` syntax to read from environment/`.env`.
