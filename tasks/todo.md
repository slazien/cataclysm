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

## Phase 1: Sessions + Overview Tab [COMPLETE]
- [x] Backend: services/pipeline.py wrapping cataclysm/ (44 tests, 91% coverage)
- [x] Backend: services/serializers.py
- [x] Backend: Session upload, CRUD, track folder scan endpoints
- [x] Backend: Analysis endpoints (corners, consistency, grip, gains, delta, linked)
- [x] Backend: In-memory session store (DB persistence deferred)
- [x] Backend: Tests (44 passing)
- [x] Frontend: Zustand store + TanStack Query hooks
- [x] Frontend: Sidebar (track selector, file upload, session list)
- [x] Frontend: D3 infra (useD3, theme.ts, scales.ts)
- [x] Frontend: D3 charts (LapTimesBar, LapConsistency, TrackSpeedMap, TrackConsistencyMap, TractionCircle)
- [x] Frontend: MetricCard, OverviewTab assembly
- [x] Frontend: UI components (Button, Select, FileUpload, Spinner, Table)

## Phase 2: Speed Trace Tab + Linked Chart [COMPLETE]
- [x] Backend: /charts/linked bundle, /delta endpoint (done in Phase 1)
- [x] Frontend: SpeedTrace, DeltaT, TrackMapInteractive, BrakeThrottle D3 charts
- [x] Frontend: LinkedSpeedMap with hover sync + zoom sync across panels
- [x] Frontend: SpeedTraceTab assembly with lap multi-selector

## Phase 3: Corners Tab [COMPLETE]
- [x] Backend: /corners/all-laps, corner detail data (done in Phase 1)
- [x] Frontend: CornerKPITable (sortable, comparison deltas)
- [x] Frontend: CornerDetailChart (speed + G-force dual subplot)
- [x] Frontend: CornerMiniMap (canvas+SVG with entry/apex/exit markers)
- [x] Frontend: BrakeConsistency (variation chart with std dev bands)
- [x] Frontend: CornersTab (comparison selector, expandable per-corner details)
- [x] Frontend: Expandable + Popover UI components

## Phase 4: AI Coach Tab [COMPLETE]
- [x] Backend: POST/GET coaching report (mock-ready, asyncio.to_thread)
- [x] Backend: WebSocket chat with CoachingContext
- [x] Backend: In-memory coaching store
- [x] Backend: Tests (8 coaching tests, 52 total backend)
- [x] Frontend: GainPerCorner, IdealLapOverlay, IdealLapDelta D3 charts
- [x] Frontend: CoachingReportView, CornerGrades, PriorityCorners
- [x] Frontend: ChatInterface (WebSocket-based)
- [x] Frontend: CoachingTab (generate + display + gain analysis + chat)

## Phase 5: Trends Tab [COMPLETE]
- [x] Backend: /trends/{track} endpoint (already implemented Phase 1, added lap_times_s)
- [x] Frontend: LapTimeTrend (3-line: best/top3/theoretical)
- [x] Frontend: ConsistencyTrend (with background score bands)
- [x] Frontend: SessionBoxPlot (Q1-Q3 boxes, whiskers, best lap diamonds)
- [x] Frontend: CornerHeatmap (multi-metric selector)
- [x] Frontend: CornerTrendGrid (small multiples sparklines)
- [x] Frontend: TrendsTab (metrics, milestones, all charts)

## Phase 6: Polish + Deploy
- [ ] Gzip middleware, ETag caching
- [ ] Canvas optimization, error boundaries, loading skeletons
- [ ] Docker multi-stage builds
- [ ] CI/CD (GitHub Actions)
- [ ] Playwright E2E tests
- [ ] Update CLAUDE.md
