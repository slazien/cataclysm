# Comparison Results + Share Card Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the session share card (PNG) to a Spotify Wrapped identity-focused style, and replace the overwhelming comparison results with a two-tier summary + expandable deep dive.

**Architecture:** Identity label system shared between both features. Share card is a Canvas rewrite in `shareCardRenderer.ts`. Comparison gets new backend fields (speed traces, skill dimensions, AI verdict) and a two-tier frontend (summary card collapses into deep dive). New `POST /api/sharing/{token}/ai-comparison` endpoint generates cached AI narrative via Haiku.

**Tech Stack:** Canvas API (share card), D3 + Canvas (charts), FastAPI + Claude Haiku (AI endpoints), Pydantic (schemas), SVG RadarChart (skill comparison), existing design tokens from `design-tokens.ts`.

---

## Task 1: Identity Label System

Adds `getIdentityLabel()` to `skillDimensions.ts` — a pure function mapping skill dimensions to personality labels.

**Files:**
- Modify: `frontend/src/lib/skillDimensions.ts` (add after line 52)
- Create: `frontend/src/lib/__tests__/skillDimensions.test.ts`

**Step 1: Write the test**

```typescript
// frontend/src/lib/__tests__/skillDimensions.test.ts
import { getIdentityLabel, computeSkillDimensions } from '../skillDimensions';

describe('getIdentityLabel', () => {
  it('returns braking label when braking is highest', () => {
    const dims = { braking: 90, trailBraking: 60, throttle: 50, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['LATE BRAKER', 'BRAKE BOSS']).toContain(label);
  });

  it('returns trail braking label when trailBraking is highest', () => {
    const dims = { braking: 50, trailBraking: 95, throttle: 60, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['TRAIL WIZARD', 'SMOOTH OPERATOR']).toContain(label);
  });

  it('returns throttle label when throttle is highest', () => {
    const dims = { braking: 50, trailBraking: 60, throttle: 92, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['THROTTLE KING', 'POWER PLAYER']).toContain(label);
  });

  it('returns line label when line is highest', () => {
    const dims = { braking: 50, trailBraking: 60, throttle: 55, line: 95 };
    const label = getIdentityLabel(dims);
    expect(['LINE MASTER', 'APEX HUNTER']).toContain(label);
  });

  it('returns balanced label when all within 10pts', () => {
    const dims = { braking: 75, trailBraking: 80, throttle: 78, line: 72 };
    const label = getIdentityLabel(dims);
    expect(['COMPLETE DRIVER', 'WELL ROUNDED']).toContain(label);
  });

  it('returns fallback for null input', () => {
    expect(getIdentityLabel(null)).toBe('TRACK WARRIOR');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest --testPathPattern skillDimensions --no-coverage`
Expected: FAIL — `getIdentityLabel` is not exported

**Step 3: Implement `getIdentityLabel`**

Add to `frontend/src/lib/skillDimensions.ts` after the `dimensionsToArray` function (after line 52):

```typescript
const IDENTITY_LABELS: Record<string, string[]> = {
  braking: ['LATE BRAKER', 'BRAKE BOSS'],
  trailBraking: ['TRAIL WIZARD', 'SMOOTH OPERATOR'],
  throttle: ['THROTTLE KING', 'POWER PLAYER'],
  line: ['LINE MASTER', 'APEX HUNTER'],
  balanced: ['COMPLETE DRIVER', 'WELL ROUNDED'],
};

/** Map skill dimensions to an identity label for share cards. */
export function getIdentityLabel(dims: SkillDimensions | null): string {
  if (!dims) return 'TRACK WARRIOR';

  const entries: [string, number][] = [
    ['braking', dims.braking],
    ['trailBraking', dims.trailBraking],
    ['throttle', dims.throttle],
    ['line', dims.line],
  ];
  const max = Math.max(...entries.map(([, v]) => v));
  const min = Math.min(...entries.map(([, v]) => v));

  // If all dimensions within 10 points, driver is balanced
  const key = max - min <= 10
    ? 'balanced'
    : entries.find(([, v]) => v === max)![0];

  const pool = IDENTITY_LABELS[key];
  // Deterministic pick based on dimension values (not random, so same data = same label)
  const hash = Math.round(dims.braking + dims.throttle * 3 + dims.line * 7);
  return pool[hash % pool.length];
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest --testPathPattern skillDimensions --no-coverage`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/lib/skillDimensions.ts frontend/src/lib/__tests__/skillDimensions.test.ts
git commit -m "feat: add identity label system for share cards and comparison"
```

---

## Task 2: Share Card Renderer Rewrite

Complete rewrite of `shareCardRenderer.ts` with identity-focused Spotify Wrapped layout.

**Files:**
- Rewrite: `frontend/src/lib/shareCardRenderer.ts`
- Modify: `frontend/src/hooks/useShareCard.ts` (pass identity label)

**Step 1: Update `ShareCardData` interface**

In `frontend/src/lib/shareCardRenderer.ts`, replace the `ShareCardData` interface (lines 3-15) to add `identityLabel`:

```typescript
export interface ShareCardData {
  trackName: string;
  sessionDate: string;
  bestLapTime: number | null;
  sessionScore: number | null;
  nLaps: number;
  consistencyScore: number | null;
  identityLabel: string;          // NEW — e.g. "SMOOTH OPERATOR"
  gpsCoords?: { lat: number[]; lon: number[] };
  heroStat?: string;
  consistencyLabel?: string;
  cornersGraded?: string;
  improvement?: string;
  topInsight?: string;
}
```

**Step 2: Rewrite `renderSessionCard`**

Replace the entire `renderSessionCard` function (lines 97-242) and helper functions with the new identity-focused layout. The layout order is:

1. Dark gradient background with subtle grain
2. Track name + date at top (28px)
3. Track outline as decorative glow (blurred, 15% opacity)
4. Identity label (96px bold, centered)
5. Score ring (r=100, thick arc stroke with glow)
6. Best lap time (48px)
7. Stat pills (laps, consistency) as frosted-glass rounded rects
8. Footer CTA ("cataclysm.app")

Key canvas patterns to use (from existing code):
- `ctx.roundRect(x, y, w, h, r)` for pill shapes (already used in current code)
- `drawTrackOutline` function exists but needs blur + lower opacity
- `drawScoreRing` function exists but needs larger radius and glow
- Font: `Barlow Semi Condensed` for display, `JetBrains Mono` for numbers (from `design-tokens.ts`)

Full implementation code:

```typescript
import { formatLapTime } from './formatters';

