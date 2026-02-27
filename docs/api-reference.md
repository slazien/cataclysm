# API Reference

Base URL: `http://localhost:8000` (dev) / `https://backend-production-4c97.up.railway.app` (prod)

Interactive Swagger UI: `GET /docs`

## Authentication

Most endpoints require a valid NextAuth.js v5 JWE session token, sent via:
1. `Authorization: Bearer <token>` header
2. `__Secure-authjs.session-token` cookie (production HTTPS)
3. `authjs.session-token` cookie (development)

Unauthenticated requests return `401 Unauthorized`.

Set `DEV_AUTH_BYPASS=true` in backend environment to skip auth (QA mode).

---

## Health

### `GET /health`

Health check endpoint. No authentication required.

**Response**: `200 OK`
```json
{ "status": "ok" }
```

---

## Auth (`/api/auth`)

### `GET /api/auth/me`

Get the authenticated user's profile. Creates user record on first login.

**Auth**: Required

**Response** (`200`):
```json
{
  "id": "user-uuid",
  "email": "driver@example.com",
  "name": "Track Driver",
  "avatar_url": "https://...",
  "skill_level": "intermediate",
  "created_at": "2026-01-15T10:30:00Z"
}
```

---

## Sessions (`/api/sessions`)

### `POST /api/sessions/upload`

Upload one or more RaceChrono CSV v3 files. Triggers background tasks for weather lookup and coaching report generation.

**Auth**: Required

**Request**: `multipart/form-data` with field `files` (one or more `.csv` files)

**Response** (`200`):
```json
{
  "session_ids": ["abc123", "def456"],
  "message": "Processed 2 session(s)"
}
```

### `GET /api/sessions`

List all sessions for the authenticated user.

**Auth**: Required

**Response** (`200`):
```json
{
  "items": [
    {
      "session_id": "abc123",
      "track_name": "Barber Motorsports Park",
      "session_date": "2026-02-15",
      "n_laps": 18,
      "n_clean_laps": 15,
      "best_lap_time_s": 92.45,
      "top3_avg_time_s": 93.12,
      "avg_lap_time_s": 95.67,
      "consistency_score": 82.5,
      "session_score": 78.0,
      "gps_quality_score": 0.92,
      "gps_quality_grade": "A",
      "tire_model": "RE-71RS",
      "compound_category": "super_200tw",
      "equipment_profile_name": "Track Setup",
      "weather_temp_c": 24.0,
      "weather_condition": "Clear",
      "weather_humidity_pct": 45,
      "weather_wind_kmh": 12,
      "weather_precipitation_mm": 0
    }
  ],
  "total": 1
}
```

### `GET /api/sessions/{session_id}`

Get detailed session summary.

**Auth**: Required

**Response** (`200`): Same schema as individual item in session list.

### `GET /api/sessions/{session_id}/laps`

Get lap summaries for a session.

**Auth**: Required

**Response** (`200`):
```json
[
  {
    "lap_number": 3,
    "lap_time_s": 93.21,
    "is_clean": true,
    "lap_distance_m": 3662.4,
    "max_speed_mps": 58.3
  }
]
```

### `GET /api/sessions/{session_id}/laps/{lap_number}/data`

Get telemetry data for a specific lap. All arrays are aligned by distance (0.7m intervals).

**Auth**: Required

**Response** (`200`):
```json
{
  "lap_number": 3,
  "distance_m": [0.0, 0.7, 1.4, ...],
  "speed_mph": [45.2, 45.5, 45.8, ...],
  "lat": [33.5123, 33.5124, ...],
  "lon": [-86.6234, -86.6235, ...],
  "heading_deg": [180.0, 180.5, ...],
  "lateral_g": [0.01, 0.02, ...],
  "longitudinal_g": [-0.3, -0.25, ...],
  "lap_time_s": [0.0, 0.015, 0.031, ...],
  "altitude_m": [200.0, 200.1, ...]
}
```

### `GET /api/sessions/{session_id}/laps/{lap_number}/tags`

Get tags for a specific lap.

**Auth**: Required

**Response** (`200`):
```json
{ "lap_number": 3, "tags": ["clean", "personal_best"] }
```

### `PUT /api/sessions/{session_id}/laps/{lap_number}/tags`

Set tags for a specific lap.

**Auth**: Required

**Request**:
```json
{ "tags": ["clean", "personal_best"] }
```

### `DELETE /api/sessions/{session_id}`

Delete a session and all associated data.

**Auth**: Required

**Response** (`200`):
```json
{ "message": "Session abc123 deleted" }
```

