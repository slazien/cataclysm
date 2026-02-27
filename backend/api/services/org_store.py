"""Organization (HPDE club) management service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import Organization, OrgEvent, OrgMembership, User


async def create_org(
    db: AsyncSession,
    name: str,
    slug: str,
    owner_id: str,
    logo_url: str | None,
    brand_color: str | None,
) -> str:
    """Create an organization and add the creator as owner. Returns org ID."""
    org_id = str(uuid.uuid4())[:12]
    db.add(
        Organization(id=org_id, name=name, slug=slug, logo_url=logo_url, brand_color=brand_color)
    )
    await db.flush()  # ensure Organization row exists before FK reference
    db.add(OrgMembership(org_id=org_id, user_id=owner_id, role="owner"))
    await db.flush()
    return org_id


async def get_org_by_slug(db: AsyncSession, slug: str) -> dict | None:
    """Get an organization by its slug."""
    result = await db.execute(select(Organization).where(Organization.slug == slug))
    org = result.scalar_one_or_none()
    if org is None:
        return None

    count_result = await db.execute(
        select(func.count()).select_from(OrgMembership).where(OrgMembership.org_id == org.id)
    )
    member_count = count_result.scalar() or 0

    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "logo_url": org.logo_url,
        "brand_color": org.brand_color,
        "member_count": member_count,
    }


async def get_user_orgs(db: AsyncSession, user_id: str) -> list[dict]:
    """Get all organizations a user belongs to."""
    result = await db.execute(
        select(Organization, OrgMembership.role)
        .join(OrgMembership, OrgMembership.org_id == Organization.id)
        .where(OrgMembership.user_id == user_id)
    )
    orgs = []
    for row in result.all():
        org, role = row
        count_result = await db.execute(
            select(func.count()).select_from(OrgMembership).where(OrgMembership.org_id == org.id)
        )
        member_count = count_result.scalar() or 0
        orgs.append(
            {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "logo_url": org.logo_url,
                "brand_color": org.brand_color,
                "member_count": member_count,
            }
        )
    return orgs


async def get_org_members(db: AsyncSession, org_id: str) -> list[dict]:
    """Get all members of an organization."""
    result = await db.execute(
        select(OrgMembership, User)
        .join(User, User.id == OrgMembership.user_id)
        .where(OrgMembership.org_id == org_id)
    )
    members = []
    for row in result.all():
        membership, user = row
        members.append(
            {
                "user_id": user.id,
                "name": user.name,
                "email": user.email,
                "role": membership.role,
                "run_group": membership.run_group,
                "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
            }
        )
    return members


async def add_member(
    db: AsyncSession, org_id: str, user_id: str, role: str, run_group: str | None
) -> bool:
    """Add a member to an organization. Returns False if already a member."""
    existing = await db.execute(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id, OrgMembership.user_id == user_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    db.add(OrgMembership(org_id=org_id, user_id=user_id, role=role, run_group=run_group))
    await db.flush()
    return True


async def remove_member(db: AsyncSession, org_id: str, user_id: str) -> bool:
    """Remove a member from an organization."""
    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id, OrgMembership.user_id == user_id
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        return False

    await db.delete(membership)
    await db.flush()
    return True


async def check_org_role(db: AsyncSession, org_id: str, user_id: str, roles: set[str]) -> bool:
    """Check if a user has one of the specified roles in an org."""
    result = await db.execute(
        select(OrgMembership.role).where(
            OrgMembership.org_id == org_id, OrgMembership.user_id == user_id
        )
    )
    role = result.scalar_one_or_none()
    return role is not None and role in roles


async def create_event(
    db: AsyncSession,
    org_id: str,
    name: str,
    track_name: str,
    event_date_str: str,
    run_groups: list[str] | None,
) -> str:
    """Create an org event. Returns event ID."""
    event_id = str(uuid.uuid4())[:12]
    event_date = datetime.fromisoformat(event_date_str).replace(tzinfo=UTC)
    db.add(
        OrgEvent(
            id=event_id,
            org_id=org_id,
            name=name,
            track_name=track_name,
            event_date=event_date,
            run_groups=run_groups,
        )
    )
    await db.flush()
    return event_id


async def get_org_events(db: AsyncSession, org_id: str) -> list[dict]:
    """Get all events for an organization."""
    result = await db.execute(
        select(OrgEvent).where(OrgEvent.org_id == org_id).order_by(OrgEvent.event_date)
    )
    events = []
    for ev in result.scalars().all():
        events.append(
            {
                "id": ev.id,
                "org_id": ev.org_id,
                "name": ev.name,
                "track_name": ev.track_name,
                "event_date": ev.event_date.isoformat() if ev.event_date else None,
                "run_groups": ev.run_groups,
            }
        )
    return events


async def delete_event(db: AsyncSession, event_id: str, org_id: str) -> bool:
    """Delete an event from an organization."""
    result = await db.execute(
        select(OrgEvent).where(OrgEvent.id == event_id, OrgEvent.org_id == org_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        return False
    await db.delete(event)
    await db.flush()
    return True
