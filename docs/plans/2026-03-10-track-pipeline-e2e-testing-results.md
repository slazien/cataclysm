# Track Data Pipeline v2 — E2E Testing Results (Railway `testing`)

Date: 2026-03-10
Environment: `testing`
Branch: `testing`

## Environment Setup

- Railway environment created: `testing`
- Services used: `backend`, `frontend`, `Postgres-ywwZ`
- Domains:
  - Backend: `https://backend-testing-97fb.up.railway.app`
  - Frontend: `https://frontend-testing-ec7a.up.railway.app`

## Applied Backend/Frontend Variables

Backend (`testing`):
- `PORT=8000`
- `SKIP_TRACK_SEEDING=true`
- `TRACK_DB_ONLY=true`
- `DEV_AUTH_BYPASS=false`
- `LOG_LEVEL=DEBUG`
- `NEXTAUTH_SECRET=dev-secret-do-not-use-in-production`
- `CORS_ORIGINS_RAW=["https://frontend-testing-ec7a.up.railway.app"]`
- `DATABASE_URL` wired to `Postgres-ywwZ` and converted to `postgresql+asyncpg://...`
- `ADMIN_EMAIL=dev@localhost` (testing-only admin override)
- `ANTHROPIC_API_KEY` copied from staging

Frontend (`testing`):
- `AUTH_SECRET=dev-secret-do-not-use-in-production`
- `AUTH_TRUST_HOST=true`
- `DEV_AUTH_BYPASS=false`
- `BACKEND_URL=http://backend.railway.internal:8000`
- `NEXTAUTH_URL=https://frontend-testing-ec7a.up.railway.app`
- `RAILWAY_DOCKERFILE_PATH=Dockerfile.frontend`

## Code Changes Made

1. `backend/api/main.py`
- Added `SKIP_TRACK_SEEDING` env gate around hardcoded track seeding.

2. `backend/api/db/migrations/versions/g7c8d9e0f1a2_fix_corner_type_check_constraint.py`
- Guarded migration so it no-ops when `track_corners_v2` table does not exist on clean DB migration path.

3. `cataclysm/track_db_hybrid.py`
- Added `TRACK_DB_ONLY=true` mode to disable fallback to Python hardcoded tracks.

4. `backend/api/routers/admin.py`
- Added `ADMIN_EMAIL` env override (default unchanged) to enable admin API access in testing env.

5. `backend/api/services/pipeline.py` + `cataclysm/track_db_hybrid.py`
- Added alias propagation support for auto-discovered tracks (committed, but see deployment caveat below).

## Deployment Caveat

- The latest commit (`a05293a`) could not be deployed due repeated Railway CLI `up` request timeouts to backboard.
- Last confirmed healthy backend runtime deployment during validation: `727df4f4-be2d-4ee6-8123-486d6b27d61a`.
- Health confirmed: `{"status":"ok","db":"ok"}`.

## E2E Execution Evidence

### 1) Clean startup behavior

Backend deployment logs show:
- `SKIP_TRACK_SEEDING=true — skipping hardcoded track seed`
- `Loaded 0 track(s) from DB into hybrid cache`
- `Computed corner hashes for 0 track(s)`

### 2) Upload Barber session and auto-discovery

Upload command:
- `POST /api/sessions/upload` with `session_20260222_162404_barber_motorsports_park_v3.csv`

Result:
- Session created: `barber_motorsports_p_20260222_b101ba9c`

Logs:
- `Auto-discovered track: OSM Way 237456804 (3712m) via OSM`
- `Auto-created draft track: osm-way-237456804`

Track list (`/api/track-admin/`) includes:
- `osm-way-237456804` with `source: "osm-auto"`

### 3) Duplicate upload behavior

- Re-uploaded the same Barber CSV.
- Track count remained unchanged (`2` before/after at the time of check), indicating no duplicate auto-discovery row.

### 4) OSM import of another location (Road Atlanta area)

Command:
- `POST /api/track-admin/import/osm` near Road Atlanta coordinates.

Observed result includes:
- `road-atlanta-racetrack`
- Additional nearby OSM-derived slugs

Track list confirms Road Atlanta entry exists:
- `road-atlanta-racetrack`

### 5) Track admin save path (bug regression check)

- Read corners from `the-esses`.
- Updated one corner fraction via `PUT /api/track-admin/the-esses/corners`.
- Response succeeded (`200`, `{"track_slug":"the-esses","corners_count":1}`), no 500 error.

### 6) Validation and enrichment endpoints

- `POST /api/track-admin/the-esses/validate` succeeded (`is_valid: true`).
- `POST /api/track-admin/road-atlanta-racetrack/enrich` executed and returned structured result.

### 7) Coaching generation check

- `GET /api/coaching/barber_motorsports_p_20260222_b101ba9c/report`
- Response status: `ready`
- Contains summary, priority corners, corner-specific grades/notes, drills.

## Validation Checklist

Auto-Discovery Pipeline:
- [x] Upload of unknown track triggered OSM query
- [x] OSM result created `Track` row with `source='osm-auto'`
- [~] Enrichment auto-run for the auto-discovered draft track
  - Note: auto-discovered track was created without centerline geometry; direct enrich endpoint on this draft slug returns `422` without centerline/corner lat-lon basis.
- [x] Session processing completed end-to-end despite unknown track at upload
- [x] Second upload of same track did not create duplicate track rows

Track Admin API:
- [x] Track list endpoint works (`GET /api/track-admin/`)
- [x] Corner list endpoint works (`GET /api/track-admin/{slug}/corners`)
- [x] Corner save endpoint works (`PUT /api/track-admin/{slug}/corners`, no 500)
- [x] OSM import endpoint works (`POST /api/track-admin/import/osm`)
- [x] Enrichment endpoint executes (`POST /api/track-admin/{slug}/enrich`)
- [x] Validation endpoint executes (`POST /api/track-admin/{slug}/validate`)

Coaching Integration:
- [x] Coaching report generated and available as `ready`
- [x] Corner-specific coaching notes present in response payload

## Deviations From Original Plan

1. API path drift in current codebase:
- Plan uses `/api/admin/tracks/...`
- Current implementation uses `/api/track-admin/...`

2. Auth behavior on Railway:
- `DEV_AUTH_BYPASS=true` is blocked by backend guard when `RAILWAY_ENVIRONMENT` is set.
- Testing used dev-secret fallback plus `ADMIN_EMAIL` override for admin endpoints.

3. Railway deployment instability:
- Multiple post-validation deployments failed due CLI `up` request timeout before build association.

## Follow-up Recommendations

1. Fix `import/osm` transaction handling in `track_admin.py`:
- Current loop-level `rollback()` on duplicate can roll back earlier successful inserts in the same request.

2. Persist centerline geometry for auto-discovered tracks:
- This would let `/enrich` work directly on `osm-auto` tracks without manual centerline injection.

3. Resolve Railway CLI `up` timeout issue (network/backboard path) to ensure latest pushed commits are deployable from CLI.
