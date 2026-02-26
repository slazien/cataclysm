# Equipment Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add equipment tracking (tires, brakes, suspension) per session with named profiles, per-session overrides, tire grip lookup, weather auto-populate, physics integration, and coaching context.

**Architecture:** Five phases (A→E), each building on the previous. Core data model in `cataclysm/equipment.py`, persistence via `equipment_store.py` (mirrors coaching_store pattern), FastAPI CRUD endpoints, frontend Zustand store + forms. Phase D wires equipment → VehicleParams → velocity solver. Phase E adds equipment context to coaching prompts.

**Tech Stack:** Python 3.11+ dataclasses, FastAPI, Pydantic v2, httpx (UTQG + Open-Meteo APIs), Zustand, TanStack Query, TypeScript, Tailwind CSS.

**Design doc:** `docs/plans/2026-02-25-equipment-tracking-design.md`

---

## Phase A: Equipment Profiles + Session Association + Filtering

Core data model, persistence, CRUD API, and session-equipment linkage.

---

### Task A1: Core Equipment Data Model

**Files:**
- Create: `cataclysm/equipment.py`
- Test: `tests/test_equipment.py`

**Step 1: Write failing test for equipment dataclasses**

Create `tests/test_equipment.py`:

```python
"""Tests for cataclysm.equipment."""

from __future__ import annotations

from cataclysm.equipment import (
    BrakeSpec,
    EquipmentProfile,
    MuSource,
    SuspensionSpec,
    TireCompoundCategory,
    TireSpec,
)


class TestTireSpec:
    def test_create_basic_tire(self) -> None:
        tire = TireSpec(
            model="Bridgestone RE-71RS",
            compound_category=TireCompoundCategory.SUPER_200TW,
            size="255/40R17",
            treadwear_rating=200,
            estimated_mu=1.10,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="Track test aggregate for 200TW super category",
        )
        assert tire.model == "Bridgestone RE-71RS"
        assert tire.estimated_mu == 1.10
        assert tire.mu_source == MuSource.CURATED_TABLE

    def test_tire_compound_categories_exist(self) -> None:
        assert TireCompoundCategory.STREET.value == "street"
        assert TireCompoundCategory.R_COMPOUND.value == "r_comp"
        assert TireCompoundCategory.SLICK.value == "slick"

    def test_mu_source_values(self) -> None:
        assert MuSource.FORMULA_ESTIMATE.value == "formula_estimate"
        assert MuSource.MANUFACTURER_SPEC.value == "manufacturer_spec"
        assert MuSource.USER_OVERRIDE.value == "user_override"


class TestEquipmentProfile:
    def test_create_minimal_profile(self) -> None:
        tire = TireSpec(
            model="Hankook RS4",
            compound_category=TireCompoundCategory.ENDURANCE_200TW,
            size="245/40R18",
            treadwear_rating=200,
            estimated_mu=1.00,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="Category default for endurance 200TW",
        )
        profile = EquipmentProfile(
            id="prof_001",
            name="Track Day - RS4",
            tires=tire,
        )
        assert profile.name == "Track Day - RS4"
        assert profile.brakes is None
        assert profile.suspension is None

    def test_create_full_profile(self) -> None:
        tire = TireSpec(
            model="Hoosier R7",
            compound_category=TireCompoundCategory.R_COMPOUND,
            size="275/35R18",
            treadwear_rating=40,
            estimated_mu=1.35,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="R-compound category default",
        )
        brakes = BrakeSpec(compound="Hawk DTC-60", rotor_type="2-piece")
        susp = SuspensionSpec(
            type="coilover",
            front_spring_rate="12kg/mm",
            rear_spring_rate="10kg/mm",
            front_camber_deg=-3.0,
            rear_camber_deg=-2.5,
        )
        profile = EquipmentProfile(
            id="prof_002",
            name="Race Setup",
            tires=tire,
            brakes=brakes,
            suspension=susp,
        )
        assert profile.brakes is not None
        assert profile.brakes.compound == "Hawk DTC-60"
        assert profile.suspension is not None
        assert profile.suspension.front_camber_deg == -3.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_equipment.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cataclysm.equipment'`

**Step 3: Implement the data model**

Create `cataclysm/equipment.py`:

```python
"""Equipment tracking data model for vehicle setup profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TireCompoundCategory(str, Enum):
    """Tire compound categories ordered by approximate grip level."""

    STREET = "street"                    # 300+ TW, all-season/summer
    ENDURANCE_200TW = "endurance_200tw"  # 200 TW, durable (RS4, RT660)
    SUPER_200TW = "super_200tw"          # 200 TW, grippy (RE-71RS, AD09)
    TW_100 = "100tw"                     # 100 TW (Rival S, A052)
    R_COMPOUND = "r_comp"                # R-compound / DOT slick (Hoosier R7)
    SLICK = "slick"                      # Full slick (race only)


class MuSource(str, Enum):
    """Provenance of a tire's estimated grip coefficient."""

    FORMULA_ESTIMATE = "formula_estimate"    # HPWizard UTQG formula
    CURATED_TABLE = "curated_table"          # Community/editorial data
    MANUFACTURER_SPEC = "manufacturer_spec"  # Manufacturer datasheets
    USER_OVERRIDE = "user_override"          # User-set value


# Default mu values per compound category.
# Sources: track test aggregates, community data, conservative estimates.
CATEGORY_MU_DEFAULTS: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 0.85,
    TireCompoundCategory.ENDURANCE_200TW: 1.00,
    TireCompoundCategory.SUPER_200TW: 1.10,
    TireCompoundCategory.TW_100: 1.20,
    TireCompoundCategory.R_COMPOUND: 1.35,
    TireCompoundCategory.SLICK: 1.50,
}


def estimate_mu_from_treadwear(treadwear: int) -> float:
    """Estimate friction coefficient from UTQG treadwear rating.

    Uses the HPWizard approximation: mu = 2.25 / TW^0.15

    Parameters
    ----------
    treadwear:
        UTQG treadwear rating (e.g., 200, 340).

    Returns
    -------
    float
        Estimated friction coefficient.
    """
    if treadwear <= 0:
        return 1.0  # fallback for invalid input
    return 2.25 / (treadwear ** 0.15)


@dataclass
class TireSpec:
    """Tire specification with grip estimation metadata."""

    # Essential (always visible)
    model: str
    compound_category: TireCompoundCategory
    size: str
    treadwear_rating: int | None

    # Physics
    estimated_mu: float
    mu_source: MuSource
    mu_confidence: str

    # Advanced (expandable in UI)
    pressure_psi: float | None = None
    brand: str | None = None
    age_sessions: int | None = None


@dataclass
class BrakeSpec:
    """Brake pad and rotor specification."""

    compound: str | None = None
    rotor_type: str | None = None
    pad_temp_range: str | None = None
    fluid_type: str | None = None


@dataclass
class SuspensionSpec:
    """Suspension setup specification."""

    type: str | None = None
    front_spring_rate: str | None = None
    rear_spring_rate: str | None = None
    front_camber_deg: float | None = None
    rear_camber_deg: float | None = None
    front_toe: str | None = None
    rear_toe: str | None = None
    front_rebound: int | None = None
    front_compression: int | None = None
    rear_rebound: int | None = None
    rear_compression: int | None = None
    sway_bar_front: str | None = None
    sway_bar_rear: str | None = None


@dataclass
class EquipmentProfile:
    """Named, reusable vehicle equipment configuration."""

    id: str
    name: str
    tires: TireSpec
    brakes: BrakeSpec | None = None
    suspension: SuspensionSpec | None = None
    notes: str | None = None


class TrackCondition(str, Enum):
    """Track surface condition."""

    DRY = "dry"
    DAMP = "damp"
    WET = "wet"


@dataclass
class SessionConditions:
    """Weather and track conditions for a session."""

    track_condition: TrackCondition = TrackCondition.DRY
    ambient_temp_c: float | None = None
    track_temp_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    precipitation_mm: float | None = None
    weather_source: str | None = None  # "open-meteo" or "user"


@dataclass
class SessionEquipment:
    """Equipment assignment for a session, with per-field overrides."""

    session_id: str
    profile_id: str
    overrides: dict[str, object] = field(default_factory=dict)
    conditions: SessionConditions | None = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_equipment.py -v`
