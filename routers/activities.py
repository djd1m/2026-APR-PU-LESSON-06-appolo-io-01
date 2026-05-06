"""Activities router — log, timeline, aggregate counts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Activity, ActivityType, Contact, get_db
from routers.auth import get_current_user, User

router = APIRouter(prefix="/activities", tags=["Activities"])


class ActivityLog(BaseModel):
    contact_id: int
    company_id: Optional[int] = None
    enrollment_id: Optional[int] = None
    activity_type: ActivityType
    metadata: Optional[dict] = None
    occurred_at: Optional[datetime] = None


class ActivityResponse(BaseModel):
    id: int
    contact_id: int
    company_id: Optional[int]
    enrollment_id: Optional[int]
    activity_type: ActivityType
    occurred_at: str
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/", response_model=ActivityResponse, status_code=201)
async def log_activity(payload: ActivityLog, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    contact = (await db.execute(select(Contact).where(Contact.id == payload.contact_id))).scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    activity = Activity(
        contact_id=payload.contact_id,
        company_id=payload.company_id,
        enrollment_id=payload.enrollment_id,
        activity_type=payload.activity_type,
        metadata_=payload.metadata,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


@router.get("/timeline/{contact_id}", response_model=List[ActivityResponse])
async def get_timeline(
    contact_id: int,
    activity_type: Optional[ActivityType] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Activity).where(Activity.contact_id == contact_id).order_by(Activity.occurred_at.desc())
    if activity_type:
        query = query.where(Activity.activity_type == activity_type)
    result = await db.execute(query.offset(offset).limit(limit))
    return result.scalars().all()


@router.get("/aggregate/{contact_id}")
async def aggregate_activities(contact_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(Activity.activity_type, func.count(Activity.id).label("count"))
        .where(Activity.contact_id == contact_id)
        .group_by(Activity.activity_type)
    )
    return {"contact_id": contact_id, "counts": {row.activity_type.value: row.count for row in result.all()}}
