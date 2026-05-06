"""Enrollments router — enroll contacts in sequences, advance, manage status."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Enrollment, EnrollmentStatus, Contact, Sequence, SequenceStep, get_db
from routers.auth import get_current_user, User

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


class EnrollRequest(BaseModel):
    contact_id: int
    sequence_id: int


class EnrollmentResponse(BaseModel):
    id: int
    contact_id: int
    sequence_id: int
    current_step: int
    status: EnrollmentStatus
    enrolled_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StatusUpdate(BaseModel):
    status: EnrollmentStatus


@router.post("/", response_model=EnrollmentResponse, status_code=201)
async def enroll_contact(payload: EnrollRequest, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    contact = (await db.execute(select(Contact).where(Contact.id == payload.contact_id))).scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    seq = (await db.execute(select(Sequence).where(Sequence.id == payload.sequence_id))).scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    if not seq.is_active:
        raise HTTPException(status_code=422, detail="Sequence is not active")
    existing = (await db.execute(
        select(Enrollment).where(Enrollment.contact_id == payload.contact_id, Enrollment.sequence_id == payload.sequence_id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Contact already enrolled in this sequence")
    enrollment = Enrollment(contact_id=payload.contact_id, sequence_id=payload.sequence_id, current_step=1, status=EnrollmentStatus.active)
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.get("/", response_model=List[EnrollmentResponse])
async def list_enrollments(
    contact_id: Optional[int] = Query(None),
    sequence_id: Optional[int] = Query(None),
    enrollment_status: Optional[EnrollmentStatus] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Enrollment)
    if contact_id:
        query = query.where(Enrollment.contact_id == contact_id)
    if sequence_id:
        query = query.where(Enrollment.sequence_id == sequence_id)
    if enrollment_status:
        query = query.where(Enrollment.status == enrollment_status)
    result = await db.execute(query.offset(offset).limit(limit))
    return result.scalars().all()


@router.post("/{enrollment_id}/advance", response_model=EnrollmentResponse)
async def advance_enrollment(enrollment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    enrollment = (await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))).scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if enrollment.status not in (EnrollmentStatus.active, EnrollmentStatus.pending):
        raise HTTPException(status_code=422, detail=f"Cannot advance enrollment with status '{enrollment.status.value}'")
    steps = (await db.execute(select(SequenceStep).where(SequenceStep.sequence_id == enrollment.sequence_id))).scalars().all()
    max_step = max((s.step_order for s in steps), default=0)
    if enrollment.current_step >= max_step:
        enrollment.status = EnrollmentStatus.completed
        enrollment.completed_at = datetime.now(timezone.utc)
    else:
        enrollment.current_step += 1
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.put("/{enrollment_id}/status", response_model=EnrollmentResponse)
async def update_status(enrollment_id: int, payload: StatusUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    enrollment = (await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))).scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    enrollment.status = payload.status
    if payload.status == EnrollmentStatus.completed:
        enrollment.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment
