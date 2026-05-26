from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class PhaseKey(str, enum.Enum):
    INDUSTRY = "industry_analysis"
    COMPANIES = "company_scoring"
    COMMUNICATION = "communication"
    OUTREACH = "outreach"
    PROJECTS = "projects"


class PhaseStatus(str, enum.Enum):
    LOCKED = "locked"
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class EscalationStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


PHASE_ORDER: list[PhaseKey] = [
    PhaseKey.INDUSTRY,
    PhaseKey.COMPANIES,
    PhaseKey.COMMUNICATION,
    PhaseKey.OUTREACH,
    PhaseKey.PROJECTS,
]

PHASE_META: dict[PhaseKey, dict[str, str]] = {
    PhaseKey.INDUSTRY: {
        "title": "Анализ индустрии",
        "description": "Компетенции рынка и соответствие программе",
    },
    PhaseKey.COMPANIES: {
        "title": "Поиск и скоринг",
        "description": "Пул компаний и шорт-лист партнёров",
    },
    PhaseKey.COMMUNICATION: {
        "title": "Коммуникации",
        "description": "Письма, материалы, план касаний",
    },
    PhaseKey.OUTREACH: {
        "title": "Outreach",
        "description": "Рассылка, ответы, квалификация",
    },
    PhaseKey.PROJECTS: {
        "title": "Проекты и ТЗ",
        "description": "Каталог проектов для студентов",
    },
}


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="Основной цикл")
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    phases: Mapped[list[PhaseRun]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    escalations: Mapped[list[Escalation]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class PhaseRun(Base):
    __tablename__ = "phase_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    phase_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default=PhaseStatus.LOCKED.value)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="phases")


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    phase_key: Mapped[str] = mapped_column(String(64))
    level: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=EscalationStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="escalations")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True, index=True)
    actor_email: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(512))
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    has_education_program: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="candidate")
    in_shortlist: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(32), default="program")
    demand_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    program_level: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(32), default="hh")
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    communication_id: Mapped[int | None] = mapped_column(
        ForeignKey("communications.id"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    auto_handled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Communication(Base):
    __tablename__ = "communications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    comm_type: Mapped[str] = mapped_column(String(32), default="letter")
    tone: Mapped[str] = mapped_column(String(32), default="formal")
    subject: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    value_proposition: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    delivery_status: Mapped[str] = mapped_column(String(32), default="pending")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TouchPoint(Base):
    __tablename__ = "touch_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    communication_id: Mapped[int | None] = mapped_column(
        ForeignKey("communications.id"), nullable=True
    )
    step_order: Mapped[int] = mapped_column(Integer, default=0)
    channel: Mapped[str] = mapped_column(String(32), default="email")
    title: Mapped[str] = mapped_column(String(255))
    days_after_start: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="planned")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PartnerAgreement(Base):
    __tablename__ = "partner_agreements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="agreed")
    recorded_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    agreement_id: Mapped[int | None] = mapped_column(
        ForeignKey("partner_agreements.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    competencies: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    catalog_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
