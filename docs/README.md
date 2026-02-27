# Cataclysm Documentation

**AI-Powered Motorsport Telemetry Analysis & Coaching Platform**

Cataclysm ingests RaceChrono CSV v3 exports, processes them in the distance domain, detects corners, and generates AI coaching reports via the Anthropic Claude API.

## Documentation Index

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System architecture, component diagrams, data flow |
| [Data Pipeline](data-pipeline.md) | Core engine: parsing, resampling, corner detection, coaching |
| [API Reference](api-reference.md) | Complete FastAPI endpoint reference (REST API) |
| [Data Models](data-models.md) | All dataclasses, Pydantic schemas, and TypeScript types |
| [Frontend Guide](frontend-guide.md) | Next.js frontend architecture, components, state management |
| [Developer Guide](developer-guide.md) | Setup, testing, linting, contributing |
| [Deployment Guide](deployment.md) | Railway deployment, Docker, CI/CD |
| [User Guide](user-guide.md) | End-user guide for track day drivers |

## Quick Links

- **Backend API**: `http://localhost:8000` (dev) / `https://backend-production-4c97.up.railway.app` (prod)
- **Frontend**: `http://localhost:3000` (dev) / `https://cataclysm.up.railway.app` (prod)
- **API Docs (Swagger)**: `http://localhost:8000/docs`

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Core Engine | Python 3.11+, NumPy, SciPy, Pandas |
| Backend API | FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic |
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind 4, D3.js |
| AI Coaching | Anthropic Claude API (Haiku 4.5) |
| Auth | NextAuth.js v5, Google OAuth |
| State | Zustand (UI) + TanStack Query (API cache) |
| Deployment | Railway (auto-deploy from `main` branch) |
| CI/CD | GitHub Actions |
