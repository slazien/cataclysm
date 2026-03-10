# Track Data Pipeline v2 — E2E Testing Plan (Clean Railway Environment)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a clean Railway environment with no pre-seeded tracks, upload a Barber session CSV, and verify the full auto-discovery → enrichment → corner detection → coaching pipeline works end-to-end.

**Architecture:** New Railway environment (`testing`) linked to a `testing` branch. Backend + frontend + PostgreSQL. The testing branch disables hardcoded track seeding so auto-discovery is forced. After E2E validation, the environment is torn down.

**Tech Stack:** Railway CLI, PostgreSQL, FastAPI, Next.js, OSM Overpass API

---

## Context for the Implementing Agent

**Read these files first** (in this order) to understand the project:

1. `CLAUDE.md` — Project conventions, quality gates, deployment rules
2. `docs/deployment.md` — Railway deployment architecture, env vars, service setup
3. `docs/architecture.md` — System architecture overview
4. `backend/api/config.py` — All backend env vars (Settings class)
5. `backend/api/main.py` — App lifespan, startup seeding, middleware
6. `backend/api/services/pipeline.py:462-526` — Auto-discovery flow (`_try_auto_discover_track`)
7. `backend/api/services/track_enrichment.py:1-11` — Enrichment steps overview
8. `backend/api/services/track_seed.py:79-100` — Hardcoded track seeding
9. `backend/api/routers/track_admin.py:480-526` — OSM import endpoint
10. `Dockerfile.backend` — Backend Docker build + startup command
11. `Dockerfile.frontend` — Frontend Docker build
12. `memory/MEMORY.md` — Operational gotchas (Railway, deployment, auth)

**Key operational rules:**
- NEVER push to `main`. Only push to `testing` branch.
- NEVER modify Railway env vars without explicit user permission.
- Always check Railway deploy logs after every push (`list-deployments` → `get-logs`).
- `PORT=8000` MUST be set explicitly on backend (Railway assigns dynamic ports otherwise).
- `NEXTAUTH_SECRET` must match EXACTLY between frontend and backend.
- `DEV_AUTH_BYPASS` — can use `true` for this testing env (no real users). Set on BOTH backend and frontend.
- `DATABASE_URL` is auto-provided by Railway PostgreSQL addon — don't set manually.

**Railway CLI commands you'll need:**
```bash
# List projects
railway list

# Link to project
railway link

# Create environment
railway environment create testing

# Set env vars
railway variables set KEY=VALUE --service <service> --environment testing

# Deploy
railway up --service <service> --environment testing

# Check deploys
railway service list
list-deployments --service <service> --environment testing

# Get logs
get-logs --service <service> --environment testing --logType deploy --lines 50

# Generate public domain
railway domain --service <service> --environment testing
```

---

## Phase 1: Create the Testing Branch

### Task 1: Create `testing` branch from `staging`

**Files:**
- None (git operations only)

**Step 1: Create and push the branch**

```bash
git checkout staging
git pull origin staging
git checkout -b testing
git push origin testing
```

**Step 2: Verify branch exists on remote**

```bash
git branch -r | grep testing
```

Expected: `origin/testing`

---

## Phase 2: Disable Hardcoded Track Seeding

The auto-discovery pipeline only triggers when `detect_track_or_lookup()` returns `None` (no known track). On a normal deploy, `seed_tracks_from_hardcoded()` pre-loads Barber/AMP/Roebling into the DB at startup, so uploads always match and never trigger auto-discovery.

We need to skip that seeding on the testing branch so the DB starts empty.

### Task 2: Add env-var gate to skip track seeding

**Files:**
- Modify: `backend/api/main.py` (the lifespan function where `seed_tracks_from_hardcoded` is called)

**Step 1: Find the seeding call in the lifespan function**

```bash
grep -n "seed_tracks_from_hardcoded" backend/api/main.py
```

Note the line number.

**Step 2: Add an env-var gate**

Wrap the seeding call with:

```python
import os

# ... inside the lifespan function, around the seed call:
if os.environ.get("SKIP_TRACK_SEEDING") != "true":
    seeded = await seed_tracks_from_hardcoded(db)
    logger.info("Seeded %d hardcoded tracks", seeded)
else:
    logger.info("SKIP_TRACK_SEEDING=true — skipping hardcoded track seed")
```

