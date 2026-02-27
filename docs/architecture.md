# System Architecture

## Overview

Cataclysm is a three-tier application: a Python core engine for telemetry processing, a FastAPI backend serving REST APIs, and a Next.js frontend for visualization and interaction.

```mermaid
graph TB
    subgraph "Frontend (Next.js 16)"
        UI[React 19 UI]
        D3[D3.js Charts]
        Zustand[Zustand Stores]
        TQ[TanStack Query]
    end

    subgraph "Backend (FastAPI)"
        API[REST API :8000]
        Auth[NextAuth JWT Validation]
        Pipeline[Pipeline Service]
        Stores[In-Memory Stores]
        BGTasks[Background Tasks]
    end

    subgraph "Core Engine (Python)"
        Parser[parser.py]
        Engine[engine.py]
        Corners[corners.py]
        Coaching[coaching.py]
        Gains[gains.py]
        Physics[velocity_profile.py]
    end

    subgraph "External Services"
        Claude[Anthropic Claude API]
        Google[Google OAuth]
        Weather[Weather API]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL)]
        FS[File System<br/>data/coaching/<br/>data/session/]
    end

    UI --> TQ
    TQ --> API
    UI --> D3
    UI --> Zustand
    API --> Auth
    Auth --> Google
    API --> Pipeline
    API --> Stores
    API --> BGTasks
    Pipeline --> Parser
    Pipeline --> Engine
    Engine --> Corners
    Pipeline --> Gains
    Pipeline --> Physics
    BGTasks --> Coaching
    Coaching --> Claude
    BGTasks --> Weather
    Stores --> PG
    Stores --> FS
```

## Component Architecture

### Core Engine (`cataclysm/`)

The core engine is a pure Python library with no web framework dependencies. All processing converts time-domain GPS telemetry into **distance-domain** data, resampled at 0.7m intervals to match 25Hz GPS resolution.

```mermaid
graph LR
    CSV[RaceChrono CSV v3] --> Parser[parser.py]
    Parser --> Engine[engine.py]
    Engine --> Corners[corners.py]
    Engine --> Delta[delta.py]
    Corners --> Gains[gains.py]
    Corners --> Analysis[corner_analysis.py]
    Corners --> Consistency[consistency.py]
    Engine --> Curvature[curvature.py]
    Curvature --> VelocityProfile[velocity_profile.py]
    VelocityProfile --> OptimalComp[optimal_comparison.py]

    Gains --> Coaching[coaching.py]
    Analysis --> Coaching
    OptimalComp --> Coaching
    Coaching --> Claude[Claude API]
    Claude --> Report[CoachingReport]
```

**Key design decisions:**
- **Distance domain**: All lap data resampled to 0.7m steps (not time-based). This makes corner detection deterministic and lap comparison straightforward.
- **Dataclass-centric**: All structured data uses Python `dataclasses`, not dicts. This enables type checking with mypy.
- **Stateless modules**: Each module accepts structured input and returns structured output. No shared mutable state.

### Backend API (`backend/`)

FastAPI application serving REST endpoints with async PostgreSQL via SQLAlchemy.

```mermaid
graph TB
    subgraph "Routers (13)"
        R1[sessions]
        R2[analysis]
        R3[coaching]
        R4[equipment]
        R5[trends]
        R6[tracks]
        R7[auth]
        R8[sharing]
        R9[leaderboards]
        R10[achievements]
        R11[instructor]
        R12[organizations]
        R13[wrapped]
    end

    subgraph "Services"
        S1[pipeline.py]
        S2[session_store.py]
        S3[coaching_store.py]
        S4[equipment_store.py]
        S5[achievement_engine.py]
        S6[leaderboard_store.py]
        S7[comparison.py]
    end

    subgraph "Dependencies"
        D1[get_current_user]
        D2[get_db]
        D3[get_settings]
    end

    R1 --> S1
    R1 --> S2
    R2 --> S1
    R3 --> S3
    R4 --> S4
    R9 --> S6
    R10 --> S5

    R1 --> D1
    R2 --> D1
    R3 --> D1
    D1 --> D3
```

**Key patterns:**
- **Dependency injection**: `get_current_user()` validates JWT tokens from NextAuth.js v5.
- **Background tasks**: Coaching reports and weather data are fetched asynchronously after upload.
- **Dual storage**: In-memory session store (fast) + PostgreSQL (persistent). Sessions loaded from DB on startup.
- **Response models**: Pydantic schemas for all endpoints, with automatic OpenAPI generation.

### Frontend (`frontend/`)

Next.js 16 App Router with React 19, using Zustand for UI state and TanStack Query for API caching.

```mermaid
graph TB
    subgraph "Pages"
        P1["/ (Dashboard)"]
        P2["/analysis/[id]"]
        P3["/compare/[id]"]
        P4["/share/[token]"]
        P5["/org/[slug]"]
        P6["/instructor"]
    end

    subgraph "Views (ViewRouter)"
        V1[Dashboard]
        V2[Deep Dive]
        V3[Progress]
        V4[Debrief]
    end

    subgraph "State"
        Z1[sessionStore]
        Z2[analysisStore]
        Z3[coachStore]
        Z4[uiStore]
        RQ[TanStack Query Cache]
    end

    subgraph "Components"
        C1[TopBar]
        C2[SessionDrawer]
        C3[CoachPanel]
        C4["D3 Charts (22+)"]
        C5[TrackMap]
    end

    P1 --> V1
    P1 --> V2
    P1 --> V3
    P1 --> V4
    V1 --> C4
    V2 --> C4
    V2 --> C5
    C1 --> Z4
    C2 --> Z1
    C3 --> Z3
    C4 --> Z2
    C4 --> RQ
```

