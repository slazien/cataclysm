# Cataclysm

AI-powered motorsport telemetry analysis and coaching platform for track day drivers.

## What It Does

Upload RaceChrono CSV telemetry exports and get:
- **Automated corner detection** with per-corner KPIs (braking, trail-braking, min speed, throttle)
- **AI coaching reports** via Claude, grading each corner with specific improvement tips
- **Lap comparison** with delta-T overlay in the distance domain
- **Progress tracking** across sessions with trend analysis
- **PDF session reports** for post-session debrief

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS, D3.js |
| Backend | FastAPI, Python 3.11+, SQLAlchemy + asyncpg |
| Database | PostgreSQL (metadata) + in-memory (telemetry) |
| AI | Claude Haiku 4.5 via Anthropic API |
| Deployment | Railway (auto-deploy from `main`) |

## Architecture

```
RaceChrono CSV → parser.py → engine.py → corners.py → coaching.py
                                ↓              ↓
                          distance-domain   corner KPIs
                          resampled @0.7m   per lap
```

All processing converts time-domain GPS telemetry into **distance-domain** data (resampled at 0.7m intervals). This normalizes lap data for direct comparison regardless of speed.

**Dual storage model:**
- **PostgreSQL** — user accounts, session metadata, coaching reports, equipment profiles
- **In-memory dicts** — full telemetry DataFrames for fast analysis (reloaded from DB on startup)

See `docs/` for detailed architecture documentation.

## Quick Start

```bash
# Clone and set up Python
git clone https://github.com/yourusername/cataclysm.git
cd cataclysm
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Set up environment
cp .env.example .env  # Add your ANTHROPIC_API_KEY

# Run backend
uvicorn backend.api.main:app --reload --port 8000

# Run frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Or use Docker:
```bash
docker compose up
```

## Development

```bash
# Run tests
pytest                                      # all tests
pytest -m "not slow"                        # fast tests only (~12s)
pytest --cov=cataclysm --cov-report=term   # with coverage

# Lint and format (must pass before committing)
ruff check cataclysm/ tests/ backend/
ruff format cataclysm/ tests/ backend/
mypy cataclysm/ backend/
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI coaching |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `NEXTAUTH_SECRET` | Yes | Shared secret for JWT auth |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client secret |
| `DEV_AUTH_BYPASS` | No | Set `true` to skip auth (dev/QA only) |
| `CORS_ORIGINS_RAW` | No | JSON array of allowed origins |

## Deployment

Deployed on Railway with auto-deploy from `main` branch:
- **Frontend**: https://cataclysm.up.railway.app
- **Backend**: https://backend-production-4c97.up.railway.app

## Documentation

- `docs/architecture.md` — System architecture and data flow
- `docs/api-reference.md` — All 70+ API endpoints with examples
- `docs/developer-guide.md` — Development setup and conventions
- `docs/frontend-guide.md` — Frontend architecture and components
- `docs/deployment.md` — Railway deployment and configuration
