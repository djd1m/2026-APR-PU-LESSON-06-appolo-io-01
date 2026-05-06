from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, List, Any

from sqlalchemy import (
    Integer, String, Boolean, Float, Text, DateTime, Enum,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    JSON, func, Table, Column,
)
from sqlalchemy.ext.asyncio import (
    AsyncAttrs, create_async_engine, AsyncSession, async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship

from config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_kwargs: dict = {"echo": settings.DEBUG}
if not _is_sqlite:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 15

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# --- Enums ---

class EnrollmentStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    completed = "completed"
    paused = "paused"
    bounced = "bounced"


class ActivityType(str, enum.Enum):
    email_sent = "email_sent"
    email_opened = "email_opened"
    email_replied = "email_replied"
    call_logged = "call_logged"
    note_added = "note_added"
    contact_enriched = "contact_enriched"
    company_enriched = "company_enriched"
    crm_synced = "crm_synced"


class IntentType(str, enum.Enum):
    hiring = "hiring"
    tender = "tender"
    revenue_growth = "revenue_growth"
    new_ceo = "new_ceo"
    media_mention = "media_mention"


# --- M2M tables ---

contact_tags = Table(
    "contact_tags", Base.metadata,
    Column("contact_id", Integer, ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

company_tags = Table(
    "company_tags", Base.metadata,
    Column("company_id", Integer, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


# --- ORM Models ---

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    credits: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    sequences: Mapped[List["Sequence"]] = relationship("Sequence", back_populates="creator", lazy="noload")
    credit_transactions: Mapped[List["CreditTransaction"]] = relationship(
        "CreditTransaction", back_populates="user", lazy="noload"
    )


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inn: Mapped[Optional[str]] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    okved_main: Mapped[Optional[str]] = mapped_column(String(10))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(128))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    revenue_range: Mapped[Optional[str]] = mapped_column(String(50))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    intent_score: Mapped[int] = mapped_column(Integer, default=0)
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    contacts: Mapped[List["Contact"]] = relationship("Contact", back_populates="company", lazy="noload")
    tags: Mapped[List["Tag"]] = relationship("Tag", secondary=company_tags, lazy="noload")
    intent_signals: Mapped[List["IntentSignal"]] = relationship("IntentSignal", back_populates="company", lazy="noload")

    __table_args__ = (Index("ix_companies_region_okved", "region", "okved_main"),)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    title: Mapped[Optional[str]] = mapped_column(String(200))
    seniority: Mapped[Optional[str]] = mapped_column(String(50))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    score: Mapped[Optional[int]] = mapped_column(
        Integer, CheckConstraint("score >= 0 AND score <= 100", name="ck_contact_score")
    )
    score_version: Mapped[Optional[str]] = mapped_column(String(20))
    email_confidence: Mapped[Optional[float]] = mapped_column(Float)
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="contacts", lazy="noload")
    tags: Mapped[List["Tag"]] = relationship("Tag", secondary=contact_tags, lazy="noload")
    enrollments: Mapped[List["Enrollment"]] = relationship("Enrollment", back_populates="contact", lazy="noload")
    activities: Mapped[List["Activity"]] = relationship("Activity", back_populates="contact", lazy="noload")

    __table_args__ = (
        Index("ix_contacts_name", "first_name", "last_name"),
        Index("ix_contacts_seniority", "seniority"),
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    color: Mapped[Optional[str]] = mapped_column(String(7))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Sequence(Base):
    __tablename__ = "sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    creator: Mapped[Optional["User"]] = relationship("User", back_populates="sequences", lazy="noload")
    steps: Mapped[List["SequenceStep"]] = relationship(
        "SequenceStep", back_populates="sequence", lazy="noload",
        order_by="SequenceStep.step_order",
    )
    enrollments: Mapped[List["Enrollment"]] = relationship("Enrollment", back_populates="sequence", lazy="noload")


class SequenceStep(Base):
    __tablename__ = "sequence_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sequence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sequences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_template: Mapped[str] = mapped_column(String(500), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sequence: Mapped["Sequence"] = relationship("Sequence", back_populates="steps", lazy="noload")

    __table_args__ = (UniqueConstraint("sequence_id", "step_order", name="uq_sequence_step_order"),)


class Enrollment(Base):
    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sequences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus), default=EnrollmentStatus.pending, nullable=False, index=True
    )
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    contact: Mapped["Contact"] = relationship("Contact", back_populates="enrollments", lazy="noload")
    sequence: Mapped["Sequence"] = relationship("Sequence", back_populates="enrollments", lazy="noload")

    __table_args__ = (UniqueConstraint("contact_id", "sequence_id", name="uq_contact_sequence"),)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    enrollment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("enrollments.id", ondelete="SET NULL"), index=True
    )
    activity_type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), nullable=False, index=True)
    metadata_: Mapped[Optional[Any]] = mapped_column("metadata", JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    contact: Mapped["Contact"] = relationship("Contact", back_populates="activities", lazy="noload")

    __table_args__ = (Index("ix_activities_contact_occurred", "contact_id", "occurred_at"),)


class IntentSignal(Base):
    __tablename__ = "intent_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_type: Mapped[IntentType] = mapped_column(Enum(IntentType), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    strength: Mapped[int] = mapped_column(Integer, default=50)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    company: Mapped["Company"] = relationship("Company", back_populates="intent_signals", lazy="noload")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="credit_transactions", lazy="noload")