Expected: PASS (all 5 tests)

**Step 5: Run quality gates**

Run: `ruff check cataclysm/equipment.py tests/test_equipment.py && ruff format cataclysm/equipment.py tests/test_equipment.py && mypy cataclysm/equipment.py`

**Step 6: Commit**

```bash
git add cataclysm/equipment.py tests/test_equipment.py
git commit -m "feat: add equipment tracking data model"
```

---

### Task A2: UTQG Formula + Category Defaults Tests

**Files:**
- Modify: `tests/test_equipment.py`
- (Already created in A1): `cataclysm/equipment.py`

**Step 1: Write failing tests for mu estimation**

Append to `tests/test_equipment.py`:

```python
from cataclysm.equipment import CATEGORY_MU_DEFAULTS, estimate_mu_from_treadwear


class TestEstimateMuFromTreadwear:
    def test_treadwear_200(self) -> None:
        mu = estimate_mu_from_treadwear(200)
        # 2.25 / 200^0.15 ≈ 0.93
        assert 0.90 < mu < 0.96

    def test_treadwear_100(self) -> None:
        mu = estimate_mu_from_treadwear(100)
        # lower TW = higher grip
        mu_200 = estimate_mu_from_treadwear(200)
        assert mu > mu_200

    def test_treadwear_400(self) -> None:
        mu = estimate_mu_from_treadwear(400)
        mu_200 = estimate_mu_from_treadwear(200)
        assert mu < mu_200

    def test_zero_treadwear_fallback(self) -> None:
        assert estimate_mu_from_treadwear(0) == 1.0

    def test_negative_treadwear_fallback(self) -> None:
        assert estimate_mu_from_treadwear(-50) == 1.0


class TestCategoryMuDefaults:
    def test_all_categories_have_defaults(self) -> None:
        for cat in TireCompoundCategory:
            assert cat in CATEGORY_MU_DEFAULTS

    def test_defaults_increase_with_grip(self) -> None:
        cats = [
            TireCompoundCategory.STREET,
            TireCompoundCategory.ENDURANCE_200TW,
            TireCompoundCategory.SUPER_200TW,
            TireCompoundCategory.TW_100,
            TireCompoundCategory.R_COMPOUND,
            TireCompoundCategory.SLICK,
        ]
        mus = [CATEGORY_MU_DEFAULTS[c] for c in cats]
        for i in range(len(mus) - 1):
            assert mus[i] < mus[i + 1], f"{cats[i]} should have lower mu than {cats[i+1]}"
```

**Step 2: Run tests**

Run: `pytest tests/test_equipment.py -v`
Expected: PASS (all tests — implementation was done in A1)

**Step 3: Commit**

```bash
git add tests/test_equipment.py
git commit -m "test: add mu estimation and category defaults tests"
```

---

### Task A3: Equipment Store (In-Memory + JSON Disk Persistence)

**Files:**
- Create: `backend/api/services/equipment_store.py`
- Test: `backend/tests/test_equipment_store.py`

**Step 1: Write failing tests**

Create `backend/tests/test_equipment_store.py`:

```python
"""Tests for equipment store persistence."""

from __future__ import annotations

import tempfile

import pytest

from cataclysm.equipment import (
    EquipmentProfile,
    MuSource,
    SessionConditions,
    SessionEquipment,
    TireCompoundCategory,
    TireSpec,
    TrackCondition,
)

from backend.api.services import equipment_store


def _make_tire() -> TireSpec:
    return TireSpec(
        model="Bridgestone RE-71RS",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="255/40R17",
        treadwear_rating=200,
        estimated_mu=1.10,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Track test aggregate",
    )


def _make_profile(profile_id: str = "prof_001", name: str = "Test Setup") -> EquipmentProfile:
    return EquipmentProfile(id=profile_id, name=name, tires=_make_tire())


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    """Clear the store before each test."""
    equipment_store.clear_all_equipment()


class TestProfileCRUD:
    def test_store_and_get_profile(self) -> None:
        profile = _make_profile()
        equipment_store.store_profile(profile)
        result = equipment_store.get_profile("prof_001")
        assert result is not None
        assert result.name == "Test Setup"
        assert result.tires.model == "Bridgestone RE-71RS"

    def test_get_missing_profile_returns_none(self) -> None:
        assert equipment_store.get_profile("nonexistent") is None

    def test_list_profiles(self) -> None:
        equipment_store.store_profile(_make_profile("p1", "Setup A"))
        equipment_store.store_profile(_make_profile("p2", "Setup B"))
        profiles = equipment_store.list_profiles()
        assert len(profiles) == 2

    def test_delete_profile(self) -> None:
        equipment_store.store_profile(_make_profile())
        assert equipment_store.delete_profile("prof_001") is True
        assert equipment_store.get_profile("prof_001") is None

    def test_delete_missing_profile(self) -> None:
        assert equipment_store.delete_profile("nonexistent") is False

    def test_update_profile(self) -> None:
        profile = _make_profile()
        equipment_store.store_profile(profile)
        profile.name = "Updated Name"
        equipment_store.store_profile(profile)
        result = equipment_store.get_profile("prof_001")
        assert result is not None
        assert result.name == "Updated Name"


class TestSessionEquipmentAssignment:
    def test_assign_and_get_session_equipment(self) -> None:
        se = SessionEquipment(session_id="sess_001", profile_id="prof_001")
        equipment_store.store_session_equipment(se)
        result = equipment_store.get_session_equipment("sess_001")
        assert result is not None
        assert result.profile_id == "prof_001"

    def test_get_missing_session_equipment(self) -> None:
        assert equipment_store.get_session_equipment("nonexistent") is None

    def test_override_fields(self) -> None:
        se = SessionEquipment(
            session_id="sess_001",
            profile_id="prof_001",
            overrides={"tires.pressure_psi": 32.0},
        )
        equipment_store.store_session_equipment(se)
        result = equipment_store.get_session_equipment("sess_001")
        assert result is not None
        assert result.overrides["tires.pressure_psi"] == 32.0

    def test_session_conditions(self) -> None:
        cond = SessionConditions(
            track_condition=TrackCondition.DRY,
            ambient_temp_c=25.0,
        )
        se = SessionEquipment(
            session_id="sess_001",
            profile_id="prof_001",
            conditions=cond,
        )
        equipment_store.store_session_equipment(se)
        result = equipment_store.get_session_equipment("sess_001")
        assert result is not None
        assert result.conditions is not None
        assert result.conditions.ambient_temp_c == 25.0


class TestPersistence:
    def test_persist_and_load_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            equipment_store.init_equipment_dir(tmpdir)
            equipment_store.store_profile(_make_profile())

            # Clear in-memory, reload from disk
            equipment_store.clear_all_equipment()
            count = equipment_store.load_persisted_profiles()
            assert count == 1
            result = equipment_store.get_profile("prof_001")
            assert result is not None
            assert result.tires.model == "Bridgestone RE-71RS"
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_equipment_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.api.services.equipment_store'`

**Step 3: Implement the store**

Create `backend/api/services/equipment_store.py`:

```python
"""In-memory store for equipment profiles with JSON disk persistence.

Mirrors the coaching_store pattern: dict-based in-memory store with
JSON file persistence under the configured equipment data directory.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cataclysm.equipment import (
    BrakeSpec,
    EquipmentProfile,
    MuSource,
    SessionConditions,
    SessionEquipment,
    SuspensionSpec,
    TireCompoundCategory,
    TireSpec,
    TrackCondition,
)

logger = logging.getLogger(__name__)

# Module-level in-memory stores
_profiles: dict[str, EquipmentProfile] = {}
_session_equipment: dict[str, SessionEquipment] = {}

# Disk persistence directory
_equipment_dir: Path | None = None


def init_equipment_dir(path: str) -> None:
    """Configure the directory for persisting equipment data."""
    global _equipment_dir  # noqa: PLW0603
    _equipment_dir = Path(path)
    _equipment_dir.mkdir(parents=True, exist_ok=True)
    (_equipment_dir / "profiles").mkdir(exist_ok=True)
    (_equipment_dir / "sessions").mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _profile_to_dict(profile: EquipmentProfile) -> dict[str, Any]:
    """Convert an EquipmentProfile to a JSON-serializable dict."""
    d = asdict(profile)
    # Convert enums to their values for JSON
    d["tires"]["compound_category"] = profile.tires.compound_category.value
    d["tires"]["mu_source"] = profile.tires.mu_source.value
    return d


def _profile_from_dict(d: dict[str, Any]) -> EquipmentProfile:
    """Reconstruct an EquipmentProfile from a dict."""
    tires_d = d["tires"]
    tires = TireSpec(
        model=tires_d["model"],
        compound_category=TireCompoundCategory(tires_d["compound_category"]),
        size=tires_d["size"],
        treadwear_rating=tires_d.get("treadwear_rating"),
        estimated_mu=tires_d["estimated_mu"],
        mu_source=MuSource(tires_d["mu_source"]),
        mu_confidence=tires_d["mu_confidence"],
        pressure_psi=tires_d.get("pressure_psi"),
        brand=tires_d.get("brand"),
        age_sessions=tires_d.get("age_sessions"),
    )

    brakes = None
    if d.get("brakes"):
        b = d["brakes"]
        brakes = BrakeSpec(
            compound=b.get("compound"),
            rotor_type=b.get("rotor_type"),
            pad_temp_range=b.get("pad_temp_range"),
            fluid_type=b.get("fluid_type"),
        )

    suspension = None
    if d.get("suspension"):
        s = d["suspension"]
        suspension = SuspensionSpec(**{k: v for k, v in s.items() if v is not None})

    return EquipmentProfile(
        id=d["id"],
        name=d["name"],
        tires=tires,
        brakes=brakes,
        suspension=suspension,
        notes=d.get("notes"),
    )


def _session_equipment_to_dict(se: SessionEquipment) -> dict[str, Any]:
    """Convert SessionEquipment to a JSON-serializable dict."""
    d: dict[str, Any] = {
        "session_id": se.session_id,
        "profile_id": se.profile_id,
        "overrides": se.overrides,
    }
    if se.conditions is not None:
        cond = asdict(se.conditions)
        cond["track_condition"] = se.conditions.track_condition.value
        d["conditions"] = cond
    else:
        d["conditions"] = None
    return d


def _session_equipment_from_dict(d: dict[str, Any]) -> SessionEquipment:
    """Reconstruct SessionEquipment from a dict."""
    conditions = None
    if d.get("conditions"):
        c = d["conditions"]
        conditions = SessionConditions(
            track_condition=TrackCondition(c["track_condition"]),
            ambient_temp_c=c.get("ambient_temp_c"),
            track_temp_c=c.get("track_temp_c"),
            humidity_pct=c.get("humidity_pct"),
            wind_speed_kmh=c.get("wind_speed_kmh"),
            wind_direction_deg=c.get("wind_direction_deg"),
            precipitation_mm=c.get("precipitation_mm"),
            weather_source=c.get("weather_source"),
        )
    return SessionEquipment(
        session_id=d["session_id"],
        profile_id=d["profile_id"],
        overrides=d.get("overrides", {}),
        conditions=conditions,
    )


# ---------------------------------------------------------------------------
# Persistence (disk)
# ---------------------------------------------------------------------------


def _persist_profile(profile: EquipmentProfile) -> None:
    if _equipment_dir is None:
        return
    try:
        path = _equipment_dir / "profiles" / f"{profile.id}.json"
        path.write_text(
            json.dumps(_profile_to_dict(profile), indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.warning("Failed to persist profile %s", profile.id, exc_info=True)


def _delete_persisted_profile(profile_id: str) -> None:
    if _equipment_dir is None:
        return
    path = _equipment_dir / "profiles" / f"{profile_id}.json"
    path.unlink(missing_ok=True)


def _persist_session_equipment(se: SessionEquipment) -> None:
    if _equipment_dir is None:
        return
    try:
        path = _equipment_dir / "sessions" / f"{se.session_id}.json"
        path.write_text(
            json.dumps(_session_equipment_to_dict(se), indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.warning(
            "Failed to persist session equipment for %s", se.session_id, exc_info=True
        )


def load_persisted_profiles() -> int:
    """Load all persisted profiles from disk. Returns count loaded."""
    if _equipment_dir is None or not (_equipment_dir / "profiles").exists():
        return 0
    count = 0
    for path in (_equipment_dir / "profiles").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            profile = _profile_from_dict(data)
            _profiles[profile.id] = profile
            count += 1
        except Exception:
            logger.warning("Failed to load profile from %s", path, exc_info=True)
    return count


def load_persisted_session_equipment() -> int:
    """Load all persisted session equipment from disk. Returns count loaded."""
    if _equipment_dir is None or not (_equipment_dir / "sessions").exists():
        return 0
    count = 0
    for path in (_equipment_dir / "sessions").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            se = _session_equipment_from_dict(data)
            _session_equipment[se.session_id] = se
            count += 1
        except Exception:
            logger.warning("Failed to load session equipment from %s", path, exc_info=True)
    return count


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------


def store_profile(profile: EquipmentProfile) -> None:
    """Store or update an equipment profile."""
    _profiles[profile.id] = profile
    _persist_profile(profile)


def get_profile(profile_id: str) -> EquipmentProfile | None:
    """Get a profile by ID, or None."""
    return _profiles.get(profile_id)


def list_profiles() -> list[EquipmentProfile]:
    """List all profiles sorted by name."""
    return sorted(_profiles.values(), key=lambda p: p.name)


def delete_profile(profile_id: str) -> bool:
    """Delete a profile. Returns True if it existed."""
    existed = _profiles.pop(profile_id, None) is not None
    if existed:
        _delete_persisted_profile(profile_id)
    return existed


# ---------------------------------------------------------------------------
# Session equipment CRUD
# ---------------------------------------------------------------------------


def store_session_equipment(se: SessionEquipment) -> None:
    """Store or update session equipment assignment."""
    _session_equipment[se.session_id] = se
    _persist_session_equipment(se)


def get_session_equipment(session_id: str) -> SessionEquipment | None:
    """Get equipment assignment for a session, or None."""
    return _session_equipment.get(session_id)


def delete_session_equipment(session_id: str) -> bool:
    """Remove equipment assignment for a session."""
    existed = _session_equipment.pop(session_id, None) is not None
    if existed and _equipment_dir is not None:
        path = _equipment_dir / "sessions" / f"{session_id}.json"
        path.unlink(missing_ok=True)
    return existed


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def clear_all_equipment() -> None:
    """Remove all equipment data from memory."""
    _profiles.clear()
    _session_equipment.clear()
```

**Step 4: Run tests**

Run: `pytest backend/tests/test_equipment_store.py -v`
Expected: PASS (all 10 tests)

**Step 5: Quality gates**

Run: `ruff check backend/api/services/equipment_store.py backend/tests/test_equipment_store.py && ruff format backend/api/services/equipment_store.py backend/tests/test_equipment_store.py && mypy backend/api/services/equipment_store.py`

**Step 6: Commit**

```bash
git add backend/api/services/equipment_store.py backend/tests/test_equipment_store.py
git commit -m "feat: add equipment store with JSON disk persistence"
```

---

### Task A4: Pydantic Schemas for Equipment API

**Files:**
- Create: `backend/api/schemas/equipment.py`
- Test: inline validation via Pydantic (no separate test file needed)

**Step 1: Create Pydantic schemas**

Create `backend/api/schemas/equipment.py`:

```python
"""Pydantic schemas for equipment API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TireSpecSchema(BaseModel):
    model: str
    compound_category: str  # TireCompoundCategory value
    size: str
    treadwear_rating: int | None = None
    estimated_mu: float
    mu_source: str  # MuSource value
    mu_confidence: str
    pressure_psi: float | None = None
    brand: str | None = None
    age_sessions: int | None = None


class BrakeSpecSchema(BaseModel):
    compound: str | None = None
    rotor_type: str | None = None
    pad_temp_range: str | None = None
    fluid_type: str | None = None


class SuspensionSpecSchema(BaseModel):
    type: str | None = None
    front_spring_rate: str | None = None
    rear_spring_rate: str | None = None
    front_camber_deg: float | None = None
    rear_camber_deg: float | None = None
    front_toe: str | None = None
    rear_toe: str | None = None
    front_rebound: int | None = None
    front_compression: int | None = None
    rear_rebound: int | None = None
    rear_compression: int | None = None
    sway_bar_front: str | None = None
    sway_bar_rear: str | None = None


class EquipmentProfileCreate(BaseModel):
    """Request body for creating an equipment profile."""

    name: str = Field(..., min_length=1, max_length=100)
    tires: TireSpecSchema
    brakes: BrakeSpecSchema | None = None
    suspension: SuspensionSpecSchema | None = None
    notes: str | None = None


class EquipmentProfileResponse(BaseModel):
    """Response schema for an equipment profile."""

    id: str
    name: str
    tires: TireSpecSchema
    brakes: BrakeSpecSchema | None = None
    suspension: SuspensionSpecSchema | None = None
    notes: str | None = None


class EquipmentProfileList(BaseModel):
    items: list[EquipmentProfileResponse]
    total: int


class SessionConditionsSchema(BaseModel):
    track_condition: str = "dry"
    ambient_temp_c: float | None = None
    track_temp_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    precipitation_mm: float | None = None
    weather_source: str | None = None


class SessionEquipmentSet(BaseModel):
    """Request body for assigning equipment to a session."""

    profile_id: str
    overrides: dict[str, object] = Field(default_factory=dict)
    conditions: SessionConditionsSchema | None = None


class SessionEquipmentResponse(BaseModel):
    """Response: effective equipment for a session."""

    session_id: str
    profile_id: str
    profile_name: str
    overrides: dict[str, object]
    tires: TireSpecSchema
    brakes: BrakeSpecSchema | None = None
    suspension: SuspensionSpecSchema | None = None
    conditions: SessionConditionsSchema | None = None
```

**Step 2: Quality gates**

Run: `ruff check backend/api/schemas/equipment.py && ruff format backend/api/schemas/equipment.py && mypy backend/api/schemas/equipment.py`

**Step 3: Commit**

```bash
git add backend/api/schemas/equipment.py
git commit -m "feat: add Pydantic schemas for equipment API"
```

---

### Task A5: Equipment API Router

**Files:**
- Create: `backend/api/routers/equipment.py`
- Modify: `backend/api/main.py` — register the new router
- Modify: `backend/api/config.py` — add `equipment_data_dir` setting
- Modify: `backend/api/main.py` lifespan — init equipment store on startup
- Test: `backend/tests/test_equipment_api.py`

**Step 1: Write failing API test**

Create `backend/tests/test_equipment_api.py`:

```python
"""Tests for equipment API endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.api.services import equipment_store


@pytest_asyncio.fixture
async def client():
    equipment_store.clear_all_equipment()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    equipment_store.clear_all_equipment()


SAMPLE_TIRE = {
    "model": "Bridgestone RE-71RS",
    "compound_category": "super_200tw",
    "size": "255/40R17",
    "treadwear_rating": 200,
    "estimated_mu": 1.10,
    "mu_source": "curated_table",
    "mu_confidence": "Track test aggregate",
}

SAMPLE_PROFILE = {
    "name": "Track Day Setup",
    "tires": SAMPLE_TIRE,
}


@pytest.mark.asyncio
async def test_create_and_get_profile(client: AsyncClient) -> None:
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    assert resp.status_code == 200
    data = resp.json()
    profile_id = data["id"]
    assert data["name"] == "Track Day Setup"
    assert data["tires"]["model"] == "Bridgestone RE-71RS"

    # GET by ID
    resp = await client.get(f"/api/equipment/profiles/{profile_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Track Day Setup"


@pytest.mark.asyncio
async def test_list_profiles(client: AsyncClient) -> None:
    await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    resp = await client.get("/api/equipment/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_delete_profile(client: AsyncClient) -> None:
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = resp.json()["id"]

    resp = await client.delete(f"/api/equipment/profiles/{profile_id}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/equipment/profiles/{profile_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_missing_profile_404(client: AsyncClient) -> None:
    resp = await client.get("/api/equipment/profiles/nonexistent")
    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_equipment_api.py -v`
Expected: FAIL — route not found (404 on POST)

**Step 3: Implement the router**

Create `backend/api/routers/equipment.py`:

```python
"""Equipment profile and session equipment endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from cataclysm.equipment import (
    BrakeSpec,
    EquipmentProfile,
    MuSource,
    SessionConditions,
    SessionEquipment,
    SuspensionSpec,
    TireCompoundCategory,
    TireSpec,
    TrackCondition,
)

from backend.api.schemas.equipment import (
    EquipmentProfileCreate,
    EquipmentProfileList,
    EquipmentProfileResponse,
    SessionEquipmentResponse,
    SessionEquipmentSet,
    TireSpecSchema,
)
from backend.api.services import equipment_store, session_store

router = APIRouter()


def _profile_to_response(p: EquipmentProfile) -> EquipmentProfileResponse:
    """Convert a domain EquipmentProfile to the API response schema."""
    from backend.api.schemas.equipment import BrakeSpecSchema, SuspensionSpecSchema

    tires = TireSpecSchema(
        model=p.tires.model,
        compound_category=p.tires.compound_category.value,
        size=p.tires.size,
        treadwear_rating=p.tires.treadwear_rating,
        estimated_mu=p.tires.estimated_mu,
        mu_source=p.tires.mu_source.value,
        mu_confidence=p.tires.mu_confidence,
        pressure_psi=p.tires.pressure_psi,
        brand=p.tires.brand,
        age_sessions=p.tires.age_sessions,
    )

    brakes = None
    if p.brakes is not None:
        brakes = BrakeSpecSchema(
            compound=p.brakes.compound,
            rotor_type=p.brakes.rotor_type,
            pad_temp_range=p.brakes.pad_temp_range,
            fluid_type=p.brakes.fluid_type,
        )

    suspension = None
    if p.suspension is not None:
        suspension = SuspensionSpecSchema(
            type=p.suspension.type,
            front_spring_rate=p.suspension.front_spring_rate,
            rear_spring_rate=p.suspension.rear_spring_rate,
            front_camber_deg=p.suspension.front_camber_deg,
            rear_camber_deg=p.suspension.rear_camber_deg,
            front_toe=p.suspension.front_toe,
            rear_toe=p.suspension.rear_toe,
            front_rebound=p.suspension.front_rebound,
            front_compression=p.suspension.front_compression,
            rear_rebound=p.suspension.rear_rebound,
            rear_compression=p.suspension.rear_compression,
            sway_bar_front=p.suspension.sway_bar_front,
            sway_bar_rear=p.suspension.sway_bar_rear,
        )

    return EquipmentProfileResponse(
        id=p.id,
        name=p.name,
        tires=tires,
        brakes=brakes,
        suspension=suspension,
        notes=p.notes,
    )


def _schema_to_tire(s: TireSpecSchema) -> TireSpec:
    """Convert API schema to domain TireSpec."""
    return TireSpec(
        model=s.model,
        compound_category=TireCompoundCategory(s.compound_category),
        size=s.size,
        treadwear_rating=s.treadwear_rating,
        estimated_mu=s.estimated_mu,
        mu_source=MuSource(s.mu_source),
        mu_confidence=s.mu_confidence,
        pressure_psi=s.pressure_psi,
        brand=s.brand,
        age_sessions=s.age_sessions,
    )


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------


@router.post("/profiles", response_model=EquipmentProfileResponse)
async def create_profile(body: EquipmentProfileCreate) -> EquipmentProfileResponse:
    """Create a new equipment profile."""
    profile_id = f"eq_{uuid.uuid4().hex[:12]}"

    tires = _schema_to_tire(body.tires)

    brakes = None
    if body.brakes is not None:
        brakes = BrakeSpec(
            compound=body.brakes.compound,
            rotor_type=body.brakes.rotor_type,
            pad_temp_range=body.brakes.pad_temp_range,
            fluid_type=body.brakes.fluid_type,
        )

    suspension = None
    if body.suspension is not None:
        s = body.suspension
        suspension = SuspensionSpec(
            type=s.type,
            front_spring_rate=s.front_spring_rate,
            rear_spring_rate=s.rear_spring_rate,
            front_camber_deg=s.front_camber_deg,
            rear_camber_deg=s.rear_camber_deg,
            front_toe=s.front_toe,
            rear_toe=s.rear_toe,
            front_rebound=s.front_rebound,
            front_compression=s.front_compression,
            rear_rebound=s.rear_rebound,
            rear_compression=s.rear_compression,
            sway_bar_front=s.sway_bar_front,
            sway_bar_rear=s.sway_bar_rear,
        )

    profile = EquipmentProfile(
        id=profile_id,
        name=body.name,
        tires=tires,
        brakes=brakes,
        suspension=suspension,
        notes=body.notes,
    )
    equipment_store.store_profile(profile)
    return _profile_to_response(profile)


@router.get("/profiles", response_model=EquipmentProfileList)
async def list_profiles() -> EquipmentProfileList:
    """List all equipment profiles."""
    profiles = equipment_store.list_profiles()
    items = [_profile_to_response(p) for p in profiles]
    return EquipmentProfileList(items=items, total=len(items))


@router.get("/profiles/{profile_id}", response_model=EquipmentProfileResponse)
async def get_profile(profile_id: str) -> EquipmentProfileResponse:
    """Get a single equipment profile."""
    profile = equipment_store.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return _profile_to_response(profile)


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str) -> dict[str, str]:
    """Delete an equipment profile."""
    if not equipment_store.delete_profile(profile_id):
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return {"message": f"Profile {profile_id} deleted"}


# ---------------------------------------------------------------------------
# Session equipment assignment
# ---------------------------------------------------------------------------


@router.put("/{session_id}/equipment", response_model=SessionEquipmentResponse)
async def set_session_equipment(
    session_id: str,
    body: SessionEquipmentSet,
) -> SessionEquipmentResponse:
    """Assign or update equipment for a session."""
    # Validate session exists
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Validate profile exists
    profile = equipment_store.get_profile(body.profile_id)
    if profile is None:
        raise HTTPException(
            status_code=404, detail=f"Profile {body.profile_id} not found"
        )

    conditions = None
    if body.conditions is not None:
        conditions = SessionConditions(
            track_condition=TrackCondition(body.conditions.track_condition),
            ambient_temp_c=body.conditions.ambient_temp_c,
            track_temp_c=body.conditions.track_temp_c,
            humidity_pct=body.conditions.humidity_pct,
            wind_speed_kmh=body.conditions.wind_speed_kmh,
            wind_direction_deg=body.conditions.wind_direction_deg,
            precipitation_mm=body.conditions.precipitation_mm,
            weather_source=body.conditions.weather_source,
        )

    se = SessionEquipment(
        session_id=session_id,
        profile_id=body.profile_id,
        overrides=body.overrides,
        conditions=conditions,
    )
    equipment_store.store_session_equipment(se)

    resp = _profile_to_response(profile)
    return SessionEquipmentResponse(
        session_id=session_id,
        profile_id=body.profile_id,
        profile_name=profile.name,
        overrides=body.overrides,
        tires=resp.tires,
        brakes=resp.brakes,
        suspension=resp.suspension,
        conditions=body.conditions,
    )


@router.get("/{session_id}/equipment", response_model=SessionEquipmentResponse)
async def get_session_equipment(session_id: str) -> SessionEquipmentResponse:
    """Get the effective equipment for a session."""
    se = equipment_store.get_session_equipment(session_id)
    if se is None:
        raise HTTPException(
            status_code=404, detail=f"No equipment assigned to session {session_id}"
        )
    profile = equipment_store.get_profile(se.profile_id)
    if profile is None:
        raise HTTPException(
            status_code=404, detail=f"Profile {se.profile_id} not found"
        )

    resp = _profile_to_response(profile)
    cond = None
    if se.conditions is not None:
        from backend.api.schemas.equipment import SessionConditionsSchema

        cond = SessionConditionsSchema(
            track_condition=se.conditions.track_condition.value,
            ambient_temp_c=se.conditions.ambient_temp_c,
            track_temp_c=se.conditions.track_temp_c,
            humidity_pct=se.conditions.humidity_pct,
            wind_speed_kmh=se.conditions.wind_speed_kmh,
            wind_direction_deg=se.conditions.wind_direction_deg,
            precipitation_mm=se.conditions.precipitation_mm,
            weather_source=se.conditions.weather_source,
        )
    return SessionEquipmentResponse(
        session_id=session_id,
        profile_id=se.profile_id,
        profile_name=profile.name,
        overrides=se.overrides,
        tires=resp.tires,
        brakes=resp.brakes,
        suspension=resp.suspension,
        conditions=cond,
    )
```

**Step 4: Register the router in main.py**

In `backend/api/main.py`, add to imports:
```python
from backend.api.routers import analysis, coaching, equipment, sessions, tracks, trends
```

Add to router registration section:
```python
app.include_router(equipment.router, prefix="/api/equipment", tags=["equipment"])
```

Add to lifespan startup (after coaching init):
```python
from backend.api.services.equipment_store import (
    init_equipment_dir,
    load_persisted_profiles,
    load_persisted_session_equipment,
)
init_equipment_dir(settings.equipment_data_dir)
n_profiles = load_persisted_profiles()
n_se = load_persisted_session_equipment()
if n_profiles or n_se:
    logger.info("Loaded %d equipment profile(s), %d session assignment(s)", n_profiles, n_se)
```

**Step 5: Add config setting**

In `backend/api/config.py`, add field to `Settings`:
```python
equipment_data_dir: str = "data/equipment"
```

**Step 6: Run tests**

Run: `pytest backend/tests/test_equipment_api.py -v`
Expected: PASS (all 4 tests)

**Step 7: Run full test suite + quality gates**

Run: `pytest tests/ backend/tests/ -v && ruff check backend/ cataclysm/ && mypy backend/ cataclysm/`

**Step 8: Commit**

```bash
git add backend/api/routers/equipment.py backend/api/schemas/equipment.py backend/api/main.py backend/api/config.py backend/tests/test_equipment_api.py
git commit -m "feat: add equipment CRUD API with profile and session endpoints"
```

---

### Task A6: Session List Filtering by Equipment

**Files:**
- Modify: `backend/api/routers/sessions.py` — add equipment info to session list
- Modify: `backend/api/schemas/session.py` — add equipment fields to SessionSummary
- Test: `backend/tests/test_equipment_api.py` — add filtering test

**Step 1: Add equipment fields to SessionSummary schema**

In `backend/api/schemas/session.py`, add to `SessionSummary`:
```python
tire_model: str | None = None
compound_category: str | None = None
equipment_profile_name: str | None = None
```

**Step 2: Populate equipment fields in session list endpoint**

In `backend/api/routers/sessions.py` `list_sessions()`, after building the `SessionSummary`, look up equipment:

```python
from backend.api.services import equipment_store

# Inside list_sessions, for each sd:
se = equipment_store.get_session_equipment(sd.session_id)
tire_model = None
compound_category = None
profile_name = None
if se is not None:
    profile = equipment_store.get_profile(se.profile_id)
    if profile is not None:
        tire_model = profile.tires.model
        compound_category = profile.tires.compound_category.value
        profile_name = profile.name
```

Then pass these into the SessionSummary constructor.

**Step 3: Write test**

Append to `backend/tests/test_equipment_api.py`:

```python
@pytest.mark.asyncio
async def test_session_list_includes_equipment(client: AsyncClient) -> None:
    """After assigning equipment to a session, it appears in the session list."""
    # This test requires a session to exist first — upload synthetic CSV
    # (Follow the pattern from backend/tests/conftest.py)
    from backend.tests.conftest import build_synthetic_csv

    csv_bytes = build_synthetic_csv()
    files = {"files": ("test.csv", csv_bytes, "text/csv")}
    resp = await client.post("/api/sessions/upload", files=files)
    session_id = resp.json()["session_ids"][0]

    # Create profile + assign
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = resp.json()["id"]
    await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id},
    )

    # Session list should include tire_model
    resp = await client.get("/api/sessions")
    items = resp.json()["items"]
    match = [s for s in items if s["session_id"] == session_id]
    assert len(match) == 1
    assert match[0]["tire_model"] == "Bridgestone RE-71RS"
```