export interface ShareCardData {
  trackName: string;
  sessionDate: string;
  bestLapTime: number | null;
  sessionScore: number | null;
  nLaps: number;
  consistencyScore: number | null;
  identityLabel: string;
  gpsCoords?: { lat: number[]; lon: number[] };
}

const CARD_W = 1080;
const CARD_H = 1920;
const ACCENT = '#6366f1';
const ACCENT_GLOW = 'rgba(99, 102, 241, 0.4)';

function drawBackground(ctx: CanvasRenderingContext2D): void {
  const grad = ctx.createLinearGradient(0, 0, 0, CARD_H);
  grad.addColorStop(0, '#0a0a1a');
  grad.addColorStop(0.5, '#111128');
  grad.addColorStop(1, '#1a1a2e');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, CARD_W, CARD_H);

  // Subtle grain texture (random noise dots at 3% opacity)
  ctx.globalAlpha = 0.03;
  for (let i = 0; i < 8000; i++) {
    const x = Math.random() * CARD_W;
    const y = Math.random() * CARD_H;
    ctx.fillStyle = Math.random() > 0.5 ? '#fff' : '#000';
    ctx.fillRect(x, y, 1, 1);
  }
  ctx.globalAlpha = 1;
}

function drawTrackGlow(
  ctx: CanvasRenderingContext2D,
  coords: { lat: number[]; lon: number[] },
): void {
  const { lat, lon } = coords;
  if (lat.length < 10) return;

  const minLat = Math.min(...lat), maxLat = Math.max(...lat);
  const minLon = Math.min(...lon), maxLon = Math.max(...lon);
  const rangeX = maxLon - minLon || 1e-6;
  const rangeY = maxLat - minLat || 1e-6;
  const size = 500; // fit within this box
  const scale = size / Math.max(rangeX, rangeY);
  const cx = CARD_W / 2;
  const cy = 650; // center of track glow area

  ctx.save();
  ctx.globalAlpha = 0.12;
  ctx.strokeStyle = ACCENT;
  ctx.lineWidth = 6;
  ctx.shadowColor = ACCENT_GLOW;
  ctx.shadowBlur = 40;
  ctx.beginPath();
  for (let i = 0; i < lat.length; i++) {
    const x = cx + (lon[i] - (minLon + maxLon) / 2) * scale;
    const y = cy - (lat[i] - (minLat + maxLat) / 2) * scale;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.globalAlpha = 1;
  ctx.restore();
}

function drawScoreRing(
  ctx: CanvasRenderingContext2D,
  score: number,
  cx: number,
  cy: number,
): void {
  const r = 100;
  const lineW = 14;
  const startAngle = -Math.PI / 2;
  const endAngle = startAngle + (2 * Math.PI * Math.min(score, 10)) / 10;

  // Background ring
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, 2 * Math.PI);
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.lineWidth = lineW;
  ctx.stroke();

  // Score arc with glow
  ctx.save();
  ctx.shadowColor = ACCENT_GLOW;
  ctx.shadowBlur = 20;
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, endAngle);
  ctx.strokeStyle = ACCENT;
  ctx.lineWidth = lineW;
  ctx.lineCap = 'round';
  ctx.stroke();
  ctx.restore();

  // Score text inside ring
  ctx.fillStyle = '#fff';
  ctx.font = "bold 64px 'Barlow Semi Condensed', sans-serif";
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(score.toFixed(1), cx, cy - 8);
  ctx.font = "24px 'Barlow Semi Condensed', sans-serif";
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.fillText('/ 10', cx, cy + 32);
}

function drawStatPill(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  value: string,
  label: string,
): void {
  const w = 180;
  const h = 90;
  // Frosted glass background
  ctx.fillStyle = 'rgba(255,255,255,0.06)';
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(x - w / 2, y, w, h, 16);
  ctx.fill();
  ctx.stroke();

  // Value
  ctx.fillStyle = '#fff';
  ctx.font = "bold 32px 'JetBrains Mono', monospace";
  ctx.textAlign = 'center';
  ctx.fillText(value, x, y + 36);
  // Label
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.font = "18px 'Barlow Semi Condensed', sans-serif";
  ctx.fillText(label, x, y + 68);
}