This is a minimal, non-destructive change — staging/prod behavior is unchanged (env var not set = seeds normally).

**Step 3: Run quality gates**

```bash
source .venv/bin/activate
ruff format backend/api/main.py && ruff check backend/api/main.py
dmypy run -- backend/api/main.py
```

**Step 4: Commit and push**

```bash
git add backend/api/main.py
git commit -m "feat: SKIP_TRACK_SEEDING env var to disable hardcoded track seed

For E2E testing of auto-discovery pipeline in clean environments.

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin testing
```

---

## Phase 3: Set Up Railway Testing Environment

### Task 3: Create the Railway environment and PostgreSQL

**Step 1: Create the testing environment**

Use Railway CLI or dashboard:

```bash
railway environment create testing
```

If CLI doesn't support this, use the Railway dashboard:
1. Go to project → Settings → Environments → New Environment
2. Name: `testing`
3. Link branch: `testing`

**Step 2: Add PostgreSQL addon**

In Railway dashboard:
1. Select the `testing` environment
2. Click "+ New" → "Database" → "PostgreSQL"
3. Wait for provisioning (~30s)

The `DATABASE_URL` env var is auto-set on all services in the environment.

**Step 3: Verify the environment exists**

```bash
railway environment list
```

Expected: `testing` appears in the list.

---

### Task 4: Configure backend environment variables

**Step 1: Set required env vars on the backend service**

```bash
# Required
railway variables set PORT=8000 --service backend --environment testing
railway variables set SKIP_TRACK_SEEDING=true --service backend --environment testing
railway variables set DEV_AUTH_BYPASS=true --service backend --environment testing
railway variables set LOG_LEVEL=DEBUG --service backend --environment testing

# Auth (use same secret for both services)
railway variables set NEXTAUTH_SECRET=testing-secret-e2e-2026 --service backend --environment testing

# CORS — will need to be updated after frontend domain is generated
railway variables set CORS_ORIGINS_RAW='["http://localhost:3000"]' --service backend --environment testing

# Anthropic API key (needed for coaching generation test)
# Ask the user for the key or copy from staging
railway variables set ANTHROPIC_API_KEY=<key> --service backend --environment testing
```

**IMPORTANT**: The `ANTHROPIC_API_KEY` is sensitive. Ask the user to provide it or copy it from the staging environment via the Railway dashboard.

**Step 2: Set the Dockerfile path for backend**

In Railway dashboard → testing env → backend service → Settings:
- Builder: Dockerfile
- Dockerfile path: `Dockerfile.backend`

Or via Railway CLI if supported.

**Step 3: Generate a public domain for backend**

```bash
railway domain --service backend --environment testing
```

Note the generated URL (e.g., `backend-testing-xxxx.up.railway.app`).

---

### Task 5: Configure frontend environment variables

**Step 1: Set required env vars**

```bash
# Auth
railway variables set AUTH_SECRET=testing-secret-e2e-2026 --service frontend --environment testing
railway variables set AUTH_TRUST_HOST=true --service frontend --environment testing
railway variables set DEV_AUTH_BYPASS=true --service frontend --environment testing

# Backend URL — private network (same Railway project)
# This is a BUILD ARG, may need to be set differently
railway variables set BACKEND_URL=http://backend.railway.internal:8000 --service frontend --environment testing
```

**Step 2: Set the Dockerfile path for frontend**

In Railway dashboard → testing env → frontend service → Settings:
- Builder: Dockerfile
- Dockerfile path: `Dockerfile.frontend`

**Step 3: Generate a public domain for frontend**

```bash
railway domain --service frontend --environment testing
```

Note the generated URL (e.g., `frontend-testing-xxxx.up.railway.app`).

**Step 4: Update backend CORS with frontend URL**

```bash
railway variables set CORS_ORIGINS_RAW='["https://frontend-testing-xxxx.up.railway.app"]' --service backend --environment testing
```

**Step 5: Set NEXTAUTH_URL on frontend**

```bash
railway variables set NEXTAUTH_URL=https://frontend-testing-xxxx.up.railway.app --service frontend --environment testing
```

---

### Task 6: Trigger initial deployment

**Step 1: Push to testing branch (if not auto-deploying)**

```bash
git push origin testing
```

Railway should auto-deploy both services from the `testing` branch.

**Step 2: Wait for both deploys to succeed (~3-5 min)**

