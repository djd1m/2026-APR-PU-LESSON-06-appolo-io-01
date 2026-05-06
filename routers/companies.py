"""Companies router — search, CRUD, filters (ОКВЭД, region, revenue, intent)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.database import Company, IntentSignal, get_db
from routers.auth import get_current_user, User

logger = logging.getLogger(__name__)

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


class AISearchRequest(BaseModel):
    query: str


AI_SEARCH_SYSTEM_PROMPT = """\
You are a search query parser for a Russian B2B company database.
Given a natural language query in Russian or English, extract structured search filters.

Available filters (return ONLY those that apply):
- "q": partial company name match (string). Use for searching by company name keywords.
- "okved": ОКВЭД code prefix (string). Use SHORT prefixes to match more companies.
  IMPORTANT: For broad industry searches use 1-2 digit prefixes.
  Common ОКВЭД prefixes in our database:
  06 = нефтедобыча, 19 = нефтепереработка, 24 = металлургия,
  35 = энергетика, 46 = оптовая торговля, 47 = розничная торговля,
  49 = транспорт, 51 = авиация, 61 = телеком,
  64 = финансы/IT-холдинги (Сбербанк=64.19, Яндекс/VK/МТС=64.20),
  68 = недвижимость, 84 = госуправление
  NOTE: Major Russian IT companies (Яндекс, VK) are registered under 64.20, NOT 62.
  For "IT компании" prefer using "q" with keywords or multiple okved prefixes.
- "region": region name in Russian (string), e.g. "Москва", "Санкт-Петербург"
- "revenue_range": one of "0-10M", "10-50M", "50-200M", "200-500M", "500M+", "10B+"
- "employee_min": minimum employee count (integer)
- "employee_max": maximum employee count (integer)
- "intent_min": minimum intent score 0-100 (integer)

Strategy tips:
- For broad queries like "IT компании" or "tech companies", use "q" with a name keyword
  rather than okved, since IT companies may have various ОКВЭД codes.
- For industry queries like "банки", "нефть", "металлургия" — use okved prefix.
- Use SHORT okved prefixes (e.g. "06" not "06.10.1") to match more companies.
- You can combine multiple filters for precise results.

Return ONLY valid JSON object with applicable filters. No explanation.\
"""


@router.post("/ai-search", response_model=CompanySearchResponse)
async def ai_search_companies(
    payload: AISearchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Parse a natural language query into search filters via GPT-4, then search."""
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
                {"role": "system", "content": AI_SEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": payload.query},
            ],
            temperature=0,
            max_tokens=200,
        )
        raw = response.choices[0].message.content or "{}"
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        filters = json.loads(raw)
        logger.info("AI search query=%r -> filters=%r", payload.query, filters)
    except Exception as exc:
        logger.warning("AI search parse failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"Не удалось разобрать запрос: {exc}")

    # Build query using extracted filters
    def apply_filters(filters_dict):
        q = select(Company)
        if filters_dict.get("q"):
            q = q.where(Company.name.ilike(f"%{filters_dict['q']}%"))
        if filters_dict.get("okved"):
            okved_val = filters_dict["okved"]
            if isinstance(okved_val, list):
                q = q.where(or_(*[Company.okved_main.like(f"{code}%") for code in okved_val]))
            else:
                q = q.where(Company.okved_main.like(f"{okved_val}%"))
        if filters_dict.get("region"):
            q = q.where(Company.region.ilike(f"%{filters_dict['region']}%"))
        if filters_dict.get("revenue_range"):
            q = q.where(Company.revenue_range == filters_dict["revenue_range"])
        if filters_dict.get("employee_min") is not None:
            q = q.where(Company.employee_count >= filters_dict["employee_min"])
        if filters_dict.get("employee_max") is not None:
            q = q.where(Company.employee_count <= filters_dict["employee_max"])
        if filters_dict.get("intent_min") is not None:
            q = q.where(Company.intent_score >= filters_dict["intent_min"])
        return q

    query = apply_filters(filters)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Fallback: if strict filters returned 0 results, progressively relax filters
    if total == 0:
        # Try dropping okved first
        if filters.get("okved"):
            fallback = {k: v for k, v in filters.items() if k != "okved"}
            if not fallback.get("q"):
                fallback["q"] = payload.query
            query = apply_filters(fallback)
            count_q = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_q)).scalar() or 0
            logger.info("AI search fallback 1 (drop okved): q=%r total=%d", fallback.get("q"), total)
        # If still 0, try just region filter
        if total == 0 and filters.get("region"):
            query = apply_filters({"region": filters["region"]})
            count_q = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_q)).scalar() or 0
            logger.info("AI search fallback 2 (region only): total=%d", total)
        # If still 0, return all companies
        if total == 0:
            query = select(Company)
            count_q = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_q)).scalar() or 0
            logger.info("AI search fallback 3 (all companies): total=%d", total)

    query = query.order_by(Company.intent_score.desc()).limit(100)
    result = await db.execute(query)
    items = result.scalars().all()

    return CompanySearchResponse(
        items=[CompanyResponse.model_validate(c) for c in items],
        total=total, page=1, per_page=100,
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
