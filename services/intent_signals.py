"""Intent signals service — mock data for MVP.

In production: scheduled ETL from hh.ru, zakupki.gov.ru, ЕГРЮЛ, media RSS.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

MOCK_SIGNALS = [
    {"company": "ТехноСофт", "inn": "7710123456", "type": "hiring", "title": "Нанимает 3 DevOps-инженеров", "source": "hh.ru", "strength": 85},
    {"company": "Инфосистемы", "inn": "7720234567", "type": "tender", "title": "Тендер на CRM-систему, 5M₽", "source": "zakupki.gov.ru", "strength": 92},
    {"company": "DataFlow", "inn": "7730345678", "type": "revenue_growth", "title": "Выручка +45% YoY (320M → 464M₽)", "source": "Rusprofile", "strength": 78},
    {"company": "CloudBase", "inn": "7740456789", "type": "new_ceo", "title": "Новый CEO — экс-директор Яндекс.Облако", "source": "ЕГРЮЛ", "strength": 70},
    {"company": "МаркетПро", "inn": "7750567890", "type": "hiring", "title": "Открыл 5 вакансий в отдел продаж", "source": "hh.ru", "strength": 88},
    {"company": "SmartERP", "inn": "7760678901", "type": "media_mention", "title": "Упомянута в рейтинге CNews TOP-100", "source": "CNews", "strength": 65},
    {"company": "ФинТехЛаб", "inn": "7770789012", "type": "tender", "title": "Закупка серверного оборудования, 12M₽", "source": "zakupki.gov.ru", "strength": 80},
    {"company": "НейроСеть", "inn": "7780890123", "type": "revenue_growth", "title": "Выручка +78% YoY (45M → 80M₽)", "source": "Rusprofile", "strength": 95},
    {"company": "АйТиСервис", "inn": "7790901234", "type": "hiring", "title": "Ищет Head of Sales + 2 SDR", "source": "hh.ru", "strength": 90},
    {"company": "DigitalWave", "inn": "7701012345", "type": "new_ceo", "title": "Смена учредителя, привлечение инвестиций", "source": "ЕГРЮЛ", "strength": 72},
]


class IntentSignalService:
    def get_hot_signals(self, limit: int = 10) -> List[dict]:
        now = datetime.now(timezone.utc)
        signals = []
        for i, s in enumerate(MOCK_SIGNALS[:limit]):
            signals.append({
                **s,
                "detected_at": (now - timedelta(hours=i * 3)).isoformat(),
                "intent_score": s["strength"],
            })
        return sorted(signals, key=lambda x: x["strength"], reverse=True)

    def get_signals_for_company(self, inn: str) -> List[dict]:
        return [s for s in MOCK_SIGNALS if s["inn"] == inn]
