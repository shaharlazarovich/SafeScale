import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.resource import ConfidenceLevel, CriticalityTier, HAClassification
from app.models.scan import ScanStatus


class ScanCreate(BaseModel):
    account_id: uuid.UUID


class AuditLogEntryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    scan_id: uuid.UUID
    timestamp: datetime
    phase: str
    service: str | None
    region: str | None
    action: str
    status: str
    resource_arn: str | None
    details: dict | None
    duration_ms: int | None


class PhaseProgress(BaseModel):
    name: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    items_completed: int = 0
    items_total: int | None = None


class ScanProgress(BaseModel):
    scan_id: uuid.UUID
    status: ScanStatus
    overall_progress_pct: int
    current_phase: str
    phases: list[PhaseProgress]
    running_totals: dict
    live_log_entries: list[AuditLogEntryResponse]


class ScanResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    account_id: uuid.UUID
    status: ScanStatus
    phases_completed: dict | None
    resources_found: int
    eligible_resources: int
    total_monthly_cost: Decimal | None
    estimated_savings: Decimal | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime


class ScanList(BaseModel):
    scans: list[ScanResponse]
    total: int


class ResourceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    scan_id: uuid.UUID
    account_id: uuid.UUID
    arn: str
    resource_type: str
    service: str
    region: str
    az: str | None
    name: str | None
    configuration: dict | None
    multi_az: bool
    ha_classification: HAClassification
    eligibility_reason: str | None
    monthly_cost: Decimal | None
    estimated_savings: Decimal | None
    criticality_tier: CriticalityTier
    confidence_level: ConfidenceLevel
    created_at: datetime


class ResourceList(BaseModel):
    resources: list[ResourceResponse]
    total: int
    page: int
    page_size: int
