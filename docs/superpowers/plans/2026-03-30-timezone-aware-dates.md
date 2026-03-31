# Timezone-Aware Date Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display all session dates/times in the local timezone of the track where the session took place, and normalize `session_date` to ISO 8601 across the API.

**Architecture:** Backend resolves timezone from GPS coords via `timezonefinder`, converts UTC session date to local display string (`session_date_local`), and returns ISO UTC in `session_date`. Frontend displays `session_date_local` for humans, parses `session_date` (ISO) for sorting/grouping.

**Tech Stack:** Python `timezonefinder` + `zoneinfo` (backend), `Intl.DateTimeFormat` (frontend)

---

### Task 1: Update `localize_session_date()` output format

**Files:**
- Modify: `cataclysm/timezone_utils.py:47-93`
- Modify: `tests/test_timezone_utils.py`

- [ ] **Step 1: Update tests for new output format**

In `tests/test_timezone_utils.py`, replace the existing `localize_session_date` tests with ones expecting the new `"Mar 21, 2026 · 8:31 AM EDT"` format:

```python
def test_localize_session_date_utc_to_eastern() -> None:
    """17:32 UTC → 1:32 PM EDT during March (DST)."""
    result = localize_session_date("15/03/2026 17:32", "America/New_York")
    assert result is not None
    assert result == "Mar 15, 2026 · 1:32 PM EDT"


def test_localize_session_date_utc_to_eastern_winter() -> None:
    """17:32 UTC → 12:32 PM EST during January (no DST)."""
    result = localize_session_date("15/01/2026 17:32", "America/New_York")
    assert result is not None
    assert result == "Jan 15, 2026 · 12:32 PM EST"


def test_localize_session_date_utc_to_central() -> None:
    """12:31 UTC → 7:31 AM CDT for Barber (Central time, March DST)."""
    result = localize_session_date("21/03/2026 12:31", "America/Chicago")
    assert result is not None
    assert result == "Mar 21, 2026 · 7:31 AM CDT"


def test_localize_session_date_date_only() -> None:
    """Date-only strings get midnight UTC converted."""
    result = localize_session_date("15/03/2026", "America/New_York")
    assert result is not None
    # Midnight UTC → 8 PM EDT previous day
    assert result == "Mar 14, 2026 · 8:00 PM EDT"


def test_localize_session_date_iso_format() -> None:
    """ISO format input also works."""
    result = localize_session_date("2026-03-15 17:32:00", "America/New_York")
    assert result is not None
    assert result == "Mar 15, 2026 · 1:32 PM EDT"


def test_localize_session_date_invalid_tz() -> None:
    """Invalid timezone → None."""
    assert localize_session_date("15/03/2026 12:00", "Fake/Zone") is None


def test_localize_session_date_bad_date() -> None:
    """Unparseable date → None."""
    assert localize_session_date("not-a-date", "America/New_York") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_timezone_utils.py -v`
Expected: FAIL — old format `"15/03/2026 13:32 EDT"` doesn't match new expected format.

- [ ] **Step 3: Update `localize_session_date()` output format**

In `cataclysm/timezone_utils.py`, replace the final return line (line 93) and update the docstring:

```python
def localize_session_date(
    session_date_utc: str,
    timezone_name: str,
) -> str | None:
    """Convert a UTC session date string to local time.

    Parameters
    ----------
    session_date_utc:
        Date string in one of the RaceChrono formats
        (``"DD/MM/YYYY HH:MM"``) or ISO (``"YYYY-MM-DD HH:MM:SS"``).
    timezone_name:
        IANA timezone name, e.g. ``"America/New_York"``.

    Returns
    -------
    Localized string like ``"Mar 21, 2026 · 8:31 AM EDT"``, or ``None`` on failure.
    """
    try:
        tz = ZoneInfo(timezone_name)
    except (KeyError, Exception):
        return None

    # Parse the UTC date string
    utc_dt: datetime | None = None
    for fmt in [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y,%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]:
        try:
            utc_dt = datetime.strptime(session_date_utc.strip(), fmt).replace(
                tzinfo=ZoneInfo("UTC"),
            )
            break
        except ValueError:
            continue

    if utc_dt is None:
        return None

    local_dt = utc_dt.astimezone(tz)
    abbrev = local_dt.strftime("%Z")  # e.g. "EDT", "EST", "CET"
    # Format: "Mar 21, 2026 · 8:31 AM EDT"
    time_str = local_dt.strftime("%-I:%M %p")  # "8:31 AM" (no leading zero)
    date_str = local_dt.strftime("%b %-d, %Y")  # "Mar 21, 2026"
    return f"{date_str} · {time_str} {abbrev}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_timezone_utils.py -v`
