import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HAClassification(str, enum.Enum):
    BUILT_IN = "built_in"
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class CriticalityTier(str, enum.Enum):
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"
    UNCLASSIFIED = "unclassified"


class ConfidenceLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DiscoveredResource(Base):
    __tablename__ = "discovered_resources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False
    )
    arn: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    service: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    az: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    multi_az: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ha_classification: Mapped[HAClassification] = mapped_column(
        Enum(HAClassification, name="ha_classification"),
        default=HAClassification.INELIGIBLE,
        nullable=False,
    )
    eligibility_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_savings: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    criticality_tier: Mapped[CriticalityTier] = mapped_column(
        Enum(CriticalityTier, name="criticality_tier"),
        default=CriticalityTier.UNCLASSIFIED,
        nullable=False,
    )
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel, name="confidence_level"),
        default=ConfidenceLevel.LOW,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DiscoveredResource {self.service}/{self.resource_type} {self.arn[:60]}>"


class ResourceDependency(Base):
    __tablename__ = "resource_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False
    )
    source_resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovered_resources.id", ondelete="CASCADE"), nullable=False
    )
    target_resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovered_resources.id", ondelete="CASCADE"), nullable=False
    )
    dependency_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel, name="confidence_level", create_constraint=False),
        default=ConfidenceLevel.LOW,
        nullable=False,
    )
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<ResourceDependency {self.dependency_type} {self.source_resource_id} -> {self.target_resource_id}>"
