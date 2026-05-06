"""Lead scoring engine. (Source: Apollo full-qe — services/scoring.py)

Score = profile(30%) + engagement(35%) + fit(25%) + recency(10%)
Each component returns 0-100. Deterministic, no I/O, fully testable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List

SCORE_VERSION = "2.0"

SENIORITY_WEIGHTS = {
    "c_level": 100, "ceo": 100, "cto": 100, "cfo": 100,
    "vp": 85, "director": 70, "head": 70,
    "manager": 55, "senior": 40, "ic": 30, "junior": 15,
}

SIZE_WEIGHTS = {
    "1001+": 100, "501-1000": 90, "201-500": 80,
    "51-200": 65, "11-50": 45, "1-10": 25,
}


class ScoringService:
    def score_contact(self, contact: dict, activities: Optional[List[dict]] = None) -> dict:
        activities = activities or []
        profile = self._profile_score(contact)
        engagement = self._engagement_score(activities)
        fit = self._fit_score(contact)
        recency = self._recency_score(activities)
        raw = profile * 0.30 + engagement * 0.35 + fit * 0.25 + recency * 0.10
        return {
            "score": min(100, max(0, round(raw))),
            "breakdown": {
                "profile_score": round(profile, 1),
                "engagement_score": round(engagement, 1),
                "fit_score": round(fit, 1),
                "recency_score": round(recency, 1),
            },
            "version": SCORE_VERSION,
        }

    def _profile_score(self, c: dict) -> float:
        s = 10.0
        if c.get("first_name"): s += 10
        if c.get("last_name"): s += 10
        if c.get("title"): s += 15
        if c.get("seniority"): s += 15
        if c.get("linkedin_url"): s += 20
        if c.get("phone"): s += 10
        conf = c.get("email_confidence")
        if conf is not None:
            s += float(conf) * 10
        return min(100.0, s)

    def _engagement_score(self, activities: List[dict]) -> float:
        if not activities:
            return 0.0
        weights = {
            "email_replied": 30, "email_opened": 15, "call_logged": 20,
            "note_added": 10, "email_sent": 5, "contact_enriched": 2,
            "company_enriched": 1, "crm_synced": 1,
        }
        total = sum(weights.get(a.get("activity_type", ""), 0) for a in activities)
        if total > 60:
            total = 60 + (total - 60) * 0.3
        return min(100.0, total)

    def _fit_score(self, c: dict) -> float:
        sen = (c.get("seniority") or "").lower().strip()
        size = (c.get("company_size") or "").strip()
        return (SENIORITY_WEIGHTS.get(sen, 20) + SIZE_WEIGHTS.get(size, 30)) / 2.0

    def _recency_score(self, activities: List[dict]) -> float:
        if not activities:
            return 0.0
        now = datetime.now(timezone.utc)
        latest = None
        for a in activities:
            occ = a.get("occurred_at")
            if occ is None:
                continue
            if isinstance(occ, str):
                try:
                    occ = datetime.fromisoformat(occ.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if not getattr(occ, "tzinfo", None):
                occ = occ.replace(tzinfo=timezone.utc)
            if latest is None or occ > latest:
                latest = occ
        if latest is None:
            return 0.0
        days = (now - latest).days
        if days <= 7: return 100.0
        if days <= 30: return 70.0
        if days <= 90: return 40.0
        return 10.0

    def batch_score(self, items: List[dict]) -> List[dict]:
        results = []
        for item in items:
            r = self.score_contact(item.get("contact", {}), item.get("activities", []))
            r["contact_id"] = item.get("contact", {}).get("id")
            results.append(r)
        return results


scoring_service = ScoringService()
