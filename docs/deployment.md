# Deployment Guide

Cataclysm supports two deployment targets:
- **Railway** (PaaS) — auto-deploys from `main` branch
- **Hetzner VPS** (self-managed) — auto-deploys from `main-hetzner` branch via GitHub Actions

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

## Environments

Railway has two environments, each with its own services and database:

| Environment | Branch | Frontend URL | Backend URL |
|-------------|--------|-------------|-------------|
| **production** | `main` | `https://cataclysm.up.railway.app` | `https://backend-production-4c97.up.railway.app` |
| **staging** | `staging` | `https://cataclysm-staging.up.railway.app` | `https://backend-staging-0dbd.up.railway.app` |

## Auto-Deployment

Each environment auto-deploys from its linked branch. All development work goes to `staging` by default.

**Deployment workflow**:
```bash
# 1. Develop on staging → auto-deploys to staging environment
git checkout staging
# ... make changes ...
git add <files> && git commit -m "Description"
git push origin staging
# → Staging deploys automatically. QA on staging URLs.

# 2. When ready for production (explicit decision only)
git checkout main
git merge staging
git push origin main
# → Production deploys automatically.

# 3. Switch back to dev
git checkout staging
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

---

## Hetzner VPS Deployment

### Architecture

```
┌──────────────────────────────────────────────────────┐
│  Hetzner CX32 (Ashburn)                             │
│                                                       │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │  Caddy    │───▶│ Frontend │    │ Grafana  │       │
│  │  :80/:443 │    │  :3000   │    │  :3000   │       │
│  │           │───▶│          │    │          │       │
│  │           │    └──────────┘    └──────────┘       │
│  │           │    ┌──────────┐    ┌────────────┐     │
│  │           │───▶│ Backend  │    │ Prometheus │     │
│  │           │    │  :8000   │    │  :9090     │     │
│  └──────────┘    └──────────┘    └────────────┘     │
│                   ┌──────────┐    ┌──────────┐       │
│                   │ Postgres │    │  Dozzle  │       │
│                   │  :5432   │    │  :8080   │       │
│                   └──────────┘    └──────────┘       │
│                   ┌──────────────┐ ┌──────────┐      │
│                   │ Node Exporter│ │ cAdvisor │      │
│                   │  :9100       │ │  :8080   │      │
│                   └──────────────┘ └──────────┘      │
│                                                       │
│  Docker Compose internal network                      │
│  Volumes: pgdata, grafana-data, prometheus-data       │
└──────────────────────────────────────────────────────┘
```

10 services orchestrated by Docker Compose. Only Caddy exposes ports 80/443 to the internet.

### Deployment Workflow

GitHub Actions triggers on push to `main-hetzner`:
1. Run lint + tests (reuses CI workflow)
2. Build Docker images (frontend + backend)
3. Push to `ghcr.io/slazien/cataclysm/`
4. SSH into VPS, pull images, restart containers
5. Health check verification

```bash
# Develop on hetzner-migration
git checkout hetzner-migration
# ... make changes ...
git push origin hetzner-migration

# Deploy to Hetzner
git checkout main-hetzner
git merge hetzner-migration
git push origin main-hetzner
# → GitHub Actions auto-deploys
```

### Initial VPS Setup

1. **Provision CX32** in Hetzner Cloud console (Ashburn, Ubuntu 24.04, add SSH key)

2. **Run setup script**:
   ```bash
   ssh root@<VPS_IP> 'bash -s' < scripts/setup-server.sh
   ```
   This installs Docker, fail2ban, configures UFW (22/80/443), creates `deploy` user, and sets up backup cron.

3. **Clone repo as deploy user**:
   ```bash
   ssh deploy@<VPS_IP>
   git clone https://github.com/slazien/cataclysm.git /opt/cataclysm
   cd /opt/cataclysm && git checkout main-hetzner
   ```

4. **Create `.env`**:
   ```bash
   cp .env.example .env
   nano .env  # Fill in real values
   ```

5. **Docker login to GHCR**:
   ```bash
   docker login ghcr.io -u YOUR_GITHUB_USER
   ```

6. **Start services**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

### GitHub Secrets Required

Configure these in your GitHub repository settings:

| Secret | Value |
|--------|-------|
| `VPS_HOST` | VPS IP address |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | Private SSH key for deploy user |

`GITHUB_TOKEN` is automatically available for GHCR access.

### Data Migration from Railway

```bash
# 1. Export from Railway
railway run pg_dump -Fc > railway_backup.dump
scp railway_backup.dump deploy@<VPS_IP>:/opt/backups/

# 2. Import on VPS (start postgres first)
docker compose -f docker-compose.prod.yml up -d postgres
sleep 5
docker exec -i cataclysm-postgres-1 pg_restore \
    -U cataclysm -d cataclysm --clean < /opt/backups/railway_backup.dump

# 3. Start remaining services
docker compose -f docker-compose.prod.yml up -d
```

### Backup Management

Daily automated backups at 03:00 UTC via cron (`scripts/pg_backup.sh`):
- Location: `/opt/backups/`
- Format: PostgreSQL custom format (`.dump`)
- Retention: 7 days

Manual backup:
```bash
/opt/cataclysm/scripts/pg_backup.sh
```

Restore:
```bash
docker exec -i cataclysm-postgres-1 pg_restore \
    -U cataclysm -d cataclysm --clean < /opt/backups/cataclysm_YYYYMMDD.dump
```

### Monitoring

| Tool | URL | Purpose |
|------|-----|---------|
| Grafana | `http://<VPS_IP>/grafana` | Dashboards (CPU, memory, request metrics) |
| Dozzle | `http://<VPS_IP>/dozzle` | Live Docker container logs |
| Prometheus | Internal only | Metrics collection + alerting |

### Adding a Custom Domain

1. Update `Caddyfile`: change `:80` to `yourdomain.com` (Caddy auto-provisions TLS)
2. Update `.env`: set `NEXTAUTH_URL`, `CORS_ORIGINS` to the domain
3. Restart Caddy: `docker compose -f docker-compose.prod.yml restart caddy`

### Hetzner Troubleshooting

**Container won't start**: Check logs with `docker compose -f docker-compose.prod.yml logs <service>`

**Health check fails**: Ensure postgres is healthy first: `docker compose -f docker-compose.prod.yml ps`

**GHCR pull fails**: Re-run `docker login ghcr.io` on the VPS

**Disk space**: Check with `df -h`. Prune old images: `docker image prune -a`
