from datetime import datetime, timezone, timedelta

from services.scoring import ScoringService


def test_full_profile_score():
    svc = ScoringService()
    contact = {
        "first_name": "Алексей", "last_name": "Петров",
        "title": "Head of Sales", "seniority": "director",
        "linkedin_url": "https://linkedin.com/in/petrov",
        "phone": "+79001234567", "email_confidence": 0.9,
    }
    result = svc.score_contact(contact)
    assert 0 <= result["score"] <= 100
    assert result["version"] == "2.0"
    assert result["breakdown"]["profile_score"] == 99.0


def test_empty_contact():
    svc = ScoringService()
    result = svc.score_contact({})
    assert result["score"] >= 0
    assert result["breakdown"]["engagement_score"] == 0


def test_engagement_with_activities():
    svc = ScoringService()
    activities = [
        {"activity_type": "email_replied", "occurred_at": datetime.now(timezone.utc).isoformat()},
        {"activity_type": "email_opened", "occurred_at": datetime.now(timezone.utc).isoformat()},
        {"activity_type": "call_logged", "occurred_at": datetime.now(timezone.utc).isoformat()},
    ]
    result = svc.score_contact({"seniority": "c_level"}, activities)
    assert result["breakdown"]["engagement_score"] > 0
    assert result["breakdown"]["recency_score"] == 100.0


def test_recency_old_activity():
    svc = ScoringService()
    old = datetime.now(timezone.utc) - timedelta(days=100)
    activities = [{"activity_type": "email_sent", "occurred_at": old.isoformat()}]
    result = svc.score_contact({}, activities)
    assert result["breakdown"]["recency_score"] == 10.0


def test_fit_score_c_level_large():
    svc = ScoringService()
    result = svc.score_contact({"seniority": "c_level", "company_size": "1001+"})
    assert result["breakdown"]["fit_score"] == 100.0


def test_batch_score():
    svc = ScoringService()
    items = [
        {"contact": {"id": 1, "first_name": "A", "seniority": "vp"}, "activities": []},
        {"contact": {"id": 2, "first_name": "B"}, "activities": []},
    ]
    results = svc.batch_score(items)
    assert len(results) == 2
    assert results[0]["contact_id"] == 1
    assert results[1]["contact_id"] == 2