Expected: All PASS.

- [ ] **Step 5: Run quality gates**

Run: `ruff format cataclysm/timezone_utils.py tests/test_timezone_utils.py && ruff check cataclysm/timezone_utils.py tests/test_timezone_utils.py`
Run: `dmypy run -- cataclysm/timezone_utils.py`

- [ ] **Step 6: Commit**

```bash
git add cataclysm/timezone_utils.py tests/test_timezone_utils.py
git commit -m "feat: update localize_session_date output to 'Mar 21, 2026 · 8:31 AM EDT' format"
```

---

### Task 2: Add `resolve_session_timezone()` helper and wire into pipeline

**Files:**
- Modify: `cataclysm/timezone_utils.py`
- Modify: `backend/api/services/pipeline.py`
- Modify: `tests/test_timezone_utils.py`

- [ ] **Step 1: Write test for `resolve_session_timezone()`**

Add to `tests/test_timezone_utils.py`:

```python
import pandas as pd
from cataclysm.timezone_utils import resolve_session_timezone


def test_resolve_session_timezone_from_gps() -> None:
    """Resolves timezone from GPS coordinates in telemetry DataFrame."""
    df = pd.DataFrame({"lat": [32.136, 32.137], "lon": [-81.156, -81.157]})
    tz = resolve_session_timezone(df, track_name=None)
    assert tz == "America/New_York"


def test_resolve_session_timezone_missing_gps_cols() -> None:
    """Returns None when GPS columns are missing."""
    df = pd.DataFrame({"speed": [50, 60]})
    tz = resolve_session_timezone(df, track_name=None)
    assert tz is None


def test_resolve_session_timezone_nan_gps() -> None:
    """Returns None when GPS values are all NaN."""
    df = pd.DataFrame({"lat": [float("nan")], "lon": [float("nan")]})
    tz = resolve_session_timezone(df, track_name=None)
    assert tz is None


def test_resolve_session_timezone_fallback_to_track_db() -> None:
    """Falls back to track_db center coords when GPS is missing."""
    df = pd.DataFrame({"speed": [50]})  # no lat/lon
    tz = resolve_session_timezone(df, track_name="Roebling Road Raceway")
    # Roebling center coords should resolve to Eastern
    assert tz == "America/New_York"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_timezone_utils.py::test_resolve_session_timezone_from_gps -v`
Expected: FAIL — `resolve_session_timezone` not defined.

- [ ] **Step 3: Implement `resolve_session_timezone()`**

Add to `cataclysm/timezone_utils.py`:

```python
from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from timezonefinder import TimezoneFinder

logger = logging.getLogger(__name__)


def resolve_session_timezone(
    df: pd.DataFrame,
    track_name: str | None,
) -> str | None:
    """Resolve IANA timezone from session telemetry GPS or track_db fallback.

    Parameters
    ----------
    df:
        Telemetry DataFrame with optional ``lat``/``lon`` columns.
    track_name:
        Track name for fallback lookup in ``track_db``.

    Returns
    -------
    IANA timezone name (e.g. ``"America/New_York"``) or ``None``.
    """
    # Try GPS from telemetry
    if "lat" in df.columns and "lon" in df.columns:
        lat_series = df["lat"].dropna()
        lon_series = df["lon"].dropna()
        if len(lat_series) > 0 and len(lon_series) > 0:
            lat = float(lat_series.iloc[0])
            lon = float(lon_series.iloc[0])
            if not (math.isnan(lat) or math.isnan(lon)):
                tz = get_timezone_name(lat, lon)
                if tz is not None:
                    return tz

    # Fallback: track_db center coords
    if track_name:
        try:
            from cataclysm.track_db import get_track_info

            info = get_track_info(track_name)
            if info and info.center_lat and info.center_lon:
                return get_timezone_name(info.center_lat, info.center_lon)
        except Exception:
            logger.debug("track_db fallback failed for %s", track_name, exc_info=True)

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_timezone_utils.py -v`
Expected: All PASS.