export function renderSessionCard(
  canvas: HTMLCanvasElement,
  data: ShareCardData,
): void {
  canvas.width = CARD_W;
  canvas.height = CARD_H;
  const ctx = canvas.getContext('2d')!;

  // 1. Background + grain
  drawBackground(ctx);

  // 2. Track name + date at top
  let y = 100;
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(255,255,255,0.7)';
  ctx.font = "28px 'Barlow Semi Condensed', sans-serif";
  ctx.fillText(data.trackName, CARD_W / 2, y);
  y += 40;
  ctx.fillStyle = 'rgba(255,255,255,0.4)';
  ctx.font = "22px 'Barlow Semi Condensed', sans-serif";
  ctx.fillText(data.sessionDate, CARD_W / 2, y);

  // 3. Track outline as decorative glow
  if (data.gpsCoords && data.gpsCoords.lat.length > 10) {
    drawTrackGlow(ctx, data.gpsCoords);
  }

  // 4. Identity label
  y = 920;
  ctx.fillStyle = '#fff';
  ctx.font = "bold 96px 'Barlow Semi Condensed', sans-serif";
  ctx.textAlign = 'center';
  ctx.fillText(data.identityLabel, CARD_W / 2, y);

  // Decorative line under label
  ctx.strokeStyle = 'rgba(255,255,255,0.15)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(CARD_W / 2 - 200, y + 20);
  ctx.lineTo(CARD_W / 2 + 200, y + 20);
  ctx.stroke();

  // 5. Score ring
  if (data.sessionScore != null) {
    drawScoreRing(ctx, data.sessionScore, CARD_W / 2, 1100);
  }

  // 6. Best lap time
  y = 1310;
  if (data.bestLapTime != null) {
    ctx.fillStyle = '#fff';
    ctx.font = "bold 56px 'JetBrains Mono', monospace";
    ctx.textAlign = 'center';
    ctx.fillText(formatLapTime(data.bestLapTime), CARD_W / 2, y);
    ctx.fillStyle = 'rgba(255,255,255,0.4)';
    ctx.font = "22px 'Barlow Semi Condensed', sans-serif";
    ctx.fillText('BEST LAP', CARD_W / 2, y + 36);
  }

  // 7. Stat pills
  y = 1440;
  drawStatPill(ctx, CARD_W / 2 - 120, y, String(data.nLaps), 'LAPS');
  if (data.consistencyScore != null) {
    drawStatPill(
      ctx,
      CARD_W / 2 + 120,
      y,
      `${Math.round(data.consistencyScore * 100)}%`,
      'CONSISTENCY',
    );
  }

  // 8. Footer CTA
  y = 1820;
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  ctx.font = "22px 'Barlow Semi Condensed', sans-serif";
  ctx.textAlign = 'center';
  ctx.fillText('─── cataclysm.app ───', CARD_W / 2, y);
}
```

**Step 3: Update `useShareCard.ts` to pass identity label**

In `frontend/src/hooks/useShareCard.ts`, add import of `getIdentityLabel` and `computeSkillDimensions`, compute the identity label from corner grades, and pass it in `ShareCardData`:

```typescript
// Add to imports:
import { getIdentityLabel, computeSkillDimensions } from '@/lib/skillDimensions';

// Inside the useShareCard hook, compute identity label from coaching report:
const identityLabel = useMemo(() => {
  if (!coachingReport?.corner_grades?.length) return 'TRACK WARRIOR';
  const dims = computeSkillDimensions(coachingReport.corner_grades);
  return getIdentityLabel(dims);
}, [coachingReport]);

// Update the ShareCardData construction to include identityLabel:
// Replace heroStat, consistencyLabel, cornersGraded, improvement, topInsight
// with just identityLabel (the new renderer doesn't use those fields)
```

**Step 4: Run tests**

Run: `cd frontend && npx jest --no-coverage`
Expected: PASS (existing tests + new identity label tests)

**Step 5: Commit**

```bash
git add frontend/src/lib/shareCardRenderer.ts frontend/src/hooks/useShareCard.ts
git commit -m "feat: rewrite share card renderer with identity-focused layout"
```

---

## Task 3: Backend — Extend Comparison Response

Add `speed_traces`, `skill_dimensions`, and `ai_verdict` to comparison results.

**Files:**
- Modify: `backend/api/schemas/comparison.py` (add fields to `ComparisonResult`)
- Modify: `backend/api/services/comparison.py` (extract speed traces, compute skill dims, generate verdict)
- Modify: `backend/api/schemas/sharing.py` (update `ShareComparisonResponse`)
- Create: `backend/tests/test_comparison_extended.py`

**Step 1: Write the test**

```python
# backend/tests/test_comparison_extended.py
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from backend.api.services.comparison import compare_sessions


@pytest.fixture
def mock_session_data():
    """Create minimal mock SessionData for comparison."""
    def _make(best_lap_time=90.0, n_corners=5):
        sd = MagicMock()
        sd.processed = MagicMock()
        sd.processed.best_lap = 0
        sd.processed.lap_summaries = [MagicMock(lap_time_s=best_lap_time)]
        sd.processed.corners = [MagicMock() for _ in range(n_corners)]
        sd.weather = None
        sd.coaching_report = None
        # Minimal resampled DataFrame
        import pandas as pd
        import numpy as np
        dist = np.linspace(0, 3000, 100)
        sd.processed.get_resampled_lap.return_value = pd.DataFrame({
            'distance_m': dist,
            'speed_mps': np.full(100, 30.0),
            'lat': np.full(100, 33.5),
            'lon': np.full(100, -86.6),
        })
        return sd
    return _make


@pytest.mark.asyncio
async def test_compare_sessions_has_speed_traces(mock_session_data):
    sd_a = mock_session_data(best_lap_time=88.0)
    sd_b = mock_session_data(best_lap_time=90.0)
    with patch('backend.api.services.comparison.compute_delta') as mock_delta:
        mock_delta.return_value = (
            [0.0] * 100,  # distance_m
            [0.0] * 100,  # delta_time_s
        )
        result = await compare_sessions(sd_a, sd_b)
    assert 'speed_traces' in result
    assert 'a' in result['speed_traces']
    assert 'b' in result['speed_traces']
    assert len(result['speed_traces']['a']['speed_mph']) > 0


