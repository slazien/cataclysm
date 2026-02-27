# Developer Guide

## Prerequisites

- Python 3.11+
- Node.js 22+
- PostgreSQL 16+ (or use Docker Compose)

## Setup

### Option 1: Docker Compose (Recommended for first-time setup)

```bash
# Clone the repository
git clone https://github.com/<org>/cataclysm.git
cd cataclysm

# Create .env file from example
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and Google OAuth credentials

# Start all services
docker compose up
```

Services:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- PostgreSQL: localhost:5432

### Option 2: Manual Setup

#### Backend

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate    # Linux/Mac
# .venv\Scripts\activate     # Windows

# Install core engine + dev dependencies
pip install -e ".[dev]"

# Install backend dependencies
pip install fastapi uvicorn pydantic-settings sqlalchemy asyncpg alembic httpx pytest-asyncio python-multipart

# Run database migrations
alembic upgrade head

# Start backend server
uvicorn backend.api.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:3000, proxies API calls to http://localhost:8000.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://cataclysm:cataclysm@localhost:5432/cataclysm` | PostgreSQL connection |
| `ANTHROPIC_API_KEY` | For coaching | — | Claude API key |
| `NEXTAUTH_SECRET` | For auth | `dev-secret-...` | Shared JWT secret |
| `GOOGLE_CLIENT_ID` | For auth | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For auth | — | Google OAuth secret |
| `CORS_ORIGINS` | Production | `["http://localhost:3000"]` | JSON array of allowed origins |
| `DEV_AUTH_BYPASS` | Dev only | `false` | Skip auth for QA testing |
| `SESSION_DATA_DIR` | No | `data/session` | Path to session CSV storage |
| `COACHING_DATA_DIR` | No | `data/coaching` | Path to coaching report storage |

## Code Quality

### Quality Gates

All of these **must pass** before committing:

```bash
# 1. Lint (zero errors)
ruff check cataclysm/ tests/ backend/

# 2. Format (auto-format, then verify)
ruff format cataclysm/ tests/ backend/

# 3. Type check (zero errors)
mypy cataclysm/ backend/

# 4. Tests (all pass)
pytest tests/ backend/tests/ -v

# 5. Coverage (90%+ on cataclysm/)
pytest --cov=cataclysm --cov-report=term-missing

# 6. Frontend lint
cd frontend && npm run lint
```

### Python Style

- Python 3.11+, type hints required on all functions
- Line length: 100 characters
- All files start with `from __future__ import annotations`
- Ruff rules: E, F, W, I (isort), N, UP, B, SIM
- Module-level constants in `UPPER_SNAKE_CASE`
- Dataclasses for all structured data (not dicts)
- Mypy strict mode: `disallow_untyped_defs = true`

### Frontend Style

- TypeScript strict mode
- ESLint with Next.js configuration
- Tailwind CSS 4 for styling (no custom CSS unless necessary)
- Radix UI + shadcn/ui for accessible components

## Testing

### Core Engine Tests (`tests/`)

40+ test files covering all core modules. Tests use synthetic data generated in `conftest.py` — never depend on real session files.

```bash
# Run all core tests
pytest tests/ -v

# Run single module
pytest tests/test_engine.py

# Run single test
pytest tests/test_engine.py::test_name

# With coverage report
pytest tests/ --cov=cataclysm --cov-report=term-missing

# Debug mode (stop on first failure, short traceback)
pytest tests/ -x --tb=short

# Drop into debugger on failure
pytest tests/ --pdb
```

**Test fixtures** (`tests/conftest.py`):
- `_build_header()` — Generates RaceChrono v3 metadata + header rows
- `_build_data_row()` — Parameterized row generator for synthetic telemetry
- Autouse fixtures reset coaching validator state between tests

### Backend Tests (`backend/tests/`)

18 test files for API endpoints and services. Uses in-memory SQLite for test isolation.

```bash
# Run backend tests
pytest backend/tests/ -v

# All tests together
pytest tests/ backend/tests/ -v
```

**Backend test fixtures** (`backend/tests/conftest.py`):
- In-memory SQLite database (JSONB → JSON compatibility)
- Test user: `AuthenticatedUser(user_id="test-user-123", email="test@example.com")`
- Async session factory bound to test engine
- `_disable_auto_coaching` autouse fixture prevents Claude API calls in tests