- [ ] **Step 5: Verify `track_db.get_track_info` returns center coords**

Check that `get_track_info("Roebling Road Raceway")` returns an object with `center_lat` and `center_lon`. If the attribute names differ (e.g., `lat`/`lon` or `center`), adjust the code accordingly. Run:

```bash
python -c "from cataclysm.track_db import get_track_info; t = get_track_info('Roebling Road Raceway'); print(t)"
```

Adjust attribute names in `resolve_session_timezone()` if needed.

- [ ] **Step 6: Run quality gates and commit**

```bash
ruff format cataclysm/timezone_utils.py tests/test_timezone_utils.py
ruff check cataclysm/timezone_utils.py tests/test_timezone_utils.py
dmypy run -- cataclysm/timezone_utils.py
git add cataclysm/timezone_utils.py tests/test_timezone_utils.py
git commit -m "feat: add resolve_session_timezone with GPS + track_db fallback"
```

---

### Task 3: Add `session_date_to_iso()` utility

**Files:**
- Modify: `cataclysm/timezone_utils.py`
- Modify: `tests/test_timezone_utils.py`

- [ ] **Step 1: Write tests**

Add to `tests/test_timezone_utils.py`:

```python
from cataclysm.timezone_utils import session_date_to_iso


def test_session_date_to_iso_ddmmyyyy() -> None:
    """Converts DD/MM/YYYY HH:MM to ISO 8601 UTC."""
    assert session_date_to_iso("21/03/2026 12:31") == "2026-03-21T12:31:00Z"


def test_session_date_to_iso_date_only() -> None:
    """Date-only string gets midnight."""
    assert session_date_to_iso("21/03/2026") == "2026-03-21T00:00:00Z"


def test_session_date_to_iso_already_iso() -> None:
    """ISO input passes through."""
    assert session_date_to_iso("2026-03-21 12:31:00") == "2026-03-21T12:31:00Z"


def test_session_date_to_iso_unparseable() -> None:
    """Unparseable string returns itself."""
    assert session_date_to_iso("garbage") == "garbage"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_timezone_utils.py::test_session_date_to_iso_ddmmyyyy -v`
Expected: FAIL — `session_date_to_iso` not defined.

- [ ] **Step 3: Implement `session_date_to_iso()`**

Add to `cataclysm/timezone_utils.py`:

```python
def session_date_to_iso(date_str: str) -> str:
    """Convert a RaceChrono date string to ISO 8601 UTC format.

    Returns the original string unchanged if parsing fails.
    """
    cleaned = date_str.strip()
    for fmt in [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y,%H:%M",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(cleaned, fmt)  # noqa: DTZ007
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return date_str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_timezone_utils.py -v`
Expected: All PASS.

- [ ] **Step 5: Run quality gates and commit**

```bash
ruff format cataclysm/timezone_utils.py tests/test_timezone_utils.py
ruff check cataclysm/timezone_utils.py tests/test_timezone_utils.py
dmypy run -- cataclysm/timezone_utils.py
git add cataclysm/timezone_utils.py tests/test_timezone_utils.py
git commit -m "feat: add session_date_to_iso utility for ISO 8601 conversion"
```

---

### Task 4: Wire timezone into SessionData and snapshot_json persistence