```bash
list-deployments --service backend --environment testing --limit 1
list-deployments --service frontend --environment testing --limit 1
```

Both should show `SUCCESS`.

**Step 3: Check backend logs for clean startup**

```bash
get-logs --service backend --environment testing --logType deploy --lines 30
```

Expected:
- `SKIP_TRACK_SEEDING=true — skipping hardcoded track seed`
- `Computed corner hashes for 0 track(s)` (empty DB)
- No errors

**Step 4: Verify health endpoint**

```bash
curl https://backend-testing-xxxx.up.railway.app/health
```

Expected: `{"status": "ok", "db": "ok"}`

---

## Phase 4: E2E Test — Upload & Auto-Discovery

### Task 7: Upload a Barber session CSV

**Step 1: Open the frontend in a browser**

Navigate to `https://frontend-testing-xxxx.up.railway.app`

Since `DEV_AUTH_BYPASS=true`, you should be auto-authenticated as `dev-user`.

**Step 2: Upload a Barber Motorsports Park CSV**

Use any Barber session CSV from the `data/session/` directory, e.g.:
`session_20260222_162404_barber_motorsports_park_v3.csv`

Upload via the drag-and-drop zone on the welcome page.

**Step 3: Check backend logs for auto-discovery**

```bash
get-logs --service backend --environment testing --logType deploy --lines 50 --filter "auto-discover"
```

Expected log lines:
- `Auto-discovered track: Barber Motorsports Park (xxxm) via OSM`
- `Auto-created draft track: barber-motorsports-park`

If auto-discovery fails (OSM timeout, no results), check:
```bash
get-logs --service backend --environment testing --logType deploy --lines 50 --filter "ERROR"
```

**Step 4: Verify the session loaded**

The upload should complete and show the session report page. Check:
- [ ] Session report renders (lap times, metrics)
- [ ] Corners are detected (auto-detected, not from DB since track was unknown at upload time)
- [ ] Track map shows the track outline

---

### Task 8: Verify auto-discovered track in the admin API

**Step 1: List tracks via admin API**

```bash
curl -s https://backend-testing-xxxx.up.railway.app/api/admin/tracks \
  -H "Authorization: Bearer dev" | python3 -m json.tool
```

Expected: `{"tracks": ["barber-motorsports-park"]}` (auto-discovered from OSM)

**Step 2: Get track editor data**

```bash
curl -s https://backend-testing-xxxx.up.railway.app/api/admin/tracks/barber-motorsports-park/editor \
  -H "Authorization: Bearer dev" | python3 -m json.tool | head -20
```

Expected: JSON with `track_slug`, `geometry`, `corners` array.
The corners should have been auto-detected by the enrichment pipeline.

---

### Task 9: Test enrichment trigger

**Step 1: Re-run enrichment on the auto-discovered track**

```bash
curl -s -X POST https://backend-testing-xxxx.up.railway.app/api/admin/tracks/barber-motorsports-park/enrich \
  -H "Authorization: Bearer dev" | python3 -m json.tool
```

Expected: JSON showing enrichment steps completed (corners detected, classified, elevation fetched, brake markers computed).

**Step 2: Check enrichment logs**

```bash
get-logs --service backend --environment testing --logType deploy --lines 30 --filter "enrich"
```

---

### Task 10: Test OSM import of a different track

**Step 1: Import Road Atlanta via OSM**

```bash
curl -s -X POST https://backend-testing-xxxx.up.railway.app/api/admin/tracks/import/osm \
  -H "Authorization: Bearer dev" \
  -H "Content-Type: application/json" \
  -d '{"lat": 34.1482, "lon": -83.8205, "radius_m": 2000}' | python3 -m json.tool
```

Expected: Track created with corners auto-detected.

**Step 2: Verify it appears in the track list**

```bash
curl -s https://backend-testing-xxxx.up.railway.app/api/admin/tracks \
  -H "Authorization: Bearer dev" | python3 -m json.tool
```

Expected: Both `barber-motorsports-park` and the Road Atlanta slug appear.

---

### Task 11: Test Track Editor save (the bug we just fixed)

**Step 1: Open Track Editor in the browser**

Navigate to `https://frontend-testing-xxxx.up.railway.app/admin/track-editor`

**Step 2: Select the auto-discovered Barber track**