### Frontend Tests

```bash
cd frontend
npm run test           # Vitest
```

Current frontend test coverage is limited to stores and cursor sync logic. Most frontend QA is done via manual testing or Playwright automation.

### Writing New Tests

Every new module needs a companion test file:

```bash
# Core module: cataclysm/new_module.py → tests/test_new_module.py
# Backend:     backend/api/routers/new.py → backend/tests/test_new.py
```

Test requirements:
- Use synthetic data fixtures (never real session files)
- Mock external APIs (Claude API, weather)
- Test edge cases: empty inputs, single elements, None values, boundary conditions
- Cover error paths, not just happy paths

## Project Structure

```
cataclysm/
├── cataclysm/              # Core Python engine
│   ├── parser.py           # CSV parsing
│   ├── engine.py           # Distance-domain resampling
│   ├── corners.py          # Corner detection
│   ├── coaching.py         # AI coaching (Claude API)
│   ├── gains.py            # Time-gain estimation
│   └── ...                 # 35+ analysis modules
├── backend/                # FastAPI backend
│   ├── api/
│   │   ├── main.py         # App entry point
│   │   ├── config.py       # Pydantic Settings
│   │   ├── dependencies.py # Auth, DB injection
│   │   ├── routers/        # 13 API routers
│   │   ├── services/       # Business logic
│   │   ├── schemas/        # Pydantic models
│   │   └── db/             # SQLAlchemy + Alembic
│   └── tests/              # Backend tests
├── frontend/               # Next.js 16 frontend
│   ├── src/
│   │   ├── app/            # Pages (App Router)
│   │   ├── components/     # React components
│   │   ├── stores/         # Zustand stores
│   │   ├── hooks/          # Custom hooks
│   │   └── lib/            # API client, types
│   └── package.json
├── tests/                  # Core engine tests
├── data/                   # Runtime data
├── docs/                   # Documentation
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── pyproject.toml
```

## Git Workflow

- **Development branch**: `nextjs-rewrite`
- **Production branch**: `main`
- Railway auto-deploys from `main` only

```bash
# Development work
git checkout nextjs-rewrite
# ... make changes ...
git add <files>
git commit -m "Description of changes"
git push origin nextjs-rewrite

# Deploy to production
git checkout main
git merge nextjs-rewrite
git push origin main
git checkout nextjs-rewrite
```

## CI/CD

GitHub Actions runs on push to `main`/`nextjs-rewrite` and PRs to `main`:

**Backend job**:
1. Checkout → Setup Python 3.12
2. Install dependencies
3. `ruff check` + `ruff format --check`
4. `mypy cataclysm/ backend/ --exclude migrations`
5. `pytest tests/ backend/tests/ -v --tb=short`

**Frontend job**:
1. Checkout → Setup Node 22
2. `npm ci` → `npm run lint` → `npm run build`

## Adding a New Analysis Module

1. Create `cataclysm/new_module.py`:
   ```python
   from __future__ import annotations

   from dataclasses import dataclass
   import pandas as pd

   @dataclass
   class NewAnalysisResult:
       # Define your output structure
       ...

   def compute_new_analysis(
       resampled_laps: dict[int, pd.DataFrame],
       corners: list[Corner],
   ) -> NewAnalysisResult:
       """Compute new analysis from resampled laps."""
       ...
   ```

2. Create `tests/test_new_module.py` with synthetic data tests

3. Add backend endpoint in `backend/api/routers/analysis.py`:
   ```python
   @router.get("/{session_id}/new-analysis")
   async def get_new_analysis(
       session_id: str,
       user: AuthenticatedUser = Depends(get_current_user),
   ) -> NewAnalysisResponse:
       ...
   ```

4. Add Pydantic schema in `backend/api/schemas/`

5. Add frontend hook in `frontend/src/hooks/`:
   ```typescript
   export function useNewAnalysis(sessionId: string) {
     return useQuery({
       queryKey: ['newAnalysis', sessionId],
       queryFn: () => fetchApi(`/api/sessions/${sessionId}/new-analysis`),
       enabled: !!sessionId,
     })
   }
   ```

6. Run all quality gates before committing