**Files:**
- Modify: `backend/api/services/session_store.py:48-68` (add fields to `SessionData`)
- Modify: `backend/api/services/pipeline.py` (resolve timezone after parsing)
- Modify: `backend/api/services/db_session_store.py:223-280` (persist to `snapshot_json`)

`SessionData` is a dataclass (not the DB model). Timezone data goes on it as new optional fields, then gets persisted to `snapshot_json` via `db_session_store.store_session_db()`.

- [ ] **Step 1: Add timezone fields to `SessionData`**

In `backend/api/services/session_store.py`, add three fields to the `SessionData` dataclass after `client_ip`:

```python
timezone_name: str | None = None
session_date_local: str | None = None
session_date_iso: str | None = None
```

- [ ] **Step 2: Resolve timezone in pipeline after parsing**

In `backend/api/services/pipeline.py`, find where `SessionData(...)` is constructed. After the session is parsed and GPS data is available, resolve timezone before building `SessionData`:

```python
from cataclysm.timezone_utils import resolve_session_timezone, localize_session_date, session_date_to_iso

# Resolve timezone from GPS (after parsed.data is available)
timezone_name = resolve_session_timezone(parsed.data, parsed.metadata.track_name)
session_date_local: str | None = None
if timezone_name:
    session_date_local = localize_session_date(parsed.metadata.session_date, timezone_name)
session_date_iso = session_date_to_iso(parsed.metadata.session_date)
```

Then pass these into the `SessionData(...)` constructor:

```python
timezone_name=timezone_name,
session_date_local=session_date_local,
session_date_iso=session_date_iso,
```

- [ ] **Step 3: Persist timezone data to `snapshot_json`**

In `backend/api/services/db_session_store.py`, in the `store_session_db()` function around line 223-280 where `snapshot_json` dict is built, add after the existing keys:

```python
if sd.timezone_name:
    snapshot_json["timezone_name"] = sd.timezone_name
if sd.session_date_local:
    snapshot_json["session_date_local"] = sd.session_date_local
if sd.session_date_iso:
    snapshot_json["session_date_iso"] = sd.session_date_iso
```

This ensures the data survives backend restarts (DB fallback path reads from `snapshot_json`).

- [ ] **Step 4: Test manually with a Roebling CSV**

```bash
source .venv/bin/activate
python -c "
from cataclysm.parser import parse_csv
from cataclysm.timezone_utils import resolve_session_timezone, localize_session_date, session_date_to_iso
import pathlib

csv = pathlib.Path('/mnt/d/Downloads/session_20260321_083201_roebling_road_2_v3.csv')
parsed = parse_csv(csv.read_text())
tz = resolve_session_timezone(parsed.data, parsed.metadata.track_name)
local = localize_session_date(parsed.metadata.session_date, tz) if tz else None
iso = session_date_to_iso(parsed.metadata.session_date)
print(f'Raw: {parsed.metadata.session_date}')
print(f'TZ:  {tz}')
print(f'ISO: {iso}')
print(f'Local: {local}')
"
```

Expected output:
```
Raw: 21/03/2026 12:31
TZ:  America/New_York
ISO: 2026-03-21T12:31:00Z
Local: Mar 21, 2026 · 8:31 AM EDT
```

- [ ] **Step 5: Run quality gates and commit**

```bash
ruff format backend/api/services/pipeline.py backend/api/services/session_store.py backend/api/services/db_session_store.py
ruff check backend/api/services/pipeline.py backend/api/services/session_store.py backend/api/services/db_session_store.py
dmypy run -- backend/api/services/pipeline.py backend/api/services/session_store.py backend/api/services/db_session_store.py
pytest tests/ backend/tests/ -v -n auto --timeout=60
git add backend/api/services/pipeline.py backend/api/services/session_store.py backend/api/services/db_session_store.py
git commit -m "feat: resolve timezone from GPS, store on SessionData and in snapshot_json"
```

---

### Task 5: Update `sessions.py` serialization — 3 paths

**Files:**
- Modify: `backend/api/routers/sessions.py:636-662` (in-memory list path)
- Modify: `backend/api/routers/sessions.py:691-710` (DB fallback list path)
- Modify: `backend/api/routers/sessions.py:755-775` (get_session path)