**Step 4: Run tests and quality gates**

Run: `pytest backend/tests/ -v && ruff check backend/ && mypy backend/`

**Step 5: Commit**

```bash
git add backend/api/routers/sessions.py backend/api/schemas/session.py backend/tests/test_equipment_api.py
git commit -m "feat: include equipment info in session list for filtering"
```

---

## Phase B: Tire Lookup (Curated Table + UTQG API) + Source Badges

---

### Task B1: Curated Tire Database

**Files:**
- Create: `cataclysm/tire_db.py`
- Test: `tests/test_tire_db.py`

**Step 1: Write failing tests**

Create `tests/test_tire_db.py`:

```python
"""Tests for cataclysm.tire_db."""

from __future__ import annotations

from cataclysm.tire_db import search_curated_tires, get_curated_tire


class TestSearchCuratedTires:
    def test_search_by_model(self) -> None:
        results = search_curated_tires("RE-71RS")
        assert len(results) >= 1
        assert any("RE-71RS" in r.model for r in results)

    def test_search_case_insensitive(self) -> None:
        results = search_curated_tires("re-71rs")
        assert len(results) >= 1

    def test_search_by_brand(self) -> None:
        results = search_curated_tires("Bridgestone")
        assert len(results) >= 1

    def test_search_no_match(self) -> None:
        results = search_curated_tires("XYZNONEXISTENT")
        assert results == []


class TestGetCuratedTire:
    def test_get_known_tire(self) -> None:
        tire = get_curated_tire("bridgestone_re71rs")
        assert tire is not None
        assert tire.mu_source.value == "curated_table"

    def test_get_unknown_tire(self) -> None:
        assert get_curated_tire("nonexistent") is None
```

**Step 2: Implement curated tire database**

Create `cataclysm/tire_db.py`:

```python
"""Curated database of common track tires with estimated grip coefficients."""

from __future__ import annotations

from cataclysm.equipment import MuSource, TireCompoundCategory, TireSpec

# Key: slug identifier. Values: curated TireSpec instances.
# mu_source is CURATED_TABLE for all entries here.
_CURATED_TIRES: dict[str, TireSpec] = {
    "bridgestone_re71rs": TireSpec(
        model="Bridgestone Potenza RE-71RS",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.12,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Tire Rack test data + community track reports",
        brand="Bridgestone",
    ),
    "hankook_rs4": TireSpec(
        model="Hankook Ventus RS4",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.00,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Endurance-focused 200TW; moderate grip, long life",
        brand="Hankook",
    ),
    "continental_esc": TireSpec(
        model="Continental ExtremeContact Sport",
        compound_category=TireCompoundCategory.STREET,
        size="varies",
        treadwear_rating=340,
        estimated_mu=0.92,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Street-sport category; Tire Rack comparison data",
        brand="Continental",
    ),
    "yokohama_ad09": TireSpec(
        model="Yokohama Advan Apex V601 (AD09)",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.10,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="200TW super category; close to RE-71RS grip",
        brand="Yokohama",
    ),
    "toyo_r888r": TireSpec(
        model="Toyo Proxes R888R",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=100,
        estimated_mu=1.22,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="100TW semi-slick; track test data",
        brand="Toyo",
    ),
    "nankang_ar1": TireSpec(
        model="Nankang AR-1",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=80,
        estimated_mu=1.25,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Budget semi-slick; community track reports",
        brand="Nankang",
    ),
    "hoosier_r7": TireSpec(
        model="Hoosier R7",
        compound_category=TireCompoundCategory.R_COMPOUND,
        size="varies",
        treadwear_rating=40,
        estimated_mu=1.38,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="R-compound DOT slick; race data",
        brand="Hoosier",
    ),
    "falken_rt660": TireSpec(
        model="Falken Azenis RT660",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.02,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="200TW endurance; balanced grip/longevity",
        brand="Falken",
    ),
    "michelin_ps4s": TireSpec(
        model="Michelin Pilot Sport 4S",
        compound_category=TireCompoundCategory.STREET,
        size="varies",
        treadwear_rating=300,
        estimated_mu=0.95,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Premium street sport; excellent wet/dry balance",
        brand="Michelin",
    ),
    "bf_goodrich_rival_s": TireSpec(
        model="BFGoodrich g-Force Rival S 1.5",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.15,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Autocross/track 200TW; grippier than typical 200TW",
        brand="BFGoodrich",
    ),
}


def search_curated_tires(query: str, limit: int = 10) -> list[TireSpec]:
    """Search the curated tire database by model or brand name.

    Case-insensitive substring match on model and brand fields.
    """
    q = query.lower()
    results: list[TireSpec] = []
    for tire in _CURATED_TIRES.values():
        if q in tire.model.lower() or (tire.brand and q in tire.brand.lower()):
            results.append(tire)
            if len(results) >= limit:
                break
    return results


def get_curated_tire(slug: str) -> TireSpec | None:
    """Get a specific curated tire by its slug identifier."""
    return _CURATED_TIRES.get(slug)


def list_all_curated_tires() -> list[TireSpec]:
    """Return all curated tires sorted by model name."""
    return sorted(_CURATED_TIRES.values(), key=lambda t: t.model)
```

**Step 3: Run tests**

Run: `pytest tests/test_tire_db.py -v`

**Step 4: Quality gates and commit**

```bash
ruff check cataclysm/tire_db.py tests/test_tire_db.py && ruff format cataclysm/tire_db.py tests/test_tire_db.py && mypy cataclysm/tire_db.py
git add cataclysm/tire_db.py tests/test_tire_db.py
git commit -m "feat: add curated tire database with 10 common track tires"
```

---

### Task B2: UTQG API Client

**Files:**
- Create: `cataclysm/utqg_client.py`
- Test: `tests/test_utqg_client.py`

**Step 1: Write tests (mocking httpx)**

Create `tests/test_utqg_client.py`:

```python
"""Tests for cataclysm.utqg_client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cataclysm.utqg_client import lookup_treadwear


@pytest.mark.asyncio
async def test_lookup_finds_treadwear() -> None:
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"brandname": "BRIDGESTONE", "t_unifiedtm": "POTENZA RE-71RS", "utqg_treadwear": "200"}
    ]
    with patch("cataclysm.utqg_client.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value.get = AsyncMock(return_value=mock_response)

        result = await lookup_treadwear("Bridgestone", "RE-71RS")

    assert result is not None
    assert result == 200


@pytest.mark.asyncio
async def test_lookup_no_results() -> None:
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    with patch("cataclysm.utqg_client.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value.get = AsyncMock(return_value=mock_response)

        result = await lookup_treadwear("FakeBrand", "FakeModel")

    assert result is None


@pytest.mark.asyncio
async def test_lookup_handles_api_error() -> None:
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.json.side_effect = Exception("Server error")
    with patch("cataclysm.utqg_client.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value.get = AsyncMock(return_value=mock_response)

        result = await lookup_treadwear("Bridgestone", "RE-71RS")

    assert result is None
```

**Step 2: Implement UTQG client**

Create `cataclysm/utqg_client.py`:

```python
"""NHTSA UTQG API client for looking up tire treadwear ratings.

Uses the Socrata SODA endpoint at data.transportation.gov (dataset rfqx-2vcg).
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_UTQG_API_URL = "https://data.transportation.gov/resource/rfqx-2vcg.json"
_TIMEOUT_S = 10.0


async def lookup_treadwear(brand: str, model: str) -> int | None:
    """Look up UTQG treadwear rating for a tire.

    Parameters
    ----------
    brand:
        Manufacturer name (e.g., "Bridgestone").
    model:
        Tire model name or substring (e.g., "RE-71RS").

    Returns
    -------
    int | None
        Treadwear rating if found, None otherwise.
    """
    try:
        params = {
            "$where": (
                f"upper(brandname) like '%{brand.upper()}%' "
                f"AND upper(t_unifiedtm) like '%{model.upper()}%'"
            ),
            "$limit": 5,
            "$select": "brandname,t_unifiedtm,utqg_treadwear",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(_UTQG_API_URL, params=params)
            if resp.status_code != 200:
                logger.warning("UTQG API returned status %d", resp.status_code)
                return None

            data = resp.json()
            if not data:
                return None

            tw_str = data[0].get("utqg_treadwear", "")
            return int(tw_str) if tw_str.isdigit() else None
    except Exception:
        logger.warning("UTQG lookup failed for %s %s", brand, model, exc_info=True)
        return None
```