@pytest.mark.asyncio
async def test_compare_sessions_has_skill_dimensions(mock_session_data):
    sd_a = mock_session_data()
    sd_b = mock_session_data()
    # Mock coaching reports with corner grades
    sd_a.coaching_report = {
        'corner_grades': [
            {'corner': 1, 'braking': 'A', 'trail_braking': 'B', 'min_speed': 'A', 'throttle': 'B'},
        ]
    }
    sd_b.coaching_report = {
        'corner_grades': [
            {'corner': 1, 'braking': 'C', 'trail_braking': 'C', 'min_speed': 'B', 'throttle': 'C'},
        ]
    }
    with patch('backend.api.services.comparison.compute_delta') as mock_delta:
        mock_delta.return_value = ([0.0] * 100, [0.0] * 100)
        result = await compare_sessions(sd_a, sd_b)
    assert 'skill_dimensions' in result
    assert 'a' in result['skill_dimensions']
```

**Step 2: Update `ComparisonResult` schema**

In `backend/api/schemas/comparison.py`, add after the existing fields:

```python
class SpeedTracePoint(BaseModel):
    distance_m: list[float]
    speed_mph: list[float]

class SkillDimensionSchema(BaseModel):
    braking: float
    trail_braking: float
    throttle: float
    line: float

class ComparisonResult(BaseModel):
    # ... existing fields ...
    speed_traces: dict[str, SpeedTracePoint] | None = None
    skill_dimensions: dict[str, SkillDimensionSchema] | None = None
    ai_verdict: str | None = None
```

**Step 3: Update `compare_sessions()` in `comparison.py`**

After the existing corner_deltas computation, add speed trace extraction and skill dimension computation:

```python
# Speed traces — extract speed vs distance for both best laps
MPS_TO_MPH_FACTOR = MPS_TO_MPH  # already imported
speed_traces = {
    'a': {
        'distance_m': df_a['distance_m'].tolist(),
        'speed_mph': (df_a['speed_mps'] * MPS_TO_MPH_FACTOR).tolist(),
    },
    'b': {
        'distance_m': df_b['distance_m'].tolist(),
        'speed_mph': (df_b['speed_mps'] * MPS_TO_MPH_FACTOR).tolist(),
    },
}

# Skill dimensions — from coaching reports if available
skill_dimensions = None
grades_a = _extract_corner_grades(sd_a)
grades_b = _extract_corner_grades(sd_b)
if grades_a and grades_b:
    skill_dimensions = {
        'a': _compute_skill_dims(grades_a),
        'b': _compute_skill_dims(grades_b),
    }
```

Helper functions to add:

```python
GRADE_SCORES = {'A': 100, 'B': 80, 'C': 60, 'D': 40, 'F': 20}

def _extract_corner_grades(sd: SessionData) -> list[dict] | None:
    """Extract corner grades from coaching report if available."""
    report = getattr(sd, 'coaching_report', None)
    if not report:
        return None
    grades = report.get('corner_grades') if isinstance(report, dict) else None
    return grades if grades else None

def _compute_skill_dims(grades: list[dict]) -> dict[str, float]:
    """Compute average skill dimension scores from corner grades."""
    dims = {'braking': [], 'trail_braking': [], 'throttle': [], 'line': []}
    for g in grades:
        for key, field in [('braking', 'braking'), ('trail_braking', 'trail_braking'),
                           ('throttle', 'throttle'), ('line', 'min_speed')]:
            score = GRADE_SCORES.get(g.get(field, 'C'), 60)
            dims[key].append(score)
    return {k: round(sum(v) / len(v), 1) if v else 60.0 for k, v in dims.items()}
```

**Step 4: Update `ShareComparisonResponse` schema**

In `backend/api/schemas/sharing.py`, add the new optional fields to `ShareComparisonResponse`:

```python
speed_traces: dict | None = None
skill_dimensions: dict | None = None
ai_verdict: str | None = None
```

**Step 5: Update sharing router to pass new fields through**

In `backend/api/routers/sharing.py`, the `POST /{token}/upload` endpoint calls `compare_sessions()` and stores the result. Ensure the new fields are included in the response and stored in `ShareComparisonReport`.

**Step 6: Run tests**

Run: `pytest backend/tests/test_comparison_extended.py -v`
Expected: PASS

Run: `pytest backend/tests/ -v --timeout=30`
Expected: ALL PASS

**Step 7: Quality gates**

```bash
ruff check backend/ && ruff format backend/ && dmypy run -- backend/
```

**Step 8: Commit**

```bash
git add backend/api/schemas/comparison.py backend/api/services/comparison.py \
  backend/api/schemas/sharing.py backend/api/routers/sharing.py \
  backend/tests/test_comparison_extended.py