All three `SessionSummary(...)` constructions need:
- `session_date=` → ISO string
- `session_date_local=` → localized display string

- [ ] **Step 1: Add imports and helper functions at module top**

Add near the top of `backend/api/routers/sessions.py`:

```python
from cataclysm.timezone_utils import (
    localize_session_date,
    resolve_session_timezone,
    session_date_to_iso,
)
```

Add two helper functions before `list_sessions()`:

```python
def _get_session_date_iso(sd: SessionData) -> str:
    """Return ISO 8601 UTC date from SessionData."""
    return sd.session_date_iso or session_date_to_iso(sd.snapshot.metadata.session_date)


def _get_session_date_local(sd: SessionData) -> str | None:
    """Return localized display date, resolving lazily if needed."""
    if sd.session_date_local:
        return sd.session_date_local
    # Lazy resolve for sessions uploaded before timezone support
    tz = sd.timezone_name
    if not tz:
        tz = resolve_session_timezone(sd.parsed.data, sd.snapshot.metadata.track_name)
    if tz:
        return localize_session_date(sd.snapshot.metadata.session_date, tz)
    return None


def _lazy_localize_from_db(
    row: SessionModel, snap: dict[str, object],
) -> str | None:
    """Localize session date for DB rows without cached timezone."""
    tz = snap.get("timezone_name")
    if not tz:
        tz = resolve_session_timezone(
            pd.DataFrame(),  # no telemetry available
            track_name=row.track_name,
        )
    if tz and row.session_date:
        date_str = row.session_date.strftime("%Y-%m-%d %H:%M:%S")
        return localize_session_date(date_str, str(tz))
    return None
```

Also add `import pandas as pd` if not already imported.

- [ ] **Step 2: Update in-memory list path (line 639)**

Replace:
```python
session_date=sd.snapshot.metadata.session_date,
```

With:
```python
session_date=_get_session_date_iso(sd),
session_date_local=_get_session_date_local(sd),
```

- [ ] **Step 3: Update DB fallback list path (line 694)**

Replace:
```python
session_date=date_str,
```

With:
```python
session_date=row.session_date.isoformat() + "Z" if row.session_date else "",
session_date_local=snap.get("session_date_local") or _lazy_localize_from_db(row, snap),
```

Also remove the `date_str` variable computation above it (lines 683-684) — it's no longer needed.

- [ ] **Step 4: Update get_session path (line 758)**

Same pattern as step 2:
```python
session_date=_get_session_date_iso(sd),
session_date_local=_get_session_date_local(sd),
```

- [ ] **Step 4: Run backend tests**

Run: `pytest backend/tests/ -v -n auto --timeout=60`

Fix any test assertions that expect the old DD/MM/YYYY format in `session_date`. Tests should now expect ISO format.

- [ ] **Step 5: Run quality gates and commit**

```bash
ruff format backend/api/routers/sessions.py
ruff check backend/api/routers/sessions.py
dmypy run -- backend/api/routers/sessions.py
git add backend/api/routers/sessions.py
git commit -m "feat: return ISO session_date + localized session_date_local in session API"
```

---

### Task 6: Update coaching and sharing routers

**Files:**
- Modify: `backend/api/routers/coaching.py:680-722`
- Modify: `backend/api/routers/sharing.py:191-252`

- [ ] **Step 1: Update coaching router**

In `_build_report_content()` at line 680, the `session_date` feeds `ReportContent` which is used for PDF generation. This should show the local time:

```python
session_date = sd.session_date_local or snapshot.metadata.session_date
```

The PDF header will now show `"Mar 21, 2026 · 8:31 AM EDT"` instead of `"21/03/2026 12:31"`.

- [ ] **Step 2: Update sharing router**

In `get_public_session()` at line 196, update:

```python
session_date = sd.session_date_local or sd.snapshot.metadata.session_date
```

And in the `PublicSessionView` construction at line 252, it already uses `session_date` — so it'll pick up the local string.

