from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.scans import broadcast_scan_progress
from app.core.logging import get_logger
from app.models.account import CloudAccount
from app.models.resource import (
    ConfidenceLevel,
    CriticalityTier,
    DiscoveredResource,
    HAClassification,
    ResourceDependency,
)
from app.models.scan import AuditLogEntry, ScanSession, ScanStatus

from .classifiers import classify_resource, estimate_costs, infer_criticality
from .scanners import ALL_SCANNERS, BaseScanner

logger = get_logger("auditor.engine")

PHASES = [
    "enumeration",
    "topology_mapping",
    "ha_classification",
    "cost_analysis",
    "criticality_inference",
    "report_generation",
]

ENABLED_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2",
    "ap-south-1", "sa-east-1", "ca-central-1",
]


class AuditEngine:
    """Orchestrates the 6-phase audit scan pipeline."""

    def __init__(self, db: AsyncSession, scan_id: uuid.UUID) -> None:
        self._db = db
        self._scan_id = scan_id
        self._scan: ScanSession | None = None
        self._account: CloudAccount | None = None
        self._session: boto3.Session | None = None
        self._discovered: list[dict] = []
        self._db_resources: list[DiscoveredResource] = []
        self._dependencies: list[ResourceDependency] = []
        self._phases_completed: dict = {}
        self._cancelled = False

    async def run(self) -> None:
        """Execute the full scan pipeline."""
        try:
            await self._load_scan()
            await self._update_status(ScanStatus.RUNNING)
            await self._log("system", "scan_start", "info", "Audit scan started")

            for phase in PHASES:
                if self._cancelled:
                    break
                await self._run_phase(phase)

            if not self._cancelled:
                await self._update_status(ScanStatus.COMPLETED)
                await self._log("system", "scan_complete", "info", "Audit scan completed successfully")
        except Exception as exc:
            logger.exception("Scan %s failed", self._scan_id)
            await self._update_status(ScanStatus.FAILED, error=str(exc))
            await self._log("system", "scan_error", "error", f"Scan failed: {exc}")

    def cancel(self) -> None:
        self._cancelled = True

    async def _load_scan(self) -> None:
        result = await self._db.execute(
            select(ScanSession).where(ScanSession.id == self._scan_id)
        )
        self._scan = result.scalar_one()
        self._phases_completed = self._scan.phases_completed or {}

        result = await self._db.execute(
            select(CloudAccount).where(CloudAccount.id == self._scan.account_id)
        )
        self._account = result.scalar_one()
        self._session = boto3.Session()

    async def _run_phase(self, phase: str) -> None:
        start = time.monotonic()
        self._phases_completed[phase] = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._save_phases()
        await self._broadcast_progress()

        handler = getattr(self, f"_phase_{phase}", None)
        if handler is None:
            logger.warning("No handler for phase %s", phase)
            return

        try:
            await handler()
            duration_ms = int((time.monotonic() - start) * 1000)
            self._phases_completed[phase].update({
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration_ms,
            })
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._phases_completed[phase].update({
                "status": "error",
                "error": str(exc),
                "duration_ms": duration_ms,
            })
            logger.exception("Phase %s failed for scan %s", phase, self._scan_id)
            await self._log(phase, f"{phase}_error", "error", f"Phase failed: {exc}")

        await self._save_phases()
        await self._broadcast_progress()

    # ------------------------------------------------------------------
    # Phase 1: Enumeration
    # ------------------------------------------------------------------

    async def _phase_enumeration(self) -> None:
        await self._log("enumeration", "enumeration_start", "info", "Starting resource enumeration across all regions")

        regions = self._account.regions_enabled or ENABLED_REGIONS
        total_tasks = len(regions) * len(ALL_SCANNERS)
        completed = 0

        for region in regions:
            if self._cancelled:
                break

            await self._log(
                "enumeration", "region_start", "info",
                f"Scanning region {region}",
                details={"region": region},
            )

            tasks = []
            for scanner_cls in ALL_SCANNERS:
                scanner = scanner_cls(
                    session=self._session,
                    region=region,
                    logger=logger,
                )
                tasks.append(self._run_scanner(scanner, region))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                completed += 1
                scanner_name = ALL_SCANNERS[i].SERVICE

                if isinstance(result, Exception):
                    await self._log(
                        "enumeration", "scanner_error", "warning",
                        f"Scanner {scanner_name} failed in {region}: {result}",
                        details={"scanner": scanner_name, "region": region, "error": str(result)},
                    )
                    continue

                if result:
                    self._discovered.extend(result)
                    await self._log(
                        "enumeration", "scanner_complete", "info",
                        f"Found {len(result)} {scanner_name} resources in {region}",
                        details={"scanner": scanner_name, "region": region, "count": len(result)},
                    )

            self._phases_completed["enumeration"]["items_completed"] = completed
            self._phases_completed["enumeration"]["items_total"] = total_tasks
            await self._save_phases()
            await self._broadcast_progress()

        await self._log(
            "enumeration", "enumeration_complete", "info",
            f"Enumeration complete: {len(self._discovered)} resources discovered across {len(regions)} regions",
        )

    async def _run_scanner(self, scanner: BaseScanner, region: str) -> list[dict]:
        return await scanner._safe_scan()

    # ------------------------------------------------------------------
    # Phase 2: Topology Mapping
    # ------------------------------------------------------------------

    async def _phase_topology_mapping(self) -> None:
        await self._log("topology_mapping", "topology_start", "info", "Starting topology and dependency mapping")

        arn_to_resource: dict[str, dict] = {r["arn"]: r for r in self._discovered}
        dependencies = []

        for resource in self._discovered:
            config = resource.get("configuration", {})
            service = resource.get("service", "")

            if service == "ecs":
                lb_refs = config.get("load_balancers", [])
                for lb_ref in lb_refs:
                    tg_arn = lb_ref.get("targetGroupArn", "")
                    for other_arn, other in arn_to_resource.items():
                        if other.get("service") == "elb":
                            tgs = other.get("configuration", {}).get("target_groups", [])
                            if any(tg.get("arn") == tg_arn for tg in tgs):
                                dependencies.append({
                                    "source_arn": resource["arn"],
                                    "target_arn": other_arn,
                                    "type": "ecs_to_elb",
                                    "confidence": ConfidenceLevel.HIGH,
                                })

            if service == "ec2" and resource.get("resource_type") == "auto_scaling_group":
                tg_arns = config.get("target_group_arns", [])
                for tg_arn in tg_arns:
                    for other_arn, other in arn_to_resource.items():
                        if other.get("service") == "elb":
                            tgs = other.get("configuration", {}).get("target_groups", [])
                            if any(tg.get("arn") == tg_arn for tg in tgs):
                                dependencies.append({
                                    "source_arn": resource["arn"],
                                    "target_arn": other_arn,
                                    "type": "asg_to_elb",
                                    "confidence": ConfidenceLevel.HIGH,
                                })

            if service == "rds" and resource.get("resource_type") == "db_instance":
                cluster_id = config.get("db_cluster_identifier")
                if cluster_id:
                    for other_arn, other in arn_to_resource.items():
                        if (other.get("service") == "rds"
                                and other.get("resource_type") == "db_cluster"
                                and other.get("configuration", {}).get("db_cluster_identifier") == cluster_id):
                            dependencies.append({
                                "source_arn": resource["arn"],
                                "target_arn": other_arn,
                                "type": "instance_to_cluster",
                                "confidence": ConfidenceLevel.HIGH,
                            })

            if service == "ebs":
                for inst_id in config.get("attached_instances", []):
                    for other_arn, other in arn_to_resource.items():
                        if (other.get("service") == "ec2"
                                and other.get("configuration", {}).get("instance_id") == inst_id):
                            dependencies.append({
                                "source_arn": resource["arn"],
                                "target_arn": other_arn,
                                "type": "ebs_to_ec2",
                                "confidence": ConfidenceLevel.HIGH,
                            })

            if service == "eks" and resource.get("resource_type") == "nodegroup":
                cluster_name = config.get("cluster_name")
                if cluster_name:
                    for other_arn, other in arn_to_resource.items():
                        if (other.get("service") == "eks"
                                and other.get("resource_type") == "cluster"
                                and other.get("configuration", {}).get("cluster_name") == cluster_name):
                            dependencies.append({
                                "source_arn": resource["arn"],
                                "target_arn": other_arn,
                                "type": "nodegroup_to_cluster",
                                "confidence": ConfidenceLevel.HIGH,
                            })

        resource_dep_count: dict[str, int] = {}
        for dep in dependencies:
            src = dep["source_arn"]
            tgt = dep["target_arn"]
            resource_dep_count[src] = resource_dep_count.get(src, 0) + 1
            resource_dep_count[tgt] = resource_dep_count.get(tgt, 0) + 1

        for resource in self._discovered:
            resource["_dependency_fan_out"] = resource_dep_count.get(resource["arn"], 0)

        self._discovered_dependencies = dependencies

        await self._log(
            "topology_mapping", "topology_complete", "info",
            f"Mapped {len(dependencies)} dependencies across {len(self._discovered)} resources",
        )

    # ------------------------------------------------------------------
    # Phase 3: HA Classification
    # ------------------------------------------------------------------

    async def _phase_ha_classification(self) -> None:
        await self._log("ha_classification", "classification_start", "info", "Classifying HA eligibility for all resources")

        eligible_count = 0
        for resource in self._discovered:
            classification, reason, confidence = classify_resource(resource)
            resource["_ha_classification"] = classification
            resource["_eligibility_reason"] = reason
            resource["_ha_confidence"] = confidence
            if classification == HAClassification.ELIGIBLE:
                eligible_count += 1

        await self._log(
            "ha_classification", "classification_complete", "info",
            f"Classification complete: {eligible_count} eligible out of {len(self._discovered)} resources",
        )

    # ------------------------------------------------------------------
    # Phase 4: Cost Analysis
    # ------------------------------------------------------------------

    async def _phase_cost_analysis(self) -> None:
        await self._log("cost_analysis", "cost_start", "info", "Estimating costs and potential savings")

        total_monthly = Decimal("0")
        total_savings = Decimal("0")

        for resource in self._discovered:
            ha_class = resource.get("_ha_classification", HAClassification.INELIGIBLE)
            monthly, savings = estimate_costs(resource, ha_class)
            resource["_monthly_cost"] = monthly
            resource["_estimated_savings"] = savings
            if monthly:
                total_monthly += monthly
            if savings:
                total_savings += savings

        await self._log(
            "cost_analysis", "cost_complete", "info",
            f"Cost analysis complete: ${total_monthly:,.2f}/mo total, ${total_savings:,.2f}/mo potential savings",
        )

    # ------------------------------------------------------------------
    # Phase 5: Criticality Inference
    # ------------------------------------------------------------------

    async def _phase_criticality_inference(self) -> None:
        await self._log("criticality_inference", "criticality_start", "info", "Inferring resource criticality tiers")

        tier_counts: dict[str, int] = {}
        for resource in self._discovered:
            fan_out = resource.get("_dependency_fan_out", 0)
            tier, confidence = infer_criticality(resource, fan_out)
            resource["_criticality_tier"] = tier
            resource["_criticality_confidence"] = confidence
            tier_counts[tier.value] = tier_counts.get(tier.value, 0) + 1

        summary = ", ".join(f"{k}: {v}" for k, v in sorted(tier_counts.items()))
        await self._log(
            "criticality_inference", "criticality_complete", "info",
            f"Criticality inference complete: {summary}",
        )

    # ------------------------------------------------------------------
    # Phase 6: Report Generation (persist to DB)
    # ------------------------------------------------------------------

    async def _phase_report_generation(self) -> None:
        await self._log("report_generation", "persist_start", "info", "Persisting results to database")

        arn_to_db_resource: dict[str, DiscoveredResource] = {}
        total_monthly = Decimal("0")
        total_savings = Decimal("0")
        eligible_count = 0

        for resource in self._discovered:
            ha_class = resource.get("_ha_classification", HAClassification.INELIGIBLE)
            monthly_cost = resource.get("_monthly_cost")
            est_savings = resource.get("_estimated_savings")
            crit_tier = resource.get("_criticality_tier", CriticalityTier.UNCLASSIFIED)
            confidence = resource.get("_ha_confidence", ConfidenceLevel.LOW)

            if ha_class == HAClassification.ELIGIBLE:
                eligible_count += 1
            if monthly_cost:
                total_monthly += monthly_cost
            if est_savings:
                total_savings += est_savings

            db_resource = DiscoveredResource(
                scan_id=self._scan_id,
                account_id=self._account.id,
                arn=resource["arn"],
                resource_type=resource.get("resource_type", "unknown"),
                service=resource.get("service", "unknown"),
                region=resource.get("region", "unknown"),
                az=resource.get("az"),
                name=resource.get("name"),
                configuration=resource.get("configuration"),
                multi_az=resource.get("multi_az", False),
                ha_classification=ha_class,
                eligibility_reason=resource.get("_eligibility_reason"),
                monthly_cost=monthly_cost,
                estimated_savings=est_savings,
                criticality_tier=crit_tier,
                confidence_level=confidence,
            )
            self._db.add(db_resource)
            arn_to_db_resource[resource["arn"]] = db_resource

        await self._db.flush()

        dep_count = 0
        for dep in getattr(self, "_discovered_dependencies", []):
            src_res = arn_to_db_resource.get(dep["source_arn"])
            tgt_res = arn_to_db_resource.get(dep["target_arn"])
            if src_res and tgt_res:
                db_dep = ResourceDependency(
                    scan_id=self._scan_id,
                    source_resource_id=src_res.id,
                    target_resource_id=tgt_res.id,
                    dependency_type=dep["type"],
                    confidence_level=dep.get("confidence", ConfidenceLevel.MEDIUM),
                )
                self._db.add(db_dep)
                dep_count += 1

        self._scan.resources_found = len(self._discovered)
        self._scan.eligible_resources = eligible_count
        self._scan.total_monthly_cost = total_monthly
        self._scan.estimated_savings = total_savings
        self._scan.completed_at = datetime.now(timezone.utc)
        await self._db.flush()

        await self._log(
            "report_generation", "persist_complete", "info",
            f"Persisted {len(self._discovered)} resources and {dep_count} dependencies",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _update_status(self, status: ScanStatus, error: str | None = None) -> None:
        self._scan.status = status
        if status == ScanStatus.RUNNING:
            self._scan.started_at = datetime.now(timezone.utc)
        elif status in (ScanStatus.COMPLETED, ScanStatus.FAILED):
            self._scan.completed_at = datetime.now(timezone.utc)
        if error:
            self._scan.error_message = error
        await self._db.flush()
        await self._broadcast_progress()

    async def _save_phases(self) -> None:
        self._scan.phases_completed = dict(self._phases_completed)
        await self._db.flush()

    async def _log(
        self,
        phase: str,
        action: str,
        status: str,
        message: str,
        *,
        service: str | None = None,
        region: str | None = None,
        resource_arn: str | None = None,
        details: dict | None = None,
        duration_ms: int | None = None,
    ) -> None:
        entry = AuditLogEntry(
            scan_id=self._scan_id,
            phase=phase,
            service=service,
            region=region,
            action=action,
            status=status,
            resource_arn=resource_arn,
            details=details,
            duration_ms=duration_ms,
        )
        self._db.add(entry)
        await self._db.flush()

        logger.info(
            "[%s] %s — %s",
            phase, action, message,
            extra={"scan_id": str(self._scan_id), "phase": phase},
        )

        await broadcast_scan_progress(self._scan_id, {
            "type": "log",
            "entry": {
                "timestamp": entry.timestamp.isoformat(),
                "phase": phase,
                "severity": status,
                "message": message,
            },
        })

    async def _broadcast_progress(self) -> None:
        phases = []
        for name in PHASES:
            data = self._phases_completed.get(name, {})
            phase_status = data.get("status", "pending")
            phases.append({
                "phase": name,
                "status": phase_status,
                "progress_pct": 100 if phase_status == "completed" else (
                    int(data.get("items_completed", 0) / max(data.get("items_total", 1), 1) * 100)
                    if phase_status == "running" else 0
                ),
                "duration_seconds": (data.get("duration_ms") or 0) // 1000 if data.get("duration_ms") else None,
                "details": {},
            })

        completed_count = sum(1 for p in phases if p["status"] == "completed")
        running_pct = 0
        for p in phases:
            if p["status"] == "running":
                running_pct = p["progress_pct"]
                break

        overall = int((completed_count / len(PHASES)) * 100 + running_pct / len(PHASES))

        total_savings = Decimal("0")
        for r in self._discovered:
            s = r.get("_estimated_savings")
            if s:
                total_savings += s

        await broadcast_scan_progress(self._scan_id, {
            "type": "progress",
            "phases": phases,
            "overall_pct": min(overall, 100),
            "totals": {
                "resources_discovered": len(self._discovered),
                "multi_az_eligible": sum(
                    1 for r in self._discovered
                    if r.get("_ha_classification") == HAClassification.ELIGIBLE
                ),
                "regions_with_resources": len({
                    r.get("region") for r in self._discovered if r.get("region")
                }),
                "dependencies_mapped": len(getattr(self, "_discovered_dependencies", [])),
                "zombies_found": 0,
                "estimated_savings": float(total_savings),
            },
        })
