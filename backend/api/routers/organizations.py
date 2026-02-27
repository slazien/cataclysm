"""Organization (HPDE club) endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.organization import (
    AddMemberRequest,
    EventCreate,
    EventListResponse,
    EventSchema,
    MemberListResponse,
    MemberSchema,
    OrgCreate,
    OrgListResponse,
    OrgSummary,
)
from backend.api.services.org_store import (
    add_member,
    check_org_role,
    create_event,
    create_org,
    delete_event,
    get_org_by_slug,
    get_org_events,
    get_org_members,
    get_user_orgs,
    remove_member,
)

router = APIRouter()


@router.post("", response_model=OrgSummary)
async def create_organization(
    body: OrgCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgSummary:
    """Create a new organization. The creator becomes the owner."""
    org_id = await create_org(
        db, body.name, body.slug, current_user.user_id, body.logo_url, body.brand_color
    )
    await db.commit()
    return OrgSummary(
        id=org_id,
        name=body.name,
        slug=body.slug,
        logo_url=body.logo_url,
        brand_color=body.brand_color,
        member_count=1,
    )


@router.get("", response_model=OrgListResponse)
async def list_user_orgs(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgListResponse:
    """List organizations the current user belongs to."""
    orgs = await get_user_orgs(db, current_user.user_id)
    return OrgListResponse(organizations=[OrgSummary(**o) for o in orgs])


@router.get("/{slug}", response_model=OrgSummary)
async def get_organization(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgSummary:
    """Get an organization by slug."""
    org = await get_org_by_slug(db, slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrgSummary(**org)


@router.get("/{slug}/members", response_model=MemberListResponse)
async def list_members(
    slug: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemberListResponse:
    """List members of an organization. Requires membership."""
    org = await get_org_by_slug(db, slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    is_member = await check_org_role(
        db, org["id"], current_user.user_id, {"owner", "instructor", "student"}
    )
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    members = await get_org_members(db, org["id"])
    return MemberListResponse(members=[MemberSchema(**m) for m in members])


@router.post("/{slug}/members")
async def add_org_member(
    slug: str,
    body: AddMemberRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Add a member to an organization. Requires owner or instructor role."""
    org = await get_org_by_slug(db, slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    has_permission = await check_org_role(
        db, org["id"], current_user.user_id, {"owner", "instructor"}
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    success = await add_member(db, org["id"], body.user_id, body.role, body.run_group)
    if not success:
        raise HTTPException(status_code=409, detail="User is already a member")

    await db.commit()
    return {"status": "added"}


@router.delete("/{slug}/members/{user_id}")
async def remove_org_member(
    slug: str,
    user_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Remove a member from an organization. Requires owner role."""
    org = await get_org_by_slug(db, slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    is_owner = await check_org_role(db, org["id"], current_user.user_id, {"owner"})
    if not is_owner:
        raise HTTPException(status_code=403, detail="Only org owners can remove members")

    success = await remove_member(db, org["id"], user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.commit()
    return {"status": "removed"}


@router.post("/{slug}/events", response_model=EventSchema)
async def create_org_event(
    slug: str,
    body: EventCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EventSchema:
    """Create an event for an organization. Requires owner or instructor role."""
    org = await get_org_by_slug(db, slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    has_permission = await check_org_role(
        db, org["id"], current_user.user_id, {"owner", "instructor"}
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    event_id = await create_event(
        db, org["id"], body.name, body.track_name, body.event_date, body.run_groups
    )
    await db.commit()
    return EventSchema(
        id=event_id,
        org_id=org["id"],
        name=body.name,
        track_name=body.track_name,
        event_date=body.event_date,
        run_groups=body.run_groups,
    )


@router.get("/{slug}/events", response_model=EventListResponse)
async def list_org_events(
    slug: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EventListResponse:
    """List events for an organization. Requires membership."""
    org = await get_org_by_slug(db, slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    is_member = await check_org_role(
        db, org["id"], current_user.user_id, {"owner", "instructor", "student"}
    )
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    events = await get_org_events(db, org["id"])
    return EventListResponse(events=[EventSchema(**e) for e in events])


@router.delete("/{slug}/events/{event_id}")
async def delete_org_event(
    slug: str,
    event_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Delete an event. Requires owner or instructor role."""
    org = await get_org_by_slug(db, slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    has_permission = await check_org_role(
        db, org["id"], current_user.user_id, {"owner", "instructor"}
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    success = await delete_event(db, event_id, org["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")

    await db.commit()
    return {"status": "deleted"}