- [ ] **Step 3: Run tests**

Run: `pytest backend/tests/ -v -n auto --timeout=60`
Fix any assertion failures.

- [ ] **Step 4: Run quality gates and commit**

```bash
ruff format backend/api/routers/coaching.py backend/api/routers/sharing.py
ruff check backend/api/routers/coaching.py backend/api/routers/sharing.py
dmypy run -- backend/api/routers/coaching.py backend/api/routers/sharing.py
git add backend/api/routers/coaching.py backend/api/routers/sharing.py
git commit -m "feat: use localized dates in coaching PDF and share page"
```

---

### Task 7: Update frontend `parseSessionDate()` and add `formatSessionDate()`

**Files:**
- Modify: `frontend/src/lib/formatters.ts`
- Modify: `frontend/src/lib/__tests__/formatters.test.ts`

- [ ] **Step 1: Write tests for updated `parseSessionDate()` and new `formatSessionDate()`**

Replace the `parseSessionDate` test block and add `formatSessionDate` tests in `frontend/src/lib/__tests__/formatters.test.ts`:

```typescript
// ---------------------------------------------------------------------------
// parseSessionDate
// ---------------------------------------------------------------------------
describe('parseSessionDate', () => {
  it('parses ISO 8601 UTC string', () => {
    const d = parseSessionDate('2026-03-21T12:31:00Z');
    expect(d.getUTCFullYear()).toBe(2026);
    expect(d.getUTCMonth()).toBe(2); // March, 0-indexed
    expect(d.getUTCDate()).toBe(21);
    expect(d.getUTCHours()).toBe(12);
    expect(d.getUTCMinutes()).toBe(31);
  });

  it('parses ISO without Z suffix', () => {
    const d = parseSessionDate('2026-03-21T12:31:00');
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(2);
  });

  it('falls back to DD/MM/YYYY for legacy cached responses', () => {
    const d = parseSessionDate('21/03/2026 12:31');
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(2); // March
    expect(d.getDate()).toBe(21);
  });

  it('returns valid Date for date-only ISO', () => {
    const d = parseSessionDate('2026-03-21');
    expect(d.getUTCFullYear()).toBe(2026);
    expect(isNaN(d.getTime())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// formatSessionDate
// ---------------------------------------------------------------------------
describe('formatSessionDate', () => {
  it('formats ISO date to short display format', () => {
    // Just verify it produces a reasonable string — exact output depends on locale
    const result = formatSessionDate('2026-03-21T12:31:00Z');
    expect(result).toContain('2026');
    expect(result).toContain('21');
  });

  it('returns "—" for empty string', () => {
    expect(formatSessionDate('')).toBe('—');
  });

  it('returns "—" for unparseable date', () => {
    expect(formatSessionDate('garbage')).toBe('—');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/__tests__/formatters.test.ts`
Expected: FAIL — `formatSessionDate` not exported, `parseSessionDate` tests fail on ISO input.

- [ ] **Step 3: Update `parseSessionDate()` and add `formatSessionDate()`**

Replace the existing `parseSessionDate` in `frontend/src/lib/formatters.ts` and add `formatSessionDate`:

```typescript
/**
 * Parse a session date string from the backend.
 * Primary format: ISO 8601 ("2026-03-21T12:31:00Z").
 * Fallback: legacy DD/MM/YYYY HH:MM for cached responses.
 */
export function parseSessionDate(dateStr: string): Date {
  // Try ISO first (new format)
  const iso = new Date(dateStr);
  if (!isNaN(iso.getTime()) && dateStr.includes('-')) return iso;

  // Fallback: DD/MM/YYYY HH:MM (legacy cached responses)
  const ddmm = dateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/);
  if (ddmm) {
    const [, day, month, year, hour, min] = ddmm;
    return new Date(+year, +month - 1, +day, +(hour ?? 0), +(min ?? 0));
  }

  return new Date(dateStr);
}

/**
 * Format an ISO session date for display when session_date_local is unavailable.
 * Returns a UTC-based fallback like "Mar 21, 2026 · 12:31 PM UTC".
 */
export function formatSessionDate(isoStr: string): string {
  if (!isoStr) return '—';
  const d = parseSessionDate(isoStr);
  if (isNaN(d.getTime())) return '—';
  const month = d.toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' });
  const day = d.getUTCDate();
  const year = d.getUTCFullYear();
  const hours = d.getUTCHours();
  const minutes = d.getUTCMinutes().toString().padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  const h12 = hours % 12 || 12;
  return `${month} ${day}, ${year} · ${h12}:${minutes} ${ampm} UTC`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/__tests__/formatters.test.ts`
