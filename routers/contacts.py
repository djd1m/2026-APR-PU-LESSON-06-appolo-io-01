"""Contacts router — CRUD, scoring, enrichment with credit deduction."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Contact, Company, User, Activity, CreditTransaction, get_db
from routers.auth import get_current_user
from services.scoring import scoring_service

router = APIRouter(prefix="/contacts", tags=["Contacts"])


class ContactCreate(BaseModel):
    company_id: Optional[int] = None
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    seniority: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None


class ContactResponse(BaseModel):
    id: int
    company_id: Optional[int]
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    title: Optional[str]
    seniority: Optional[str]
    linkedin_url: Optional[str]
    phone: Optional[str]
    score: Optional[int]
    score_version: Optional[str]
    email_confidence: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class ScoreResponse(BaseModel):
    score: int
    breakdown: dict
    version: str


@router.get("/", response_model=List[ContactResponse])
async def list_contacts(
    company_id: Optional[int] = Query(None),
    seniority: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search by name or email"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Contact)
    if company_id:
        query = query.where(Contact.company_id == company_id)
    if seniority:
        query = query.where(Contact.seniority == seniority)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            (Contact.email.ilike(pattern)) |
            (Contact.first_name.ilike(pattern)) |
            (Contact.last_name.ilike(pattern))
        )
    result = await db.execute(query.offset(offset).limit(limit))
    return result.scalars().all()


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(contact_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.post("/", response_model=ContactResponse, status_code=201)
async def create_contact(payload: ContactCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    existing = await db.execute(select(Contact).where(Contact.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Contact with this email already exists")
    contact = Contact(**payload.model_dump(exclude_none=True))
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.post("/{contact_id}/score", response_model=ScoreResponse)
async def score_contact(contact_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    acts = await db.execute(select(Activity).where(Activity.contact_id == contact_id))
    activities = [{"activity_type": a.activity_type.value, "occurred_at": a.occurred_at.isoformat()} for a in acts.scalars().all()]

    contact_dict = {
        "first_name": contact.first_name, "last_name": contact.last_name,
        "title": contact.title, "seniority": contact.seniority,
        "linkedin_url": contact.linkedin_url, "phone": contact.phone,
        "email_confidence": contact.email_confidence,
    }
    score_result = scoring_service.score_contact(contact_dict, activities)

    contact.score = score_result["score"]
    contact.score_version = score_result["version"]
    await db.commit()

    return score_result


@router.post("/{contact_id}/enrich", response_model=ContactResponse)
async def enrich_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enrich contact data (stub). Deducts 1 credit atomically."""
    result = await db.execute(
        update(User)
        .where(User.id == current_user.id, User.credits >= 1)
        .values(credits=User.credits - 1)
        .returning(User.credits)
    )
    new_credits = result.scalar_one_or_none()
    if new_credits is None:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    tx = CreditTransaction(user_id=current_user.id, amount=-1, reason=f"enrich_contact:{contact_id}")
    db.add(tx)

    contact_result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = contact_result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    from datetime import datetime, timezone
    contact.enriched_at = datetime.now(timezone.utc)
    contact.email_confidence = 0.85

    await db.commit()
    await db.refresh(contact)
    return contact
