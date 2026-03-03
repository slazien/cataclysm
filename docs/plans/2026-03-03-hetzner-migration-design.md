# Railway → Hetzner VPS Migration Design

**Date**: 2026-03-03
**Status**: Approved
**Motivation**: Cost savings, more control, better performance

## Overview

Migrate Cataclysm from Railway PaaS to a self-managed Hetzner VPS using Docker Compose, Caddy reverse proxy, GitHub Actions CI/CD, and a Prometheus/Grafana monitoring stack.

## VPS Specification

| Spec | Value |
|---|---|
| **Plan** | CX32 (shared vCPU) |
| **CPU** | 3 vCPUs |
| **RAM** | 8 GB |
| **Disk** | 80 GB NVMe |
| **Traffic** | 20 TB/mo |
| **Location** | Ashburn (ash) |
| **OS** | Ubuntu 24.04 LTS |
| **Cost** | €7.49/mo |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Hetzner CX32 (Ashburn)                             │
│                                                       │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │  Caddy    │───▶│ Frontend │    │ Grafana  │       │
│  │  :80/:443 │    │  :3000   │    │  :3001   │       │
│  │           │    └──────────┘    └──────────┘       │
│  │           │    ┌──────────┐    ┌────────────┐     │
│  │           │───▶│ Backend  │    │ Prometheus │     │
│  │           │    │  :8000   │    │  :9090     │     │
│  └──────────┘    └──────────┘    └────────────┘     │
│                   ┌──────────┐    ┌──────────┐       │
│                   │ Postgres │    │  Dozzle  │       │
│                   │  :5432   │    │  :9999   │       │
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

### Routing (Caddy)

- `<IP>/api/*` → `backend:8000`
- `<IP>/grafana/*` → `grafana:3001` (basic auth)
- `<IP>/dozzle/*` → `dozzle:9999` (basic auth)
- `<IP>/*` → `frontend:3000`
- When a domain is added: Caddy auto-provisions Let's Encrypt TLS

### Networking