git commit -m "feat: add speed traces, skill dimensions, AI verdict to comparison"
```

---

## Task 4: Backend — AI Comparison Narrative Endpoint

New endpoint that generates a 3-4 paragraph AI comparison analysis, cached per share token.

**Files:**
- Modify: `backend/api/routers/sharing.py` (add `POST /{token}/ai-comparison`)
- Modify: `backend/api/db/models.py` (add `ai_comparison_text` column to `ShareComparisonReport`)
- Create: `backend/tests/test_ai_comparison.py`

**Step 1: Add DB column**

Add `ai_comparison_text` to `ShareComparisonReport` model in `backend/api/db/models.py`:

```python
ai_comparison_text = Column(Text, nullable=True)
```

Generate an Alembic migration for this:

```bash
cd backend && alembic revision --autogenerate -m "add ai_comparison_text to share_comparison_reports"
alembic upgrade head
```

**Step 2: Write the test**

```python
# backend/tests/test_ai_comparison.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_ai_comparison_returns_cached():
    """If ai_comparison_text already exists, return it without calling Claude."""
    # Test via direct function call, not HTTP endpoint
    from backend.api.routers.sharing import _get_or_generate_ai_comparison

    mock_report = MagicMock()
    mock_report.ai_comparison_text = "Cached comparison text"
    mock_report.comparison_data = {}

    result = await _get_or_generate_ai_comparison(mock_report, MagicMock())
    assert result == "Cached comparison text"


@pytest.mark.asyncio
async def test_ai_comparison_generates_on_miss():
    """If ai_comparison_text is None, generate via Claude and cache."""
    from backend.api.routers.sharing import _get_or_generate_ai_comparison

    mock_report = MagicMock()
    mock_report.ai_comparison_text = None
    mock_report.comparison_data = {
        'session_a_best_lap': 88.5,
        'session_b_best_lap': 90.1,
        'corner_deltas': [{'corner_number': 1, 'speed_diff_mph': 2.3}],
    }
    mock_db = AsyncMock()

    with patch('backend.api.routers.sharing._call_haiku_comparison') as mock_haiku:
        mock_haiku.return_value = "Alex is faster because..."
        result = await _get_or_generate_ai_comparison(mock_report, mock_db)

    assert result == "Alex is faster because..."
    assert mock_report.ai_comparison_text == "Alex is faster because..."
```

**Step 3: Implement the endpoint and helper functions**

In `backend/api/routers/sharing.py`:

```python
@router.post("/{token}/ai-comparison")
async def get_ai_comparison(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str | None]:
    """Generate or retrieve cached AI comparison narrative."""
    report = await _get_comparison_report(db, token)
    if report is None:
        raise HTTPException(status_code=404, detail="No comparison found")

    text = await _get_or_generate_ai_comparison(report, db)
    return {"ai_comparison": text}


async def _get_or_generate_ai_comparison(
    report: ShareComparisonReport,
    db: AsyncSession,
) -> str:
    """Return cached AI comparison or generate via Haiku."""
    if report.ai_comparison_text:
        return report.ai_comparison_text

    text = await _call_haiku_comparison(report.comparison_data)
    report.ai_comparison_text = text
    await db.flush()
    return text


async def _call_haiku_comparison(comparison_data: dict) -> str:
    """Call Claude Haiku to generate comparison narrative."""
    import anthropic

    client = anthropic.AsyncAnthropic()
    prompt = _build_comparison_prompt(comparison_data)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _build_comparison_prompt(data: dict) -> str:
    """Build a prompt for AI comparison narrative."""
    a_time = data.get('session_a_best_lap', 0)
    b_time = data.get('session_b_best_lap', 0)
    corner_deltas = data.get('corner_deltas', [])
    delta = round(b_time - a_time, 3) if a_time and b_time else 0

    corners_str = "\n".join(
        f"  Turn {c['corner_number']}: {'A' if c['speed_diff_mph'] > 0 else 'B'} faster by "
        f"{abs(c['speed_diff_mph']):.1f} mph"
        for c in corner_deltas
    )

    return f"""Compare two drivers' track performance in 3-4 short paragraphs.
Be specific about corner numbers and techniques. Conversational, not robotic.

Driver A best lap: {a_time:.3f}s
Driver B best lap: {b_time:.3f}s
Overall delta: {delta:+.3f}s (positive = A faster)

Corner-by-corner:
{corners_str}

Write the comparison. Address drivers as "Driver A" and "Driver B".
Focus on: where each gains time, technique differences, and one actionable tip for the slower driver."""
```

**Step 4: Run tests**

Run: `pytest backend/tests/test_ai_comparison.py -v`
Expected: PASS

**Step 5: Quality gates**

```bash
ruff check backend/ && ruff format backend/ && dmypy run -- backend/
```

**Step 6: Commit**

```bash
git add backend/api/routers/sharing.py backend/api/db/models.py \
  backend/tests/test_ai_comparison.py
git commit -m "feat: add AI comparison narrative endpoint with caching"
```

---

## Task 5: Frontend — Comparison Summary Card

Replace the inline comparison result in `share/[token]/page.tsx` with a clean summary card.

**Files:**
- Create: `frontend/src/components/comparison/ComparisonSummary.tsx`
- Modify: `frontend/src/app/share/[token]/page.tsx` (replace inline comparison with new component)
- Modify: `frontend/src/lib/types.ts` (extend `ShareComparisonResult` type)

**Step 1: Extend frontend types**

In `frontend/src/lib/types.ts`, update `ShareComparisonResult` (around line 525) to add:

```typescript
export interface ShareComparisonResult {
  // ... existing fields ...
  speed_traces?: {
    a: { distance_m: number[]; speed_mph: number[] };
    b: { distance_m: number[]; speed_mph: number[] };
  };
  skill_dimensions?: {
    a: { braking: number; trail_braking: number; throttle: number; line: number };
    b: { braking: number; trail_braking: number; throttle: number; line: number };
  };
  ai_verdict?: string;
}
```

**Step 2: Create `ComparisonSummary.tsx`**

```tsx
// frontend/src/components/comparison/ComparisonSummary.tsx
'use client';

