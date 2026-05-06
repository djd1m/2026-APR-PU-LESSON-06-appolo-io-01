# REUSE_LOG — Переиспользование из предыдущих проектов

> Apollo.io May 2026 (SalesRadar) — построен на основе лучших паттернов из 4 проектов курса

---

## Источники переиспользования

### 1. Instantly AI (`full-qe-projects/instantly-ai-full-qe/`)

| Компонент | Исходный файл | Целевой файл | Что взято | Что изменено |
|-----------|---------------|--------------|-----------|--------------|
| **JWT Auth** | `routers/auth.py` | `routers/auth.py` | OAuth2PasswordBearer + bcrypt + python-jose, register/login/me endpoints, get_current_user dependency | Добавлен refresh token (access + refresh), поле plan/credits в UserResponse, tokenUrl обновлён на `/api/v1/auth/login` |
| **AI Personalization** | `services/ai_personalization.py` | `services/ai_personalization.py` | AsyncOpenAI client, tenacity retry (3 attempts, exponential backoff), graceful fallback to template rendering | Объединён personalize() в единый метод (subject+body), добавлена поддержка русского языка в system prompt, убрана зависимость от Lead model |
| **Config pattern** | `.env.example` | `.env.example` | SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, OPENAI_* settings, CORS_ORIGINS | Добавлены REFRESH_TOKEN_EXPIRE_DAYS, PAYMENTS_STUB, YOOKASSA_*, APP_VERSION |
| **conftest.py** | `tests/conftest.py` | `tests/conftest.py` | Паттерн: env mocks в начале файла → import app → setup_db fixture → auth_client fixture | Адаптирован под SQLite для тестов (aiosqlite), добавлен create_tables/drop_tables lifecycle |

### 2. Apollo.io Full QE (`full-qe-projects/apollo-io-full-qe/`)

| Компонент | Исходный файл | Целевой файл | Что взято | Что изменено |
|-----------|---------------|--------------|-----------|--------------|
| **Scoring Engine** | `services/scoring.py` | `services/scoring.py` | Полная формула: profile(30%) + engagement(35%) + fit(25%) + recency(10%), SENIORITY_WEIGHTS, SIZE_WEIGHTS, batch_score() | Добавлены дополнительные seniority ключи (ceo, cto, cfo, head), SCORE_VERSION = "2.0", улучшена типизация |
| **Enrollment Lifecycle** | `routers/enrollments.py` | `routers/enrollments.py` | EnrollmentStatus enum (pending/active/completed/paused/bounced), enroll → advance → complete flow, duplicate check | Практически 1:1 перенос, минимальные стилистические правки |
| **Activity Tracking** | `routers/activities.py` | `routers/activities.py` | ActivityType enum (8 типов), log_activity, get_timeline, aggregate_counts endpoints | Перенесён без изменений, убран metadata из response model для простоты |
| **DB Models** | `models/database.py` | `models/database.py` | 7 ORM моделей (User, Company, Contact, Tag, Sequence, SequenceStep, Enrollment), M2M tables, CheckConstraint, UniqueConstraint, составные индексы | Добавлены 3 новых модели: IntentSignal, CreditTransaction, IntentType enum. Добавлены поля: intent_score в Company, plan/credits в User |
| **CORS Middleware** | `main.py` | `main.py` | CORSMiddleware с conditional allow_origins (DEBUG → "*") | Без изменений |

### 3. Substack (`full-qe-projects/substack-full-qe/`)

| Компонент | Исходный файл | Целевой файл | Что взято | Что изменено |
|-----------|---------------|--------------|-----------|--------------|
| **YooKassa Payment Stub** | `services/payments.py` | `services/payments.py` | PaymentResult dataclass, PaymentService с is_stub property, create_payment() / confirm_payment() с stub fallback, UUID idempotency | Добавлен PLANS dict (starter/professional/agency), цены в рублях. Убрана зависимость от Settings через DI (используем глобальный settings) |

### 4. Whoop (`full-qe-projects/whoop-mvp-full-qe/`)

| Компонент | Исходный файл | Целевой файл | Что взято | Что изменено |
|-----------|---------------|--------------|-----------|--------------|
| **pydantic-settings Config** | `config.py` | `config.py` | Паттерн: BaseSettings с env_file=".env", extra="ignore" | Добавлены Apollo-специфичные настройки (YOOKASSA_*, REFRESH_TOKEN_*), упрощены имена |

### 5. Общие паттерны (из нескольких проектов)

| Паттерн | Проекты-источники | Как используется |
|---------|-------------------|-----------------|
| **FastAPI lifespan** | Instantly, Apollo full-qe, Substack | `@asynccontextmanager` для startup (create_tables) и shutdown (engine.dispose) |
| **SQLAlchemy 2.0 async** | Whoop, Instantly, Apollo full-qe | mapped_column, async_sessionmaker, get_db dependency |
| **Docker Compose** | Instantly, Substack | PostgreSQL + API service, healthcheck, volumes |
| **pytest-asyncio** | Instantly, Apollo full-qe | async test fixtures, AsyncClient с ASGITransport |

---

## Новый код (не переиспользованный)

| Компонент | Описание |
|-----------|----------|
| **Intent Signals Service** | Mock-данные для intent dashboard (hh.ru hiring, zakupki tenders, revenue growth, new CEO) |
| **Companies Search Router** | Multi-filter search (ОКВЭД, region, revenue, employees, intent score), pagination |
| **Billing Router** | Credit system, plan upgrade, YooKassa webhook |
| **Contact Enrichment** | Atomic credit deduction (UPDATE WHERE credits >= 1), CreditTransaction log |
| **Frontend SPA** | 600+ строк HTML+CSS+JS: Dashboard, Company Search, Contacts, Sequences, Analytics, Billing |
| **IntentSignal / CreditTransaction models** | Новые ORM модели для intent tracking и credit history |

---

## Статистика переиспользования

| Метрика | Значение |
|---------|----------|
| Общий объём кода | ~2,400 строк |
| Переиспользовано | ~800 строк (~33%) |
| Адаптировано | ~600 строк (~25%) |
| Написано с нуля | ~1,000 строк (~42%) |
| Источников | 4 проекта |
| Файлов переиспользовано | 8 из 22 |

---

## Ключевые решения по адаптации

1. **JWT вместо API Key**: Instantly использовал тот же паттерн JWT что и Apollo full-qe. Выбран Instantly как основа (более чистый код), добавлен refresh token из Apollo full-qe.

2. **Scoring engine**: Перенесён 1:1 из Apollo full-qe. Формула оптимальна для B2B lead scoring. Единственное изменение — расширение SENIORITY_WEIGHTS.

3. **Payment stub**: Substack pattern (PaymentService с is_stub) — чистый, тестируемый, легко заменяется на реальный YooKassa. Добавлен PLANS dictionary для тарифной сетки.

4. **Frontend — новый**: Ни один из предыдущих проектов не имел веб-интерфейса. SPA написан с нуля, но стиль UI вдохновлён CJM-прототипами из rf-clones-2026.