**Key patterns:**
- **SPA after auth**: All analysis happens on `/` with `ViewRouter` switching between 4 views.
- **Cursor sync**: `cursorDistance` in `analysisStore` synchronizes crosshair across all charts.
- **Lazy data loading**: TanStack Query fetches data on demand with 60s stale time.
- **Error boundaries**: `ViewErrorBoundary` and `ChartErrorBoundary` prevent cascading failures.

## Data Flow: CSV Upload to Coaching Report

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant Engine as Core Engine
    participant Claude as Claude API
    participant DB as PostgreSQL

    User->>FE: Upload CSV files
    FE->>API: POST /api/sessions/upload (multipart)
    API->>Engine: parse_racechrono_csv()
    Engine-->>API: ParsedSession
    API->>Engine: process_session()
    Engine-->>API: ProcessedSession (resampled laps)
    API->>DB: Store session + CSV bytes
    API-->>FE: { session_ids: [...] }

    Note over API: Background tasks start
    API->>Claude: Generate coaching report
    API->>API: Fetch weather data

    FE->>API: GET /api/coaching/{id}/report
    API-->>FE: { status: "generating" }

    Note over FE: Poll every 2 seconds

    Claude-->>API: CoachingReport JSON
    API->>DB: Persist report

    FE->>API: GET /api/coaching/{id}/report
    API-->>FE: { status: "ready", summary: "...", corner_grades: [...] }

    User->>FE: Ask follow-up question
    FE->>API: POST /api/coaching/{id}/chat
    API->>Claude: Chat with telemetry context
    Claude-->>API: Response
    API-->>FE: { role: "assistant", content: "..." }
```

## Authentication Flow

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend (Next.js)
    participant NA as NextAuth.js v5
    participant Google as Google OAuth
    participant API as FastAPI Backend

    User->>FE: Click "Sign In"
    FE->>NA: Redirect to /api/auth/signin
    NA->>Google: OAuth redirect
    Google-->>NA: Authorization code
    NA->>Google: Exchange for tokens
    Google-->>NA: Access token + profile
    NA->>NA: Create JWE session token
    NA-->>FE: Set cookie (authjs.session-token)

    FE->>API: GET /api/sessions (cookie attached)
    API->>API: Extract JWE from cookie
    API->>API: Decrypt with HKDF(NEXTAUTH_SECRET)
    API->>API: Validate expiry, extract claims
    API-->>FE: Authenticated response
```

## Database Schema

```mermaid
erDiagram
    User {
        string id PK
        string email UK
        string name
        string avatar_url
        string skill_level
        string role
        boolean leaderboard_opt_in
    }

    Session {
        string session_id PK
        string user_id FK
        string track_name
        datetime session_date
        int n_laps
        float best_lap_time_s
        json snapshot_json
    }

    SessionFile {
        string session_id FK
        string filename
        bytes csv_bytes
    }

    CoachingReport {
        string session_id FK
        string status
        json report_json
    }

    SharedSession {
        string token PK
        string user_id FK
        string session_id FK
        string track_name
        datetime expires_at
    }

    EquipmentProfile {
        string id PK
        string user_id FK
        string name
        json tires
        json brakes
        json suspension
    }

    Organization {
        string id PK
        string name
        string slug UK
    }

    User ||--o{ Session : owns
    Session ||--|| SessionFile : has
    Session ||--o| CoachingReport : generates
    User ||--o{ SharedSession : creates
    User ||--o{ EquipmentProfile : manages
    Organization ||--o{ User : contains
```

## Directory Structure

```
cataclysm/
├── cataclysm/                  # Core Python engine (35+ modules)
│   ├── parser.py               # RaceChrono CSV parsing
│   ├── engine.py               # Distance-domain resampling
│   ├── corners.py              # Corner detection & KPIs
│   ├── coaching.py             # Claude API integration
│   ├── gains.py                # Time-gain estimation
│   ├── consistency.py          # Session consistency metrics
│   ├── velocity_profile.py     # Physics-optimal speed solver
│   ├── track_db.py             # Known track database
│   └── ...
├── backend/                    # FastAPI backend
│   ├── api/
│   │   ├── main.py             # App entry point
│   │   ├── config.py           # Settings (Pydantic)
│   │   ├── dependencies.py     # DI (auth, DB, settings)
│   │   ├── routers/            # 13 API routers
│   │   ├── services/           # Business logic
│   │   ├── schemas/            # Pydantic models
│   │   └── db/                 # SQLAlchemy + Alembic
│   └── tests/                  # Backend tests (18 files)
├── frontend/                   # Next.js 16 frontend
│   ├── src/
│   │   ├── app/                # Pages (App Router)
│   │   ├── components/         # React components
│   │   ├── stores/             # Zustand stores
│   │   ├── hooks/              # Custom hooks
│   │   └── lib/                # API client, types, utils
│   └── package.json
├── tests/                      # Core engine tests (40 files)
├── data/                       # Runtime data (coaching, sessions)
├── docs/                       # Documentation
├── docker-compose.yml          # Local development
├── Dockerfile.backend          # Backend container
├── Dockerfile.frontend         # Frontend container
└── pyproject.toml              # Python project config
```
