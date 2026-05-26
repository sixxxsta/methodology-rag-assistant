from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PhaseOut(BaseModel):
    key: str
    title: str
    description: str
    status: str
    progress_pct: int
    order: int
    notes: str | None = None
    updated_at: datetime | None = None


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phase_key: str
    level: int
    title: str
    description: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_email: str
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    details: str | None = None
    created_at: datetime


class WorkspaceOut(BaseModel):
    id: int
    name: str
    industry: str | None = None
    created_at: datetime
    phases: list[PhaseOut]
    open_escalations: int


class DashboardOut(BaseModel):
    workspace: WorkspaceOut
    escalations: list[EscalationOut]
    recent_audit: list[AuditLogOut]


class PhaseUpdateIn(BaseModel):
    status: str | None = None
    progress_pct: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = None


class EscalationResolveIn(BaseModel):
    status: str = "resolved"
    comment: str | None = None


class IndustryApproveIn(BaseModel):
    industry: str = Field(min_length=2, max_length=255)
    comment: str | None = None