**Step 3: Move a corner (drag T4 or any corner)**

**Step 4: Click Save**

Expected: Save succeeds (green toast), no 500 error.

**Step 5: Reload the session page**

Navigate back to the session. Verify:
- [ ] Track map shows corner labels at the new positions
- [ ] Coaching may regenerate (if corners changed significantly)

---

### Task 12: Verify coaching generation

**Step 1: Check if coaching report was generated**

```bash
get-logs --service backend --environment testing --logType deploy --lines 30 --filter "coaching"
```

Expected: Lines showing coaching generation for the uploaded session.

**Step 2: Open the session report**

Verify:
- [ ] AI coaching insights appear in the report
- [ ] Corner-specific coaching notes are present
- [ ] Debrief tab has content

---

## Phase 5: Validation Checklist

### Task 13: Run the full validation checklist

Go through each item and verify:

**Auto-Discovery Pipeline:**
- [ ] Upload of unknown track triggers OSM query
- [ ] OSM result creates a `Track` row in DB with `source='osm-auto'`
- [ ] Enrichment runs automatically (corners detected, classified)
- [ ] Session completes processing even if auto-discovery fails (graceful degradation)
- [ ] Second upload of same track matches via GPS (no duplicate auto-discovery)

**Track Admin API:**
- [ ] `GET /api/admin/tracks` lists all tracks
- [ ] `GET /api/admin/tracks/{slug}/editor` returns geometry + corners
- [ ] `PUT /api/admin/tracks/{slug}/corners` saves corners (no 500)
- [ ] `POST /api/admin/tracks/import/osm` imports from OSM
- [ ] `POST /api/admin/tracks/{slug}/enrich` re-runs enrichment
- [ ] `POST /api/admin/tracks/{slug}/validate` runs validation gates

**Corner Flow:**
- [ ] Editor save updates `TrackCornerV2` rows in DB
- [ ] Hybrid cache updates after save
- [ ] Session corners update after save (staleness detection)
- [ ] Track map shows updated corner positions

**Coaching Integration:**
- [ ] Auto-coaching generates on upload
- [ ] Coaching uses correct corners (auto-detected or editor-edited)
- [ ] Corner-specific coaching notes appear

**Enrichment Steps (check logs for each):**
- [ ] Adaptive corner detection ran
- [ ] Corner type classification ran
- [ ] Elevation fetch attempted (may fail if USGS/Copernicus down)
- [ ] Brake marker computation ran

Record results and any failures in a comment or doc.

---

## Phase 6: Cleanup

### Task 14: Tear down testing environment

After validation is complete:

**Step 1: Confirm with user before deleting**

Ask: "Testing complete. Ready to delete the `testing` Railway environment and branch?"

**Step 2: Delete Railway environment**

Via Railway dashboard: Settings → Environments → Delete `testing`

This removes:
- Both services in the testing environment
- The PostgreSQL database
- All env vars

**Step 3: Delete the testing branch**

```bash
git checkout staging
git branch -d testing
git push origin --delete testing
```

**Step 4: Remove the `SKIP_TRACK_SEEDING` code (optional)**

If the feature gate is useful for future testing, keep it. If not:

```bash
git checkout staging
# Revert the SKIP_TRACK_SEEDING change
git revert <commit-hash-from-task-2>
git push origin staging
```

Recommendation: **Keep it** — it's a zero-cost feature gate useful for future E2E testing.

---

## Failure Modes & Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Backend deploy FAILED | Missing env var or Dockerfile path | Check build logs: `get-logs --logType build` |
| `{"status": "degraded"}` on /health | DATABASE_URL not set or DB not provisioned | Check PostgreSQL addon exists in testing env |
| Upload succeeds but no auto-discovery log | OSM Overpass API down or rate-limited | Check logs for OSM errors; retry in 1min |
| 401 on all API calls | `DEV_AUTH_BYPASS` not set or `RAILWAY_ENVIRONMENT` guard blocking | Check env var; backend safety guard raises 503 if on Railway + bypass |
| Frontend shows blank page | `BACKEND_URL` wrong or CORS blocking | Check browser console for CORS errors; verify `CORS_ORIGINS_RAW` |
| Corner save returns 500 | Field name mismatch (should be fixed) | Check backend logs for TypeError |
| Coaching not generating | `ANTHROPIC_API_KEY` not set | Set the key from staging |