All services communicate over a Docker Compose internal network by container name:
- Frontend → Backend: `http://backend:8000` (replaces Railway's `backend.railway.internal:8000`)
- Backend → Postgres: `postgresql+asyncpg://user:pass@postgres:5432/cataclysm`

Only Caddy exposes ports 80/443 to the internet. All other services are internal-only.

## Services

### Application Services

| Service | Image | Purpose |
|---|---|---|
| `caddy` | `caddy:2-alpine` | Reverse proxy, TLS termination |
| `frontend` | `ghcr.io/<repo>/frontend:latest` | Next.js 16 App Router |
| `backend` | `ghcr.io/<repo>/backend:latest` | FastAPI + telemetry engine |
| `postgres` | `postgres:16-alpine` | Primary database |

### Monitoring Services

| Service | Image | Purpose |
|---|---|---|
| `prometheus` | `prom/prometheus:latest` | Metrics collection + alerting |
| `grafana` | `grafana/grafana:latest` | Dashboards + visualization |
| `node-exporter` | `prom/node-exporter:latest` | Host metrics (CPU, RAM, disk) |
| `cadvisor` | `gcr.io/cadvisor/cadvisor:latest` | Container resource metrics |
| `dozzle` | `amir20/dozzle:latest` | Docker log viewer |

### FastAPI Metrics

Add `prometheus-fastapi-instrumentator` to backend to expose `/metrics`:
- Request count by method, path, status
- Request duration histogram
- Active request gauge

## Deployment (GitHub Actions)

### Workflow

```
Push to main → GH Actions →
  1. Run lint + tests
  2. Build Docker images (frontend + backend)
  3. Push to ghcr.io
  4. SSH into VPS
  5. docker compose pull
  6. docker compose up -d
  7. Health check (curl /health)
```

### Requirements

- **GitHub Secrets**: `VPS_HOST`, `VPS_SSH_KEY`, `VPS_USER`
- **GHCR auth**: VPS has a `docker login ghcr.io` token stored
- **Build caching**: Docker layer caching in GH Actions for fast builds

### Rollback

```bash
# On VPS, revert to previous image
docker compose pull  # after reverting the tag
docker compose up -d
```

## Database Backups

### Strategy

- **Daily `pg_dump`** at 03:00 UTC via cron
- **Format**: Compressed custom format (`.dump`)
- **Retention**: 7 daily backups, auto-rotated
- **Location**: `/opt/backups/` on VPS
- **Optional future**: Push to Hetzner Storage Box or S3 for offsite

### Backup Script

```bash
#!/bin/bash
BACKUP_DIR=/opt/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker exec postgres pg_dump -U cataclysm -Fc cataclysm > "$BACKUP_DIR/cataclysm_$TIMESTAMP.dump"
# Keep only last 7 backups
ls -t "$BACKUP_DIR"/cataclysm_*.dump | tail -n +8 | xargs -r rm
```

### Restore

```bash
docker exec -i postgres pg_restore -U cataclysm -d cataclysm --clean < /opt/backups/cataclysm_YYYYMMDD.dump
```

## Monitoring & Alerting

### Dashboards (Grafana)

1. **Host Overview**: CPU, RAM, disk usage, network I/O (via Node Exporter)
2. **Container Overview**: Per-service CPU, RAM, restarts (via cAdvisor)
3. **Application**: Request rate, latency p50/p95/p99, error rate (via FastAPI metrics)
4. **PostgreSQL**: Connections, query duration (via pg_stat_statements if enabled)

### Alert Rules (Prometheus Alertmanager)

| Alert | Condition | Severity |
|---|---|---|
| Service Down | `/health` fails for 2min | Critical |
| High CPU | >85% for 5min | Warning |
| High Memory | >85% for 5min | Warning |
| Disk Nearly Full | >85% used | Critical |
| High Error Rate | >5% 5xx responses for 5min | Warning |
| DB Connection Failure | health check db != "ok" | Critical |
| Container Restart | restart count increases | Warning |

### Alert Channels

Configure Alertmanager to send to email and/or Telegram/Discord (user's choice).

## Environment Variables

### Backend

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://cataclysm:${DB_PASSWORD}@postgres:5432/cataclysm` |
| `ANTHROPIC_API_KEY` | (from `.env`, not in repo) |
| `NEXTAUTH_SECRET` | (from `.env`, not in repo) |
| `CORS_ORIGINS` | `["http://<VPS_IP>"]` (update when domain added) |
| `PORT` | `8000` |

### Frontend

| Variable | Value |
|---|---|
| `BACKEND_URL` | `http://backend:8000` |
| `NEXTAUTH_SECRET` | (same as backend) |
| `NEXTAUTH_URL` | `http://<VPS_IP>` (update when domain added) |
| `GOOGLE_CLIENT_ID` | (from `.env`) |
| `GOOGLE_CLIENT_SECRET` | (from `.env`) |
| `AUTH_TRUST_HOST` | `true` |

## Security

- **SSH key-only auth** (disable password login)
- **UFW firewall**: Allow only 22 (SSH), 80, 443
- **Docker secrets** via `.env` file (not checked into git)
- **Caddy basic auth** on Grafana and Dozzle endpoints
- **Non-root containers** (existing Dockerfiles already use `appuser`)
- **Fail2Ban** for SSH brute-force protection

## Files to Create/Modify

### New Files

| File | Purpose |
|---|---|
| `docker-compose.prod.yml` | Production compose with all services |
| `Caddyfile` | Reverse proxy routing config |
| `.github/workflows/deploy.yml` | CI/CD pipeline |
| `monitoring/prometheus.yml` | Prometheus scrape config |
| `monitoring/alertmanager.yml` | Alert rules + notification channels |
| `monitoring/grafana/provisioning/` | Auto-provisioned dashboards + datasources |
| `scripts/pg_backup.sh` | Database backup script |
| `scripts/setup-server.sh` | VPS initial setup script |

### Modified Files

| File | Change |
|---|---|
| `docs/deployment.md` | Updated for Hetzner deployment |
| `backend/requirements.txt` or `pyproject.toml` | Add `prometheus-fastapi-instrumentator` |
| `backend/api/main.py` | Add Prometheus middleware |

### No Changes Required

- All application code (`cataclysm/`, `frontend/src/`, `backend/api/`)
- Existing Dockerfiles (reused as-is)
- Database schema / migrations
- Tests

## Migration Steps (High-Level)

1. Provision Hetzner CX32 in Ashburn
2. Run server setup script (Docker, UFW, fail2ban, dirs)
3. Create all config files (compose, Caddy, Prometheus, GH Actions)
4. Add Prometheus middleware to FastAPI
5. Export Railway PostgreSQL data
6. Import data into VPS PostgreSQL
7. Deploy via GitHub Actions
8. Verify everything works
9. Update DNS / share new URL
10. Decommission Railway