import { useState } from 'react';
import { Trophy, ChevronDown, ChevronUp } from 'lucide-react';
import { formatLapTime } from '@/lib/formatters';
import { ShareComparisonResult } from '@/lib/types';
import { ComparisonDeepDive } from './ComparisonDeepDive';

interface Props {
  comparison: ShareComparisonResult;
  inviterName: string;
  challengerName: string;
  trackName: string;
  token: string;
}

export function ComparisonSummary({
  comparison,
  inviterName,
  challengerName,
  trackName,
  token,
}: Props) {
  const [showDeepDive, setShowDeepDive] = useState(false);

  const aTime = comparison.session_a_best_lap;
  const bTime = comparison.session_b_best_lap;
  const delta = comparison.delta_s;
  const winnerName = delta > 0 ? inviterName : challengerName;
  const absDelta = Math.abs(delta).toFixed(3);

  // Count corners won by A
  const cornersWonA = comparison.corner_deltas.filter(
    (c) => c.speed_diff_mph > 0,
  ).length;
  const totalCorners = comparison.corner_deltas.length;
  const cornersWonDisplay =
    delta > 0
      ? `${cornersWonA} of ${totalCorners}`
      : `${totalCorners - cornersWonA} of ${totalCorners}`;

  return (
    <div className="space-y-4">
      {/* Winner banner */}
      <div className="rounded-xl bg-gradient-to-r from-emerald-500/20 to-emerald-500/5 border border-emerald-500/30 p-4">
        <div className="flex items-center gap-3">
          <Trophy className="h-6 w-6 text-emerald-400" />
          <div>
            <p className="text-lg font-semibold text-emerald-400">
              {winnerName} wins by {absDelta}s
            </p>
            <p className="text-sm text-[var(--cata-text-secondary)]">
              {trackName}
            </p>
          </div>
        </div>
      </div>

      {/* Stat pills */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-[var(--cata-surface)] p-3 text-center">
          <p className="text-xl font-bold font-mono text-[var(--cata-text-primary)]">
            {absDelta}s
          </p>
          <p className="text-xs text-[var(--cata-text-secondary)]">GAP</p>
        </div>
        <div className="rounded-lg bg-[var(--cata-surface)] p-3 text-center">
          <p className="text-xl font-bold font-mono text-[var(--cata-text-primary)]">
            {cornersWonDisplay}
          </p>
          <p className="text-xs text-[var(--cata-text-secondary)]">
            CORNERS WON
          </p>
        </div>
        <div className="rounded-lg bg-[var(--cata-surface)] p-3 text-center">
          <p className="text-xl font-bold font-mono text-[var(--cata-text-primary)]">
            {aTime ? formatLapTime(aTime) : '--'}
          </p>
          <p className="text-xs text-[var(--cata-text-secondary)]">
            vs {bTime ? formatLapTime(bTime) : '--'}
          </p>
        </div>
      </div>

      {/* AI verdict (1-sentence) */}
      {comparison.ai_verdict && (
        <div className="rounded-lg bg-[var(--cata-surface)] p-4 border-l-2 border-l-[var(--cata-accent)]">
          <p className="text-sm text-[var(--cata-text-secondary)] italic">
            &ldquo;{comparison.ai_verdict}&rdquo;
          </p>
        </div>
      )}

      {/* Deep Dive toggle */}
      <button
        onClick={() => setShowDeepDive(!showDeepDive)}
        className="w-full rounded-lg bg-[var(--cata-accent)] hover:bg-[var(--cata-accent-hover)] text-white py-3 px-4 font-medium flex items-center justify-center gap-2 transition-colors"
      >
        {showDeepDive ? (
          <>
            Hide Deep Dive <ChevronUp className="h-4 w-4" />
          </>
        ) : (
          <>
            Deep Dive <ChevronDown className="h-4 w-4" />
          </>
        )}
      </button>

      {/* Expandable deep dive */}
      {showDeepDive && (
        <ComparisonDeepDive
          comparison={comparison}
          inviterName={inviterName}
          challengerName={challengerName}
          token={token}
        />
      )}
    </div>
  );
}
```

**Step 3: Wire into `share/[token]/page.tsx`**

Replace the inline comparison rendering (around line 104-280) with:

```tsx
import { ComparisonSummary } from '@/components/comparison/ComparisonSummary';

// In the comparison result branch:
<ComparisonSummary
  comparison={comparison}
  inviterName={metadata.inviter_name ?? 'Driver A'}
  challengerName="You"
  trackName={metadata.track_name}
  token={token}
/>
```

**Step 4: Commit**

```bash
git add frontend/src/components/comparison/ComparisonSummary.tsx \
  frontend/src/app/share/\\[token\\]/page.tsx \
  frontend/src/lib/types.ts
git commit -m "feat: add comparison summary card with winner banner and stat pills"
```

---

## Task 6: Frontend — Comparison Deep Dive

The expandable section with delta chart, speed overlay, skill radar, AI narrative, and corner table.

**Files:**
- Create: `frontend/src/components/comparison/ComparisonDeepDive.tsx`
- Create: `frontend/src/components/comparison/SpeedTraceOverlay.tsx`

**Step 1: Create `SpeedTraceOverlay.tsx`**

New D3+Canvas chart showing both drivers' speed vs distance. Follows the same pattern as existing `SpeedTrace.tsx` and `DeltaTimeChart.tsx` (uses `useCanvasChart` hook).

```tsx
// frontend/src/components/comparison/SpeedTraceOverlay.tsx
'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { colors } from '@/lib/design-tokens';

interface Props {
  traceA: { distance_m: number[]; speed_mph: number[] };
  traceB: { distance_m: number[]; speed_mph: number[] };
  labelA: string;
  labelB: string;
  height?: number;
}

export function SpeedTraceOverlay({
  traceA,
  traceB,
  labelA,
  labelB,
  height = 300,
}: Props) {
  const { containerRef, dataCanvasRef, dimensions, getDataCtx } =
    useCanvasChart({ margins: { top: 16, right: 16, bottom: 36, left: 56 } });

  const scales = useMemo(() => {
    if (!dimensions) return null;
    const allDist = [...traceA.distance_m, ...traceB.distance_m];
    const allSpeed = [...traceA.speed_mph, ...traceB.speed_mph];
    return {
      x: d3
        .scaleLinear()
        .domain([Math.min(...allDist), Math.max(...allDist)])
        .range([0, dimensions.innerWidth]),
      y: d3
        .scaleLinear()
        .domain([0, Math.max(...allSpeed) * 1.05])
        .range([dimensions.innerHeight, 0]),
    };
  }, [dimensions, traceA, traceB]);

  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || !scales || !dimensions) return;

    const { innerWidth, innerHeight, margins } = dimensions;
    ctx.clearRect(0, 0, dimensions.width, dimensions.height);
    ctx.save();
    ctx.translate(margins.left, margins.top);

    // Draw both traces
    const drawTrace = (
      dist: number[],
      speed: number[],
      color: string,
    ) => {
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      for (let i = 0; i < dist.length; i++) {
        const x = scales.x(dist[i]);
        const y = scales.y(speed[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };

    drawTrace(traceA.distance_m, traceA.speed_mph, colors.comparison.reference);
    drawTrace(traceB.distance_m, traceB.speed_mph, colors.comparison.compare);

    // Axes
    ctx.strokeStyle = colors.axis;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, innerHeight);
    ctx.lineTo(innerWidth, innerHeight);
    ctx.moveTo(0, 0);
    ctx.lineTo(0, innerHeight);
    ctx.stroke();

    // Y-axis labels
    ctx.fillStyle = colors.text.secondary;
    ctx.font = '11px JetBrains Mono';
    ctx.textAlign = 'right';
    const yTicks = scales.y.ticks(5);
    for (const tick of yTicks) {
      ctx.fillText(`${tick}`, -8, scales.y(tick) + 4);
    }

    // Legend
    ctx.textAlign = 'left';
    ctx.fillStyle = colors.comparison.reference;
    ctx.fillRect(innerWidth - 200, 4, 12, 3);
    ctx.fillText(labelA, innerWidth - 182, 10);
    ctx.fillStyle = colors.comparison.compare;
    ctx.fillRect(innerWidth - 200, 20, 12, 3);
    ctx.fillText(labelB, innerWidth - 182, 26);

    ctx.restore();
  }, [scales, dimensions, traceA, traceB, labelA, labelB, getDataCtx]);

  return (
    <div ref={containerRef} style={{ height }} className="w-full">
      <canvas ref={dataCanvasRef} className="w-full h-full" />
    </div>
  );
}
```

**Step 2: Create `ComparisonDeepDive.tsx`**

```tsx
// frontend/src/components/comparison/ComparisonDeepDive.tsx
'use client';

