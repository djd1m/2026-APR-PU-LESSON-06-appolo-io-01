"""Sequences router — CRUD for email sequences and steps."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.database import Sequence, SequenceStep, Contact, Activity, ActivityType, User, get_db
from routers.auth import get_current_user
from services.email_sender import email_sender

logger = logging.getLogger(__name__)

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


class AIGenerateRequest(BaseModel):
    goal: str


class AIGenerateStepResponse(BaseModel):
    step_order: int
    subject_template: str
    body_template: str
    delay_days: int


class AIGenerateResponse(BaseModel):
    name: str
    description: str
    steps: List[AIGenerateStepResponse]


SEQUENCE_GEN_PROMPT = """\
You are an expert B2B cold email sequence writer for the Russian market.
Given a user's goal, generate a complete email sequence.

Return a JSON object with:
- "name": short sequence name (Russian, 3-5 words)
- "description": one-line description (Russian)
- "steps": array of 3 steps, each with:
  - "step_order": 1, 2, or 3
  - "subject_template": email subject (Russian). Use {first_name} and {company} as placeholders.
  - "body_template": email body (Russian, 3-5 sentences). Use {first_name} and {company} as placeholders. Be professional but friendly.
  - "delay_days": 0 for step 1, 3 for step 2, 5 for step 3

Make emails concise, personalized, and with clear call-to-action.
Return ONLY valid JSON, no explanation.\
"""


@router.post("/ai-generate", response_model=AIGenerateResponse)
async def ai_generate_sequence(
    payload: AIGenerateRequest,
    _: User = Depends(get_current_user),
):
    """Generate sequence content via GPT-4 based on user's goal."""
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT,
    )
    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SEQUENCE_GEN_PROMPT},
                {"role": "user", "content": payload.goal},
            ],
            temperature=0.7,
            max_tokens=800,
        )
        raw = response.choices[0].message.content or "{}"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(raw)
        return AIGenerateResponse(**result)
    except Exception as exc:
        logger.warning("AI sequence generation failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"Не удалось сгенерировать: {exc}")


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


class SendEmailRequest(BaseModel):
    contact_id: int
    step_order: int = 1


class SendEmailResponse(BaseModel):
    success: bool
    resend_id: Optional[str] = None
    error: Optional[str] = None
    to: str
    subject: str


@router.post("/{sequence_id}/send", response_model=SendEmailResponse)
async def send_sequence_email(
    sequence_id: int,
    payload: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a specific sequence step email to a contact via Resend."""
    if not email_sender.is_configured():
        raise HTTPException(status_code=503, detail="Resend API key not configured. Add RESEND_API_KEY to .env")

    # Get sequence step
    step_result = await db.execute(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id, SequenceStep.step_order == payload.step_order)
    )
    step = step_result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail=f"Step {payload.step_order} not found in sequence {sequence_id}")

    # Get contact with company
    contact_result = await db.execute(select(Contact).where(Contact.id == payload.contact_id))
    contact = contact_result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Personalize templates
    variables = {
        "first_name": contact.first_name or "",
        "last_name": contact.last_name or "",
        "email": contact.email,
        "title": contact.title or "",
        "company": "",
    }
    try:
        from models.database import Company
        if contact.company_id:
            company_result = await db.execute(select(Company).where(Company.id == contact.company_id))
            company = company_result.scalar_one_or_none()
            if company:
                variables["company"] = company.name
    except Exception:
        pass

    subject = step.subject_template.format_map({k: v for k, v in variables.items()})
    body = step.body_template.format_map({k: v for k, v in variables.items()})

    # Send via Resend
    result = email_sender.send_email(to=contact.email, subject=subject, body=body)

    # Log activity
    activity = Activity(
        contact_id=contact.id,
        company_id=contact.company_id,
        activity_type=ActivityType.email_sent,
        metadata_={
            "sequence_id": sequence_id,
            "step_order": payload.step_order,
            "subject": subject,
            "resend_id": result.resend_id,
            "success": result.success,
        },
    )
    db.add(activity)
    await db.commit()

    return SendEmailResponse(
        success=result.success,
        resend_id=result.resend_id,
        error=result.error,
        to=contact.email,
        subject=subject,
    )


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.patch("/{sequence_id}", response_model=SequenceResponse)
async def update_sequence(
    sequence_id: int,
    payload: SequenceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(seq, field, value)
    await db.commit()
    await db.refresh(seq)
    return seq


@router.delete("/{sequence_id}", status_code=204)
async def delete_sequence(sequence_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    await db.delete(seq)
    await db.commit()


@router.patch("/{sequence_id}/toggle")
async def toggle_sequence(sequence_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    seq.is_active = not seq.is_active
    await db.commit()
    return {"id": seq.id, "is_active": seq.is_active}