### `DELETE /api/sessions/all/clear`

Delete all sessions for the authenticated user.

**Auth**: Required

### `GET /api/sessions/{session_id}/compare/{other_id}`

Compare two sessions.

**Auth**: Required

### `GET /api/sessions/{session_id}/weather`

Get weather conditions for the session.

**Auth**: Required

**Response** (`200`):
```json
{
  "session_id": "abc123",
  "weather": {
    "temp_c": 24.0,
    "condition": "Clear",
    "humidity_pct": 45,
    "wind_kmh": 12,
    "precipitation_mm": 0
  }
}
```

### `POST /api/sessions/backfill-weather`

Fetch weather data for all sessions missing it.

**Auth**: Required

**Response** (`200`):
```json
{ "backfilled": 3, "skipped": 5, "failed": 0, "total": 8 }
```

---

## Analysis (`/api/sessions/{session_id}`)

### `GET /api/sessions/{session_id}/corners`

Get detected corners for the best lap.

**Auth**: Required

**Response** (`200`):
```json
{
  "session_id": "abc123",
  "lap_number": 3,
  "corners": [
    {
      "number": 1,
      "entry_distance_m": 245.0,
      "exit_distance_m": 380.0,
      "apex_distance_m": 310.0,
      "min_speed_mph": 52.3,
      "brake_point_m": 195.0,
      "peak_brake_g": -1.15,
      "throttle_commit_m": 345.0,
      "apex_type": "mid"
    }
  ]
}
```

### `GET /api/sessions/{session_id}/corners/all-laps`

Get corners for all clean laps. Returns a dictionary keyed by lap number.

**Auth**: Required

**Response** (`200`):
```json
{
  "session_id": "abc123",
  "all_laps": {
    "3": [ { "number": 1, ... } ],
    "5": [ { "number": 1, ... } ]
  }
}
```

### `GET /api/sessions/{session_id}/consistency`

Get session consistency metrics.

**Auth**: Required

**Response** (`200`):
```json
{
  "session_id": "abc123",
  "data": {
    "lap_consistency": {
      "std_dev_s": 1.23,
      "spread_s": 4.56,
      "consistency_score": 82.5,
      "choppiness_score": 88.0,
      "spread_score": 75.0,
      "jump_score": 84.0,
      "lap_numbers": [3, 4, 5, ...],
      "lap_times_s": [93.2, 94.1, 92.8, ...],
      "consecutive_deltas_s": [0.9, -1.3, ...]
    },
    "corner_consistency": [
      {
        "corner_number": 1,
        "min_speed_std_mph": 2.1,
        "min_speed_range_mph": 6.3,
        "brake_point_std_m": 5.2,
        "throttle_commit_std_m": 8.1,
        "consistency_score": 78.0,
        "lap_numbers": [3, 4, 5],
        "min_speeds_mph": [52.3, 54.1, 51.8]
      }
    ],
    "track_position": {
      "distance_m": [0.0, 0.7, ...],
      "speed_std_mph": [1.2, 1.3, ...],
      "speed_mean_mph": [85.0, 84.5, ...],
      "n_laps": 15
    }
  }
}
```

### `GET /api/sessions/{session_id}/delta?ref={lap}&comp={lap}`

Get time delta between two laps.

**Auth**: Required

**Query Parameters**:
- `ref` (int, required): Reference lap number
- `comp` (int, required): Comparison lap number

**Response** (`200`):
```json
{
  "session_id": "abc123",
  "data": {
    "distance_m": [0.0, 0.7, ...],
    "delta_s": [0.0, 0.001, ...],
    "total_delta_s": 1.45,
    "corner_deltas": [
      { "corner_number": 1, "delta_s": 0.23 }
    ]
  }
}
```

### `GET /api/sessions/{session_id}/gains`

Get time-gain analysis (3-tier).

**Auth**: Required

### `GET /api/sessions/{session_id}/grip`

Get grip analysis from g-force data.

**Auth**: Required

### `GET /api/sessions/{session_id}/gps-quality`

Get GPS quality metrics.

**Auth**: Required

### `GET /api/sessions/{session_id}/ideal-lap`

Get ideal (composite) lap data.

**Auth**: Required

### `GET /api/sessions/{session_id}/optimal-profile`

Get physics-optimal speed profile.

**Auth**: Required

### `GET /api/sessions/{session_id}/charts/linked?laps={lap1}&laps={lap2}`

Get synchronized chart data for multiple laps.

**Auth**: Required

**Query Parameters**:
- `laps` (int[], required): Lap numbers to include

### `GET /api/sessions/{session_id}/sectors`

Get sector analysis (corner-based splits).

**Auth**: Required

### `GET /api/sessions/{session_id}/mini-sectors?n_sectors=20&lap={lap}`

Get equal-distance mini-sector analysis.

**Auth**: Required

**Query Parameters**:
- `n_sectors` (int, default 20): Number of sectors
- `lap` (int, optional): Specific lap number

### `GET /api/sessions/{session_id}/degradation`

Get tire/brake degradation analysis.

**Auth**: Required

---

## Coaching (`/api/coaching`)

### `POST /api/coaching/{session_id}/report`

Generate a coaching report. Returns immediately with `status="generating"`. Poll `GET` endpoint until ready.

**Auth**: Required

**Request**:
```json
{
  "skill_level": "intermediate",
  "focus_areas": ["braking", "corner_exit"]
}
```

**Response** (`200`):
```json
{
  "session_id": "abc123",
  "status": "generating"
}
```

### `GET /api/coaching/{session_id}/report`

Get coaching report. Poll while `status` is `"generating"`.

**Auth**: Required

**Response** (`200`):
```json
{
  "session_id": "abc123",
  "status": "ready",
  "summary": "Strong session with consistent lap times. Key improvement area is T5 braking...",
  "priority_corners": [
    {
      "corner": 5,
      "time_cost_s": 0.45,
      "issue": "Late braking causing missed apex",
      "tip": "Brake at the 200m board, trail brake to apex"
    }
  ],
  "corner_grades": [
    {
      "corner": 1,
      "braking": "B+",
      "trail_braking": "B",
      "min_speed": "A-",
      "throttle": "B+",
      "notes": "Good entry speed, could carry 2mph more through apex"
    }
  ],
  "patterns": [
    "Consistently late braking into T5",
    "Strong throttle application on corner exits"
  ],
  "drills": [
    "Practice threshold braking at T5: brake at 200m board for 3 consecutive laps",
    "Focus on trail braking into T2: maintain light brake pressure past turn-in"
  ],
  "validation_failed": false,
  "validation_violations": []
}
```

### `GET /api/coaching/{session_id}/report/pdf`

Download coaching report as PDF.

**Auth**: Required

**Response**: `application/pdf` binary file

### `POST /api/coaching/{session_id}/chat`

Send a follow-up question to the AI coach (HTTP endpoint).

**Auth**: Required

**Request**:
```json
{
  "content": "How can I improve my braking into T5?",
  "context": {}
}
```

**Response** (`200`):
```json
{
  "role": "assistant",
  "content": "Looking at your T5 data, you're currently braking at 180m before the corner..."
}
```

### `WebSocket /api/coaching/{session_id}/chat`

Real-time chat with the AI coach. Requires session cookies for auth.

**Client sends**:
```json
{ "content": "What about T2?" }
```

**Server responds**:
```json
{ "role": "assistant", "content": "For T2, your brake point is..." }
```

---

## Equipment (`/api/equipment`)

### `GET /api/equipment/tires/search?q={query}`

Search the tire database by model name.

**Response** (`200`): Array of `TireSpec` objects.

### `GET /api/equipment/brakes/search?q={query}`

Search brake pad database.

### `GET /api/equipment/reference/tire-sizes`

Get list of standard tire sizes.

### `GET /api/equipment/reference/brake-fluids`

Get list of common brake fluids.

### `POST /api/equipment/weather/lookup`

Lookup weather conditions for a session.

### `POST /api/equipment/profiles`

Create an equipment profile (tires, brakes, suspension).

**Auth**: Required

**Request**:
```json
{
  "name": "Track Setup",
  "tires": {
    "model": "RE-71RS",
    "compound_category": "super_200tw",
    "size": "255/40R17",
    "treadwear_rating": 200,
    "pressure_psi": 32
  },
  "brakes": {
    "compound": "Hawk DTC-60",
    "fluid_type": "Motul RBF 600"
  },
  "suspension": {
    "type": "Coilovers",
    "front_camber_deg": -2.5,
    "rear_camber_deg": -1.8
  }
}
```

**Response** (`201`): Created profile.

### `GET /api/equipment/profiles`

List all equipment profiles.

### `GET /api/equipment/profiles/{profile_id}`

Get a specific profile.

### `PATCH /api/equipment/profiles/{profile_id}`

Update a profile.

### `DELETE /api/equipment/profiles/{profile_id}`

Delete a profile.

### `PUT /api/equipment/{session_id}/equipment`

Assign an equipment profile to a session.

### `GET /api/equipment/{session_id}/equipment`

Get equipment assigned to a session.

---

## Trends (`/api/trends`)

### `GET /api/trends/{track_name}`

Get trend analysis across all sessions at a track. Requires minimum 2 sessions.

**Auth**: Required

**Query Parameters**:
- `include_low_quality` (bool, default false): Include sessions with low GPS quality

### `GET /api/trends/{track_name}/milestones`

Get session milestones (personal bests, records).

**Auth**: Required

---

## Tracks (`/api/tracks`)

### `GET /api/tracks`

List available track data folders. No authentication required.

**Response** (`200`):
```json
[
  { "folder": "barber_motorsports_park", "n_files": 5, "path": "data/session/barber_motorsports_park" }
]
```

### `POST /api/tracks/{folder}/load`

Load sessions from a track data folder. No authentication required.

**Query Parameters**:
- `limit` (int, optional): Maximum sessions to load

---

## Sharing (`/api/sharing`)

### `POST /api/sharing/create`

Create a share link for a session. Links expire after 7 days.

**Auth**: Required

**Request**:
```json
{ "session_id": "abc123" }
```

**Response** (`200`):
```json
{
  "token": "share-token-xyz",
  "url": "https://cataclysm.up.railway.app/share/share-token-xyz",
  "expires_at": "2026-03-06T10:30:00Z"
}
```

### `GET /api/sharing/{token}`

Get share link metadata. No authentication required.

### `POST /api/sharing/{token}/upload`

Upload CSV for anonymous comparison against shared session. No authentication required.

### `GET /api/sharing/{token}/comparison`

Get comparison results. No authentication required.

---

## Leaderboards (`/api/leaderboards`)

### `GET /api/leaderboards/{track}/corners?corner={n}&limit={n}`

Get corner leaderboard rankings.

**Auth**: Required

### `GET /api/leaderboards/{track}/kings`

Get "corner kings" (best at each corner).

**Auth**: Required

### `POST /api/leaderboards/opt-in`

Toggle leaderboard participation.

**Auth**: Required

---

## Achievements (`/api/achievements`)

### `GET /api/achievements`

Get all achievements and unlock status.

**Auth**: Required

### `GET /api/achievements/recent`

Get recently unlocked achievements.

**Auth**: Required

---

## Wrapped (`/api/wrapped`)

### `GET /api/wrapped/{year}`

Get annual recap stats (year-in-review).

**Auth**: Required

---

## Instructor (`/api/instructor`)

All instructor endpoints require `role == "instructor"` on the user record.

### `GET /api/instructor/students`
### `POST /api/instructor/invite`
### `POST /api/instructor/accept/{code}`
### `DELETE /api/instructor/students/{student_id}`
### `GET /api/instructor/students/{student_id}/sessions`
### `GET /api/instructor/students/{student_id}/flags`
### `POST /api/instructor/students/{student_id}/flags`

---

## Organizations (`/api/orgs`)

### `POST /api/orgs` — Create organization (auth required)
### `GET /api/orgs` — List user's organizations (auth required)
### `GET /api/orgs/{slug}` — Get org info (public)
### `GET /api/orgs/{slug}/members` — List members (member access)
### `POST /api/orgs/{slug}/members` — Add member (owner/instructor)
### `DELETE /api/orgs/{slug}/members/{user_id}` — Remove member (owner)
### `POST /api/orgs/{slug}/events` — Create event (owner/instructor)
### `GET /api/orgs/{slug}/events` — List events (member access)
### `DELETE /api/orgs/{slug}/events/{event_id}` — Delete event (owner/instructor)

---

## Error Responses

### `401 Unauthorized`
```json
{ "detail": "Not authenticated" }
```

### `404 Not Found`
```json
{ "detail": "Session not found" }
```

### `422 Unprocessable Entity`
```json
{ "detail": "Invalid CSV format: missing lap_number column" }
```

### `500 Internal Server Error`
```json
{ "detail": "An unexpected error occurred. Please try again." }
```

---

## Middleware

### Cache Control
| Route Pattern | Cache Header |
|---------------|-------------|
| `/api/coaching` | `no-cache` |
| `/api/equipment` | `no-cache` |
| `/api/leaderboards` | `no-cache` |
| `/api/sessions/upload` | `no-cache` |
| `/api/sessions/` (GET) | `max-age=60` |
| `/api/trends` | `max-age=60` |
| `/api/tracks` | `max-age=3600` |
| Default | `no-cache` |

### GZip Compression
Enabled for responses > 1000 bytes.

### CORS
Configured via `CORS_ORIGINS` environment variable (JSON array). All methods and headers allowed. Credentials enabled.