Expected: All PASS.

- [ ] **Step 5: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/formatters.ts frontend/src/lib/__tests__/formatters.test.ts
git commit -m "feat: update parseSessionDate for ISO, add formatSessionDate fallback"
```

---

### Task 8: Update frontend display surfaces

**Files:**
- Modify: `frontend/src/components/navigation/SessionDrawer.tsx`
- Modify: `frontend/src/components/comparison/SessionSelector.tsx:104,151`

- [ ] **Step 1: Simplify `getDateCategory()` in SessionDrawer**

Replace the `parseDateStr` + `getDateCategory` block with:

```typescript
function getDateCategory(dateStr: string): string {
  const today = new Date();
  const date = new Date(dateStr); // ISO string — native parsing works
  if (isNaN(date.getTime())) return 'Older';
  const diffDays = Math.floor((today.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return 'Today';
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return 'This Week';
  if (diffDays < 30) return 'This Month';
  return 'Older';
}
```

Remove the `parseDateStr()` function entirely — it was a bandaid from earlier.

- [ ] **Step 2: Update SessionSelector to use `session_date_local`**

In `frontend/src/components/comparison/SessionSelector.tsx`, update the two display locations:

Line 104 — change:
```tsx
{currentSession.track_name} &mdash; {currentSession.session_date}
```
To:
```tsx
{currentSession.track_name} &mdash; {currentSession.session_date_local ?? currentSession.session_date}
```

Line 151 — change:
```tsx
{s.session_date} &middot; {s.n_clean_laps ?? 0}/{s.n_laps ?? 0} clean laps
```
To:
```tsx
{s.session_date_local ?? s.session_date} &middot; {s.n_clean_laps ?? 0}/{s.n_laps ?? 0} clean laps
```

- [ ] **Step 3: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/navigation/SessionDrawer.tsx frontend/src/components/comparison/SessionSelector.tsx
git commit -m "feat: simplify date grouping for ISO format, use session_date_local in selector"
```

---

### Task 9: Integration test and push to staging

**Files:** None new — verification only.

- [ ] **Step 1: Run full backend test suite**

```bash
source .venv/bin/activate
pytest tests/ backend/tests/ -v -n auto --timeout=60
```

All must pass. Fix any failures from changed date formats.

- [ ] **Step 2: Run full frontend checks**

```bash
cd frontend && npx tsc --noEmit && npx vitest run
```

- [ ] **Step 3: Run ruff + mypy**

```bash
ruff format cataclysm/ tests/ backend/
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
```

- [ ] **Step 4: Push to staging**

```bash
git push origin temp/physics-clean:staging
```

- [ ] **Step 5: Wait for Railway deploy (~2-3 min), then verify**

Use `list-deployments --service backend --environment staging` and `list-deployments --service frontend --environment staging` to confirm both deployed successfully. Then `get-logs` for both to check for errors.

- [ ] **Step 6: Visual QA on staging**

Open `https://cataclysm-staging.up.railway.app` and verify:
1. Session drawer shows dates like `"Mar 21, 2026 · 8:31 AM EDT"` (not DD/MM/YYYY)
2. Date grouping is correct (March sessions = "This Month", January = "Older")
3. Report header shows local time
4. Top bar breadcrumb shows local time
5. Progress charts show correct date labels
6. Session comparison selector shows local time

- [ ] **Step 7: Code review**

Run `superpowers:code-reviewer` on all changed files.
