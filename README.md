# SalesRadar — B2B Sales Intelligence (Apollo.io RF-Clone)

> Платформа для поиска ЛПР в российских компаниях с intent signals, lead scoring, email sequences и веб-интерфейсом.

## Quick Start

```bash
# Dev mode (SQLite)
pip install -r requirements.txt
uvicorn main:app --reload

# Docker (PostgreSQL)
docker compose up --build
```

Open http://localhost:8000 — Web UI
Open http://localhost:8000/docs — Swagger API

## Features

| Feature | Description |
|---------|-------------|
| **Company Search** | Multi-filter: ОКВЭД, регион, выручка, штат, intent score |
| **Contact Management** | CRUD + enrichment (credit-based) + lead scoring |
| **Lead Scoring** | Profile(30%) + Engagement(35%) + Fit(25%) + Recency(10%) |
| **Email Sequences** | Multi-step sequences with AI personalization (GPT-4) |
| **Intent Signals** | hh.ru hiring, zakupki tenders, revenue growth, new CEO |
| **Billing** | 3 plans (4990/14990/39990₽), YooKassa stub, credit system |
| **Web UI** | 6-page SPA: Dashboard, Search, Contacts, Sequences, Analytics, Billing |

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy 2.0 async + PostgreSQL
- **Auth**: JWT (python-jose + bcrypt)
- **AI**: OpenAI GPT-4 with tenacity retry + graceful fallback
- **Payments**: YooKassa (stub mode for development)
- **Frontend**: Self-contained HTML+CSS+JS SPA (no build step)
- **Testing**: pytest + pytest-asyncio + SQLite
- **Deploy**: Docker + docker-compose

## API Endpoints

| Group | Endpoints |
|-------|-----------|
| Auth | POST /register, /login, /refresh, GET /me |
| Companies | GET /search, GET /{id}, POST / |
| Contacts | GET /, GET /{id}, POST /, POST /{id}/score, POST /{id}/enrich |
| Sequences | GET /, GET /{id}, POST /, POST /{id}/steps, PATCH /{id}/toggle |
| Enrollments | POST /, GET /, POST /{id}/advance, PUT /{id}/status |
| Activities | POST /, GET /timeline/{id}, GET /aggregate/{id} |
| Intents | GET /hot, GET /company/{inn} |
| Analytics | GET /overview, GET /top-leads |
| Billing | GET /plans, GET /credits, POST /upgrade, POST /webhook/yookassa |

## Reuse

See [REUSE_LOG.md](REUSE_LOG.md) for detailed documentation of code reused from:
- Instantly AI (JWT auth, AI personalization)
- Apollo full-qe (scoring engine, enrollment lifecycle)
- Substack (YooKassa payment stub)
- Whoop (pydantic-settings config)
