# Deployment Guide

Cataclysm is deployed on Railway with 3 services: PostgreSQL, FastAPI backend, and Next.js frontend.

## Railway Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Railway Project                      │
│                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │  PostgreSQL  │  │   Backend   │  │   Frontend   │  │
│  │   (16-Alpine)│  │  (FastAPI)  │  │  (Next.js)   │  │
│  │   :5432      │  │   :8000     │  │   :3000      │  │
│  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘  │
│         │                 │                 │          │
│         └────────┬────────┘                 │          │
│           Private Network              Public URL     │
│      (backend.railway.internal)                       │
└──────────────────────────────────────────────────────┘

Public URLs:
  Frontend: https://cataclysm.up.railway.app
  Backend:  https://backend-production-4c97.up.railway.app
```

## Auto-Deployment

Railway monitors the `main` branch. Pushing to `main` triggers automatic deployment of both backend and frontend services.

**Deployment workflow**:
```bash
# 1. Develop on nextjs-rewrite
git checkout nextjs-rewrite
# ... make changes ...
git add <files> && git commit -m "Description"
git push origin nextjs-rewrite

# 2. Merge to main for deployment
git checkout main
git merge nextjs-rewrite
git push origin main

# 3. Switch back to dev
git checkout nextjs-rewrite
```

## Environment Variables

### Backend Service

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Auto-set by Railway PostgreSQL addon |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Required for coaching |
| `NEXTAUTH_SECRET` | (random string) | Must match frontend |
| `CORS_ORIGINS` | `["https://cataclysm.up.railway.app"]` | Must be valid JSON array |
| `PORT` | `8000` | Explicitly set (Railway assigns dynamic ports otherwise) |
| `SESSION_DATA_DIR` | `data/session` | Default |
| `COACHING_DATA_DIR` | `data/coaching` | Default |

### Frontend Service

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXTAUTH_SECRET` | (same as backend) | Must match backend |
| `NEXTAUTH_URL` | `https://cataclysm.up.railway.app` | Public URL |
| `GOOGLE_CLIENT_ID` | `...apps.googleusercontent.com` | OAuth |
| `GOOGLE_CLIENT_SECRET` | `...` | OAuth |
| `BACKEND_URL` | `http://backend.railway.internal:8000` | Private network URL |
| `AUTH_TRUST_HOST` | `true` | Required for Railway |

## Docker Configuration

### Backend (`Dockerfile.backend`)

Multi-stage build:
1. **Builder stage**: Python 3.12-slim, installs cataclysm + FastAPI dependencies
2. **Runtime stage**: Python 3.12-slim, copies installed packages

**Startup**: Runs Alembic migrations, then starts uvicorn:
```bash
alembic upgrade head && uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Frontend (`Dockerfile.frontend`)

Multi-stage build:
1. **Builder stage**: Node 22-alpine, builds Next.js project
2. **Runtime stage**: Node 22-alpine, runs standalone Next.js server

**Build arg**: `BACKEND_URL` (set during build for server-side API calls)

### Docker Compose (Local Development)

```bash
docker compose up          # Start all 3 services
docker compose up -d       # Detached mode
docker compose down        # Stop all services
docker compose down -v     # Stop and remove volumes (DB data)
```

Services:
- PostgreSQL 16-Alpine on port 5432 (healthcheck: `pg_isready`)
- Backend on port 8000 (depends on postgres health)
- Frontend on port 3000 (depends on backend)

## Database Migrations

Alembic manages PostgreSQL schema migrations.

```bash
# Create a new migration
alembic revision --autogenerate -m "Add new_table"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current revision
alembic current
```

Migrations are in `backend/api/db/migrations/`. They run automatically on backend startup in Docker.

## Troubleshooting

### CORS Errors

`CORS_ORIGINS` must be a valid JSON array:
```bash
# Correct
CORS_ORIGINS=["https://cataclysm.up.railway.app"]

# Wrong (bare URL)
CORS_ORIGINS=https://cataclysm.up.railway.app
```

Railway strips quotes from environment variables. The config parser handles this by trying JSON, then bracketed, then comma-separated formats.

### CRLF Line Endings

Railway Docker builds fail on Windows CRLF line endings. Ensure these files have LF endings:
- `.dockerignore`
- `railway.json`
- `Dockerfile.backend`
- `Dockerfile.frontend`

```bash
# Fix line endings
sed -i 's/\r$//' .dockerignore railway.json
```

### PORT Mismatch

Backend `PORT=8000` must be explicitly set on Railway. Without it, Railway assigns a dynamic port that won't match the frontend's `BACKEND_URL`.

### NextAuth Secret Mismatch

`NEXTAUTH_SECRET` must be identical on both frontend and backend. The backend uses it to decrypt JWE tokens created by NextAuth.js.

### Database Connection

The `DATABASE_URL` must use the `postgresql+asyncpg://` scheme (not `postgres://` or `postgresql://`). Railway provides `postgres://` by default — you may need to adjust the prefix.

### Auth Bypass for QA

Set `DEV_AUTH_BYPASS=true` on the backend to skip authentication for testing. This returns a fake dev user for all requests.

## Monitoring

### Health Check

```bash
curl https://backend-production-4c97.up.railway.app/health
# {"status": "ok"}
```

### Logs

View logs via Railway dashboard or CLI:
```bash
railway logs --service backend
railway logs --service frontend
```

### API Documentation

Swagger UI is available at the backend URL:
```
https://backend-production-4c97.up.railway.app/docs
```
