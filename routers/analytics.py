"""Analytics router — campaign stats, top leads, activity summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    Company, Contact, Sequence, Enrollment, EnrollmentStatus,
    Activity, ActivityType, get_db,
)
from routers.auth import get_current_user, User

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    companies = (await db.execute(select(func.count(Company.id)))).scalar() or 0
    contacts = (await db.execute(select(func.count(Contact.id)))).scalar() or 0
    sequences = (await db.execute(
        select(func.count(Sequence.id)).where(Sequence.created_by == current_user.id)
    )).scalar() or 0
    active_enrollments = (await db.execute(
        select(func.count(Enrollment.id)).where(Enrollment.status == EnrollmentStatus.active)
    )).scalar() or 0

    emails_sent = (await db.execute(
        select(func.count(Activity.id)).where(Activity.activity_type == ActivityType.email_sent)
    )).scalar() or 0
    emails_opened = (await db.execute(
        select(func.count(Activity.id)).where(Activity.activity_type == ActivityType.email_opened)
    )).scalar() or 0
    emails_replied = (await db.execute(
        select(func.count(Activity.id)).where(Activity.activity_type == ActivityType.email_replied)
    )).scalar() or 0

    return {
        "companies": companies,
        "contacts": contacts,
        "sequences": sequences,
        "active_enrollments": active_enrollments,
        "emails_sent": emails_sent,
        "emails_opened": emails_opened,
        "emails_replied": emails_replied,
        "open_rate": round(emails_opened / max(emails_sent, 1) * 100, 1),
        "reply_rate": round(emails_replied / max(emails_sent, 1) * 100, 1),
        "credits_remaining": current_user.credits,
        "plan": current_user.plan,
    }


@router.get("/top-leads")
async def top_leads(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(Contact)
        .where(Contact.score.isnot(None))
        .order_by(Contact.score.desc())
        .limit(10)
    )
    contacts = result.scalars().all()
    return [
        {"id": c.id, "email": c.email, "first_name": c.first_name,
         "last_name": c.last_name, "title": c.title, "score": c.score}
        for c in contacts
    ]
