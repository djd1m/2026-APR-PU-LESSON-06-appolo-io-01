"""Intent signals router — hot signals dashboard, company signals."""

from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Depends, Query

from routers.auth import get_current_user, User
from services.intent_signals import IntentSignalService

router = APIRouter(prefix="/intents", tags=["Intent Signals"])
intent_service = IntentSignalService()


@router.get("/hot")
async def hot_signals(limit: int = Query(10, ge=1, le=50), _: User = Depends(get_current_user)):
    return intent_service.get_hot_signals(limit)


@router.get("/company/{inn}")
async def company_signals(inn: str, _: User = Depends(get_current_user)):
    return intent_service.get_signals_for_company(inn)