import { useEffect, useState } from 'react';
import { ShareComparisonResult } from '@/lib/types';
import { DeltaTimeChart } from './DeltaTimeChart';
import { SpeedTraceOverlay } from './SpeedTraceOverlay';
import { RadarChart } from '@/components/shared/RadarChart';
import { SKILL_AXES } from '@/lib/skillDimensions';
import { CornerScorecard } from './CornerScorecard';
import { colors } from '@/lib/design-tokens';

interface Props {
  comparison: ShareComparisonResult;
  inviterName: string;
  challengerName: string;
  token: string;
}

export function ComparisonDeepDive({
  comparison,
  inviterName,
  challengerName,
  token,
}: Props) {
  const [aiNarrative, setAiNarrative] = useState<string | null>(null);
  const [loadingNarrative, setLoadingNarrative] = useState(false);

  // Fetch AI narrative on mount
  useEffect(() => {
    let cancelled = false;
    setLoadingNarrative(true);
    fetch(`/api/sharing/${token}/ai-comparison`, { method: 'POST' })
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setAiNarrative(data.ai_comparison);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingNarrative(false);
      });
    return () => { cancelled = true; };
  }, [token]);

  // Skill radar datasets
  const radarDatasets = comparison.skill_dimensions
    ? [
        {
          label: inviterName,
          values: [
            comparison.skill_dimensions.a.braking,
            comparison.skill_dimensions.a.trail_braking,
            comparison.skill_dimensions.a.throttle,
            comparison.skill_dimensions.a.line,
          ],
          color: colors.comparison.reference,
          fillOpacity: 0.2,
          strokeOpacity: 0.8,
        },
        {
          label: challengerName,
          values: [
            comparison.skill_dimensions.b.braking,
            comparison.skill_dimensions.b.trail_braking,
            comparison.skill_dimensions.b.throttle,
            comparison.skill_dimensions.b.line,
          ],
          color: colors.comparison.compare,
          fillOpacity: 0.15,
          strokeOpacity: 0.6,
        },
      ]
    : null;

  return (
    <div className="space-y-6 pt-2">
      {/* Section 1: Delta-T Chart */}
      <section>
        <h3 className="text-sm font-medium text-[var(--cata-text-secondary)] mb-2">
          TIME DELTA
        </h3>
        <DeltaTimeChart
          distanceM={comparison.distance_m}
          deltaTimeS={comparison.delta_time_s}
        />
      </section>

      {/* Section 2: Speed Trace Overlay */}
      {comparison.speed_traces && (
        <section>
          <h3 className="text-sm font-medium text-[var(--cata-text-secondary)] mb-2">
            SPEED COMPARISON
          </h3>
          <SpeedTraceOverlay
            traceA={comparison.speed_traces.a}
            traceB={comparison.speed_traces.b}
            labelA={inviterName}
            labelB={challengerName}
          />
        </section>
      )}

      {/* Section 3: Skill Radar */}
      {radarDatasets && (
        <section>
          <h3 className="text-sm font-medium text-[var(--cata-text-secondary)] mb-2">
            SKILL COMPARISON
          </h3>
          <div className="flex justify-center">
            <RadarChart
              axes={SKILL_AXES}
              datasets={radarDatasets}
              size={280}
            />
          </div>
        </section>
      )}

      {/* Section 4: AI Narrative */}
      <section>
        <h3 className="text-sm font-medium text-[var(--cata-text-secondary)] mb-2">
          AI COACH ANALYSIS
        </h3>
        {loadingNarrative ? (
          <div className="rounded-lg bg-[var(--cata-surface)] p-4 animate-pulse">
            <div className="h-4 bg-[var(--cata-surface-hover)] rounded w-3/4 mb-2" />
            <div className="h-4 bg-[var(--cata-surface-hover)] rounded w-1/2" />
          </div>
        ) : aiNarrative ? (
          <div className="rounded-lg bg-[var(--cata-surface)] p-4 space-y-3">
            {aiNarrative.split('\n\n').map((para, i) => (
              <p
                key={i}
                className="text-sm text-[var(--cata-text-secondary)] leading-relaxed"
              >
                {para}
              </p>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--cata-text-tertiary)]">
            AI analysis unavailable
          </p>
        )}
      </section>

      {/* Section 5: Corner Table (existing component) */}
      <section>
        <h3 className="text-sm font-medium text-[var(--cata-text-secondary)] mb-2">
          CORNER BREAKDOWN
        </h3>
        <CornerScorecard
          cornerDeltas={comparison.corner_deltas}
          onCornerSelect={() => {}}
          selectedCorner={null}
        />
      </section>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/comparison/ComparisonDeepDive.tsx \
  frontend/src/components/comparison/SpeedTraceOverlay.tsx
git commit -m "feat: add comparison deep dive with speed overlay, radar, AI narrative"
```

---

## Task 7: Integration Testing & QA

Wire everything together, run full test suites, and QA via Playwright.

**Files:**
- All modified files from Tasks 1-6

**Step 1: Run backend tests**

```bash
source .venv/bin/activate
pytest tests/ backend/tests/ -v --timeout=60
```
Expected: ALL PASS

**Step 2: Run frontend tests**

```bash
cd frontend && npx jest --no-coverage
```
Expected: ALL PASS

**Step 3: Quality gates**

```bash
ruff check cataclysm/ backend/ && ruff format cataclysm/ backend/
dmypy run -- cataclysm/ backend/
cd frontend && npx tsc --noEmit
```
Expected: ZERO errors

**Step 4: Visual QA via Playwright**

Test the share card:
1. Navigate to dashboard, open a session
2. Click Share button → verify new PNG card renders with identity label, score ring, track/date at top
3. Download and inspect the PNG

Test the comparison flow:
1. Create a share link from a session
2. Open share link in incognito (unauthenticated)
3. Upload a CSV → verify summary card (winner banner, stat pills, AI verdict)
4. Click "Deep Dive" → verify all 5 sections expand (delta chart, speed trace, radar, AI narrative, corner table)
5. Click "Hide Deep Dive" → verify collapse

Test mobile (Pixel 7 + iPhone 14):
6. Repeat steps 2-5 on mobile viewport
7. Verify stat pills stack properly, charts are readable, deep dive scrolls

**Step 5: Code review**

Dispatch `superpowers:code-reviewer` agent on all changed files.

**Step 6: Final commit and merge**

```bash
git checkout main && git merge --no-ff social-qa-testing
git push origin main
```

---

## Summary of All Files

### New Files
| File | Purpose |
|---|---|
| `frontend/src/lib/__tests__/skillDimensions.test.ts` | Identity label tests |
| `frontend/src/components/comparison/ComparisonSummary.tsx` | Tier 1 summary card |
| `frontend/src/components/comparison/ComparisonDeepDive.tsx` | Tier 2 expandable deep dive |
| `frontend/src/components/comparison/SpeedTraceOverlay.tsx` | D3 dual-line speed chart |
| `backend/tests/test_comparison_extended.py` | Backend comparison extension tests |
| `backend/tests/test_ai_comparison.py` | AI comparison endpoint tests |

### Modified Files
| File | Change |
|---|---|
| `frontend/src/lib/skillDimensions.ts` | Add `getIdentityLabel()` |
| `frontend/src/lib/shareCardRenderer.ts` | Complete rewrite — identity layout |
| `frontend/src/hooks/useShareCard.ts` | Pass identity label |
| `frontend/src/lib/types.ts` | Extend `ShareComparisonResult` |
| `frontend/src/app/share/[token]/page.tsx` | Use `ComparisonSummary` |
| `backend/api/schemas/comparison.py` | Add speed_traces, skill_dimensions, ai_verdict |
| `backend/api/schemas/sharing.py` | Extend response model |
| `backend/api/services/comparison.py` | Extract speed traces, skill dims |
| `backend/api/routers/sharing.py` | Add AI comparison endpoint |
| `backend/api/db/models.py` | Add ai_comparison_text column |
