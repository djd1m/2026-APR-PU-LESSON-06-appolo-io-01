"""Companies router — search, CRUD, filters (ОКВЭД, region, revenue, intent)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Company, IntentSignal, get_db
from routers.auth import get_current_user, User

router = APIRouter(prefix="/companies", tags=["Companies"])


class CompanyCreate(BaseModel):
    inn: Optional[str] = None
    name: str
    okved_main: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    employee_count: Optional[int] = None
    revenue_range: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None


class CompanyResponse(BaseModel):
    id: int
    inn: Optional[str]
    name: str
    okved_main: Optional[str]
    industry: Optional[str]
    region: Optional[str]
    city: Optional[str]
    employee_count: Optional[int]
    revenue_range: Optional[str]
    website: Optional[str]
    intent_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanySearchResponse(BaseModel):
    items: List[CompanyResponse]
    total: int
    page: int
    per_page: int


@router.get("/search", response_model=CompanySearchResponse)
async def search_companies(
    q: Optional[str] = Query(None, description="Full-text search on company name"),
    okved: Optional[str] = Query(None, description="ОКВЭД code prefix"),
    region: Optional[str] = Query(None),
    revenue_range: Optional[str] = Query(None),
    employee_min: Optional[int] = Query(None),
    employee_max: Optional[int] = Query(None),
    intent_min: Optional[int] = Query(None, description="Minimum intent score"),
    sort_by: str = Query("intent_score", enum=["name", "intent_score", "employee_count", "created_at"]),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Company)

    if q:
        query = query.where(Company.name.ilike(f"%{q}%"))
    if okved:
        query = query.where(Company.okved_main.like(f"{okved}%"))
    if region:
        query = query.where(Company.region.ilike(f"%{region}%"))
    if revenue_range:
        query = query.where(Company.revenue_range == revenue_range)
    if employee_min is not None:
        query = query.where(Company.employee_count >= employee_min)
    if employee_max is not None:
        query = query.where(Company.employee_count <= employee_max)
    if intent_min is not None:
        query = query.where(Company.intent_score >= intent_min)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    sort_col = getattr(Company, sort_by, Company.intent_score)
    query = query.order_by(sort_col.desc()).offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    items = result.scalars().all()

    return CompanySearchResponse(
        items=[CompanyResponse.model_validate(c) for c in items],
        total=total, page=page, per_page=per_page,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/", response_model=CompanyResponse, status_code=201)
async def create_company(payload: CompanyCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    company = Company(**payload.model_dump(exclude_none=True))
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company
