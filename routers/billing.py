"""Billing router — plans, credits, YooKassa payments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import User, CreditTransaction, get_db
from routers.auth import get_current_user
from services.payments import payment_service, PLANS

router = APIRouter(prefix="/billing", tags=["Billing"])


class UpgradeRequest(BaseModel):
    plan: str


class CreditPurchase(BaseModel):
    amount: int


@router.get("/plans")
async def list_plans():
    return PLANS


@router.get("/credits")
async def get_credits(current_user: User = Depends(get_current_user)):
    return {"credits": current_user.credits, "plan": current_user.plan}


@router.post("/upgrade")
async def upgrade_plan(
    payload: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = PLANS.get(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan. Available: {list(PLANS.keys())}")

    result = payment_service.create_payment(
        amount=plan["price"],
        description=f"SalesRadar {plan['name']} plan",
    )

    if result.is_stub:
        current_user.plan = payload.plan
        current_user.credits += plan["credits"]
        tx = CreditTransaction(user_id=current_user.id, amount=plan["credits"], reason=f"upgrade:{payload.plan}")
        db.add(tx)
        await db.commit()
        return {
            "status": "completed",
            "plan": payload.plan,
            "credits_added": plan["credits"],
            "total_credits": current_user.credits,
            "payment_id": result.payment_id,
            "is_stub": True,
        }

    return {"status": "pending", "payment_url": result.payment_url, "payment_id": result.payment_id}


@router.post("/webhook/yookassa")
async def yookassa_webhook(body: dict, db: AsyncSession = Depends(get_db)):
    """YooKassa payment notification webhook."""
    payment_id = body.get("object", {}).get("id")
    if not payment_id:
        raise HTTPException(status_code=400, detail="Missing payment ID")
    payment_service.confirm_payment(payment_id)
    return {"status": "ok"}
