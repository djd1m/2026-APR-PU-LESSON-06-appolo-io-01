"""Sequences router — CRUD for email sequences and steps."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Sequence, SequenceStep, User, get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/sequences", tags=["Sequences"])


class StepCreate(BaseModel):
    step_order: int
    subject_template: str
    body_template: str
    delay_days: int = 0


class SequenceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    steps: List[StepCreate] = []


class StepResponse(BaseModel):
    id: int
    step_order: int
    subject_template: str
    body_template: str
    delay_days: int

    model_config = {"from_attributes": True}


class SequenceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SequenceDetailResponse(SequenceResponse):
    steps: List[StepResponse] = []


@router.get("/", response_model=List[SequenceResponse])
async def list_sequences(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Sequence)
        .where(Sequence.created_by == current_user.id)
        .offset(offset).limit(limit)
    )
    return result.scalars().all()


@router.get("/{sequence_id}", response_model=SequenceDetailResponse)
async def get_sequence(sequence_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    steps_result = await db.execute(
        select(SequenceStep).where(SequenceStep.sequence_id == sequence_id).order_by(SequenceStep.step_order)
    )
    steps = steps_result.scalars().all()
    return SequenceDetailResponse(
        id=seq.id, name=seq.name, description=seq.description,
        is_active=seq.is_active, created_at=seq.created_at,
        steps=[StepResponse.model_validate(s) for s in steps],
    )


@router.post("/", response_model=SequenceResponse, status_code=201)
async def create_sequence(
    payload: SequenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seq = Sequence(name=payload.name, description=payload.description, created_by=current_user.id)
    db.add(seq)
    await db.flush()
    for step_data in payload.steps:
        step = SequenceStep(sequence_id=seq.id, **step_data.model_dump())
        db.add(step)
    await db.commit()
    await db.refresh(seq)
    return seq


@router.post("/{sequence_id}/steps", response_model=StepResponse, status_code=201)
async def add_step(
    sequence_id: int,
    payload: StepCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Sequence not found")
    step = SequenceStep(sequence_id=sequence_id, **payload.model_dump())
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


@router.patch("/{sequence_id}/toggle")
async def toggle_sequence(sequence_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    seq.is_active = not seq.is_active
    await db.commit()
    return {"id": seq.id, "is_active": seq.is_active}