**Step 3: Run tests and commit**

```bash
pytest tests/test_utqg_client.py -v
ruff check cataclysm/utqg_client.py tests/test_utqg_client.py && ruff format cataclysm/utqg_client.py tests/test_utqg_client.py && mypy cataclysm/utqg_client.py
git add cataclysm/utqg_client.py tests/test_utqg_client.py
git commit -m "feat: add NHTSA UTQG API client for treadwear lookup"
```

---

### Task B3: Tire Search API Endpoint

**Files:**
- Modify: `backend/api/routers/equipment.py` — add `/tires/search` endpoint
- Test: `backend/tests/test_equipment_api.py` — add search test

**Step 1: Add the endpoint**

In `backend/api/routers/equipment.py`, add:

```python
@router.get("/tires/search")
async def search_tires(q: str = "") -> list[TireSpecSchema]:
    """Search for tires: curated database first, then UTQG formula fallback."""
    from cataclysm.tire_db import search_curated_tires

    if not q or len(q) < 2:
        return []

    # Search curated database first
    curated = search_curated_tires(q)
    results = [
        TireSpecSchema(
            model=t.model,
            compound_category=t.compound_category.value,
            size=t.size,
            treadwear_rating=t.treadwear_rating,
            estimated_mu=t.estimated_mu,
            mu_source=t.mu_source.value,
            mu_confidence=t.mu_confidence,
            brand=t.brand,
        )
        for t in curated
    ]
    return results
```

**Step 2: Write test and run**

```python
@pytest.mark.asyncio
async def test_tire_search(client: AsyncClient) -> None:
    resp = await client.get("/api/equipment/tires/search", params={"q": "RE-71RS"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "RE-71RS" in data[0]["model"]
    assert data[0]["mu_source"] == "curated_table"
```

**Step 3: Quality gates and commit**

```bash
pytest backend/tests/test_equipment_api.py -v
ruff check backend/ && mypy backend/
git add backend/api/routers/equipment.py backend/tests/test_equipment_api.py
git commit -m "feat: add tire search endpoint with curated database"
```

---

## Phase C: Weather Auto-Populate (Open-Meteo)

---

### Task C1: Open-Meteo Weather Client

**Files:**
- Create: `cataclysm/weather_client.py`
- Test: `tests/test_weather_client.py`

**Step 1: Write tests (mocking httpx)**

Create `tests/test_weather_client.py` — similar pattern to UTQG tests. Mock the Open-Meteo API response to return temperature, humidity, wind speed, precipitation.

**Step 2: Implement**

Create `cataclysm/weather_client.py`:

```python
"""Open-Meteo weather API client for auto-populating session conditions.

Uses the free Open-Meteo API (no API key required):
- Forecast API: sessions within last 7 days
- Historical API: sessions older than 7 days

Docs: https://open-meteo.com/en/docs
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from cataclysm.equipment import SessionConditions, TrackCondition

logger = logging.getLogger(__name__)

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
_TIMEOUT_S = 10.0


async def lookup_weather(
    lat: float,
    lon: float,
    session_datetime: datetime,
) -> SessionConditions | None:
    """Look up weather conditions for a track session.

    Parameters
    ----------
    lat, lon:
        Track GPS coordinates.
    session_datetime:
        Session date and approximate time (UTC).

    Returns
    -------
    SessionConditions | None
        Weather data if available, None on error.
    """
    try:
        now = datetime.now(tz=timezone.utc)
        days_ago = (now - session_datetime).days

        date_str = session_datetime.strftime("%Y-%m-%d")
        hour = session_datetime.hour

        if days_ago <= 7:
            url = _FORECAST_URL
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation",
                "start_date": date_str,
                "end_date": date_str,
                "timezone": "UTC",
            }
        else:
            url = _HISTORICAL_URL
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation",
                "start_date": date_str,
                "end_date": date_str,
                "timezone": "UTC",
            }

        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning("Open-Meteo returned status %d", resp.status_code)
                return None

            data = resp.json()
            hourly = data.get("hourly", {})

            # Find the closest hour in the response
            idx = min(hour, len(hourly.get("temperature_2m", [])) - 1)
            if idx < 0:
                return None

            temp = hourly.get("temperature_2m", [None])[idx]
            humidity = hourly.get("relative_humidity_2m", [None])[idx]
            wind = hourly.get("wind_speed_10m", [None])[idx]
            wind_dir = hourly.get("wind_direction_10m", [None])[idx]
            precip = hourly.get("precipitation", [None])[idx]

            # Infer track condition from precipitation
            if precip is not None and precip > 1.0:
                condition = TrackCondition.WET
            elif precip is not None and precip > 0.1:
                condition = TrackCondition.DAMP
            else:
                condition = TrackCondition.DRY

            return SessionConditions(
                track_condition=condition,
                ambient_temp_c=temp,
                humidity_pct=humidity,
                wind_speed_kmh=wind,
                wind_direction_deg=wind_dir,
                precipitation_mm=precip,
                weather_source="open-meteo",
            )
    except Exception:
        logger.warning(
            "Weather lookup failed for %.4f,%.4f on %s",
            lat, lon, session_datetime,
            exc_info=True,
        )
        return None
```

**Step 3: Run tests and commit**

```bash
pytest tests/test_weather_client.py -v
ruff check cataclysm/weather_client.py tests/test_weather_client.py && mypy cataclysm/weather_client.py
git add cataclysm/weather_client.py tests/test_weather_client.py
git commit -m "feat: add Open-Meteo weather client for session conditions"
```

---

### Task C2: Weather Lookup API Endpoint

**Files:**
- Modify: `backend/api/routers/equipment.py` — add `POST /api/weather/lookup`
- Test: `backend/tests/test_equipment_api.py`

**Step 1: Add weather endpoint to equipment router (or create a separate weather router)**

```python
@router.post("/weather/lookup")
async def weather_lookup(lat: float, lon: float, session_date: str, hour: int = 12):
    """Look up weather conditions for a track location and date."""
    from datetime import datetime, timezone
    from cataclysm.weather_client import lookup_weather

    dt = datetime.strptime(session_date, "%Y-%m-%d").replace(
        hour=hour, tzinfo=timezone.utc
    )
    result = await lookup_weather(lat, lon, dt)
    if result is None:
        return {"conditions": None, "message": "Weather data unavailable"}

    return {
        "conditions": {
            "track_condition": result.track_condition.value,
            "ambient_temp_c": result.ambient_temp_c,
            "humidity_pct": result.humidity_pct,
            "wind_speed_kmh": result.wind_speed_kmh,
            "wind_direction_deg": result.wind_direction_deg,
            "precipitation_mm": result.precipitation_mm,
            "weather_source": result.weather_source,
        }
    }
```

**Step 2: Test (mock the weather client) and commit**

```bash
pytest backend/tests/test_equipment_api.py -v
git add backend/api/routers/equipment.py backend/tests/test_equipment_api.py
git commit -m "feat: add weather lookup API endpoint"
```

---

## Phase D: Physics Integration (Equipment → VehicleParams → Optimal Profile)

---

### Task D1: Equipment-to-VehicleParams Mapping

**Files:**
- Modify: `cataclysm/equipment.py` — add `equipment_to_vehicle_params()` function
- Test: `tests/test_equipment.py` — add mapping tests

**Step 1: Write failing tests**

Append to `tests/test_equipment.py`:

```python
from cataclysm.equipment import equipment_to_vehicle_params
from cataclysm.velocity_profile import VehicleParams


class TestEquipmentToVehicleParams:
    def test_basic_mapping(self) -> None:
        tire = TireSpec(
            model="Test Tire",
            compound_category=TireCompoundCategory.SUPER_200TW,
            size="255/40R17",
            treadwear_rating=200,
            estimated_mu=1.10,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p1", name="Test", tires=tire)
        params = equipment_to_vehicle_params(profile)

        assert isinstance(params, VehicleParams)
        assert params.mu == 1.10
        assert params.max_lateral_g == 1.10

    def test_r_compound_higher_grip(self) -> None:
        tire = TireSpec(
            model="Hoosier R7",
            compound_category=TireCompoundCategory.R_COMPOUND,
            size="275/35R18",
            treadwear_rating=40,
            estimated_mu=1.35,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p2", name="Race", tires=tire)
        params = equipment_to_vehicle_params(profile)

        assert params.mu == 1.35
        assert params.max_decel_g > 1.0  # higher grip = higher braking

    def test_street_tire_lower_grip(self) -> None:
        tire = TireSpec(
            model="Street Tire",
            compound_category=TireCompoundCategory.STREET,
            size="225/45R17",
            treadwear_rating=400,
            estimated_mu=0.85,
            mu_source=MuSource.FORMULA_ESTIMATE,
            mu_confidence="UTQG formula",
        )
        profile = EquipmentProfile(id="p3", name="Street", tires=tire)
        params = equipment_to_vehicle_params(profile)

        assert params.mu == 0.85
        assert params.max_accel_g < 0.85  # accel limited by drivetrain, not just grip
```

**Step 2: Implement**

In `cataclysm/equipment.py`, add:

```python
from cataclysm.velocity_profile import VehicleParams

# Accel/decel scaling per compound category.
# max_accel_g is drivetrain-limited (doesn't scale 1:1 with grip).
# max_decel_g scales more directly with tire grip.
_CATEGORY_ACCEL_G: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 0.40,
    TireCompoundCategory.ENDURANCE_200TW: 0.50,
    TireCompoundCategory.SUPER_200TW: 0.55,
    TireCompoundCategory.TW_100: 0.60,
    TireCompoundCategory.R_COMPOUND: 0.65,
    TireCompoundCategory.SLICK: 0.70,
}


def equipment_to_vehicle_params(profile: EquipmentProfile) -> VehicleParams:
    """Convert an equipment profile to VehicleParams for the velocity solver.

    Maps tire grip (estimated_mu) to the friction model parameters.
    Brake compound affects max_decel_g scaling.
    """
    mu = profile.tires.estimated_mu
    category = profile.tires.compound_category
    max_accel_g = _CATEGORY_ACCEL_G.get(category, 0.50)

    # Decel scales more directly with tire grip (brake torque is rarely limiting)
    max_decel_g = mu * 0.95  # slight reduction for real-world brake efficiency

    return VehicleParams(
        mu=mu,
        max_accel_g=max_accel_g,
        max_decel_g=max_decel_g,
        max_lateral_g=mu,
        top_speed_mps=80.0,
    )
```

**Step 3: Run tests and commit**

```bash
pytest tests/test_equipment.py -v
ruff check cataclysm/equipment.py && mypy cataclysm/equipment.py
git add cataclysm/equipment.py tests/test_equipment.py
git commit -m "feat: add equipment-to-VehicleParams mapping for physics solver"
```

---

### Task D2: Wire Equipment into Pipeline

**Files:**
- Modify: `backend/api/services/pipeline.py` — use equipment params when computing optimal profile
- Modify: `backend/api/routers/analysis.py` — pass equipment params to ideal-lap endpoint
- Test: `backend/tests/test_equipment_api.py`

**Step 1: Modify pipeline to accept optional VehicleParams**

In the function that calls `compute_optimal_profile`, check if the session has equipment assigned. If so, convert it to VehicleParams and pass it.

```python
# In pipeline.py or analysis.py where compute_optimal_profile is called:
from cataclysm.equipment import equipment_to_vehicle_params
from backend.api.services import equipment_store

se = equipment_store.get_session_equipment(session_id)
vehicle_params = None
if se is not None:
    profile = equipment_store.get_profile(se.profile_id)
    if profile is not None:
        vehicle_params = equipment_to_vehicle_params(profile)

optimal = compute_optimal_profile(curvature_result, params=vehicle_params)
```

**Step 2: Test that equipment changes the optimal profile**

```python
@pytest.mark.asyncio
async def test_equipment_affects_optimal_profile(client: AsyncClient) -> None:
    """Assigning a low-grip tire should produce a slower optimal profile."""
    # Upload session, get ideal lap with default params
    # Then assign a street tire profile, get ideal lap again
    # Assert the street-tire optimal is slower
    ...
```

**Step 3: Run tests and commit**

```bash
pytest backend/tests/ tests/ -v
git add backend/api/services/pipeline.py backend/api/routers/analysis.py backend/tests/test_equipment_api.py
git commit -m "feat: wire equipment profiles into velocity solver pipeline"
```

---

## Phase E: Coaching Context (Pass Equipment + Conditions to Claude Prompt)

---

### Task E1: Format Equipment for Coaching Prompt

**Files:**
- Modify: `cataclysm/coaching.py` — add `_format_equipment_context()` helper
- Modify: `cataclysm/coaching.py` — pass equipment context in `_build_coaching_prompt()`
- Test: `tests/test_coaching.py` — add test for equipment context formatting

**Step 1: Write failing test**

```python
def test_format_equipment_context() -> None:
    from cataclysm.coaching import _format_equipment_context
    from cataclysm.equipment import (
        EquipmentProfile,
        MuSource,
        SessionConditions,
        TireCompoundCategory,
        TireSpec,
        TrackCondition,
    )

    tire = TireSpec(
        model="Bridgestone RE-71RS",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="255/40R17",
        treadwear_rating=200,
        estimated_mu=1.10,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Track test aggregate",
    )
    profile = EquipmentProfile(id="p1", name="Track Setup", tires=tire)
    conditions = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=28.0,
    )

    text = _format_equipment_context(profile, conditions)
    assert "RE-71RS" in text
    assert "1.10" in text
    assert "DRY" in text or "dry" in text
    assert "28" in text
```

**Step 2: Implement**

In `cataclysm/coaching.py`, add:

```python
def _format_equipment_context(
    profile: EquipmentProfile | None,
    conditions: SessionConditions | None,
) -> str:
    """Format equipment and conditions as context for the coaching prompt."""
    if profile is None and conditions is None:
        return ""

    lines = ["\n## Vehicle Equipment & Conditions"]
    if profile is not None:
        lines.append(f"**Tires:** {profile.tires.model} ({profile.tires.compound_category.value})")
        lines.append(f"  - Grip coefficient (mu): {profile.tires.estimated_mu:.2f} [{profile.tires.mu_source.value}]")
        if profile.tires.pressure_psi is not None:
            lines.append(f"  - Pressure: {profile.tires.pressure_psi} psi")
        if profile.brakes is not None and profile.brakes.compound:
            lines.append(f"**Brakes:** {profile.brakes.compound}")
    if conditions is not None:
        lines.append(f"**Track condition:** {conditions.track_condition.value}")
        if conditions.ambient_temp_c is not None:
            lines.append(f"**Ambient temp:** {conditions.ambient_temp_c:.0f}°C")
        if conditions.humidity_pct is not None:
            lines.append(f"**Humidity:** {conditions.humidity_pct:.0f}%")

    return "\n".join(lines)
```

Then in `_build_coaching_prompt()` or `generate_coaching_report()`, accept optional `equipment_profile` and `conditions` parameters and include the formatted context.

**Step 3: Update the coaching router to pass equipment**

In `backend/api/routers/coaching.py`, when generating a report, look up the session's equipment and pass it through.

**Step 4: Run tests and commit**

```bash
pytest tests/test_coaching.py -v
ruff check cataclysm/coaching.py && mypy cataclysm/coaching.py
git add cataclysm/coaching.py backend/api/routers/coaching.py tests/test_coaching.py
git commit -m "feat: pass equipment context to AI coaching prompt"
```

---

## Verification

After all phases, run the full quality gate suite:

```bash
pytest tests/ backend/tests/ -v --tb=short
ruff check cataclysm/ tests/ backend/
ruff format cataclysm/ tests/ backend/
mypy cataclysm/ backend/
```

All must pass with zero errors.
