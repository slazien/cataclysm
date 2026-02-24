# Next.js + FastAPI Rewrite

## Phase 0: Scaffold [COMPLETE]
- [x] Create backend/ FastAPI app with CORS, health check, OpenAPI docs
- [x] Create backend config (pydantic-settings)
- [x] Set up PostgreSQL + SQLAlchemy 2.0 async + Alembic migrations
- [x] Create backend router stubs (sessions, analysis, coaching, trends, tracks)
- [x] Create backend schemas (Pydantic v2)
- [x] Create frontend/ with Next.js App Router, TypeScript, Tailwind
- [x] Set up dark theme CSS globals
- [x] Create docker-compose.yml (backend + frontend + postgres)
- [x] Create Dockerfiles (backend + frontend)
- [x] Create Makefile (dev, test, lint, build)
- [x] Backend deps installed in .venv (fastapi, uvicorn, pydantic-settings, sqlalchemy, asyncpg, alembic)
- [x] Verify: ruff/mypy/pytest all pass (340 existing + 1 backend)

## Phase 1: Sessions + Overview Tab
- [x] Backend: services/pipeline.py wrapping cataclysm/ (44 tests, 91% coverage)
- [x] Backend: services/serializers.py
- [x] Backend: Session upload, CRUD, track folder scan endpoints
- [x] Backend: Analysis endpoints (corners, consistency, grip, gains, delta, linked)
- [x] Backend: In-memory session store (DB persistence deferred)
- [x] Backend: Tests (44 passing)
- [ ] Frontend: Zustand store + TanStack Query hooks
- [ ] Frontend: Sidebar (track selector, file upload, session list)
- [ ] Frontend: D3 infra (useD3, theme.ts, scales.ts)
- [ ] Frontend: D3 charts (LapTimesBar, LapConsistency, TrackSpeedMap, etc.)
- [ ] Frontend: MetricCard, OverviewTab assembly
- [ ] Frontend: Tests

## Phase 2: Speed Trace Tab + Linked Chart
- [ ] Backend: /charts/linked bundle, /delta endpoint
- [ ] Frontend: SpeedTrace, DeltaT, TrackMap, BrakeThrottle
- [ ] Frontend: LinkedSpeedMap with HoverController + ZoomController
- [ ] Frontend: SpeedTraceTab assembly + tests

## Phase 3: Corners Tab
- [ ] Backend: /corners/all-laps, corner detail data
- [ ] Frontend: CornerKPITable, CornerDetailChart, CornerMiniMap, BrakeConsistency
- [ ] Frontend: CornersTab assembly + tests

## Phase 4: AI Coach Tab
- [ ] Backend: Report generation (POST→job, GET polls), SSE progress
- [ ] Backend: WebSocket chat, CoachingContext DB
- [ ] Frontend: GainPerCorner, IdealLapOverlay, IdealLapDelta
- [ ] Frontend: CoachingReport, CornerGrades, PriorityCorners, ChatInterface
- [ ] Frontend: CoachingTab assembly + tests

## Phase 5: Trends Tab
- [ ] Backend: /trends/{track} endpoint
- [ ] Frontend: LapTimeTrend, ConsistencyTrend, CornerHeatmap, SessionBoxPlot
- [ ] Frontend: TrendsTab assembly + tests

## Phase 6: Polish + Deploy
- [ ] Gzip middleware, ETag caching
- [ ] Canvas optimization, error boundaries, loading skeletons
- [ ] Docker multi-stage builds
- [ ] CI/CD (GitHub Actions)
- [ ] Playwright E2E tests
- [ ] Update CLAUDE.md
