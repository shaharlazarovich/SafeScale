import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, get_db
from app.core.logging import get_logger
from app.models.account import CloudAccount
from app.models.resource import DiscoveredResource
from app.models.scan import AuditLogEntry, ScanSession, ScanStatus
from app.schemas.scan import (
    AuditLogEntryResponse,
    ResourceList,
    ResourceResponse,
    ScanCreate,
    ScanList,
    ScanProgress,
    ScanResponse,
)

logger = get_logger("api.scans")
router = APIRouter(prefix="/scans", tags=["scans"])

_progress_subscribers: dict[uuid.UUID, list[WebSocket]] = {}


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(payload: ScanCreate, db: AsyncSession = Depends(get_db)) -> ScanSession:
    result = await db.execute(select(CloudAccount).where(CloudAccount.id == payload.account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    active_scan = await db.execute(
        select(ScanSession).where(
            ScanSession.account_id == payload.account_id,
            ScanSession.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING]),
        )
    )
    if active_scan.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A scan is already running for this account")

    scan = ScanSession(
        account_id=payload.account_id,
        status=ScanStatus.PENDING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(scan)
    await db.flush()
    await db.refresh(scan)

    logger.info("Scan created", extra={"scan_id": str(scan.id), "account_id": str(payload.account_id)})

    scan.status = ScanStatus.RUNNING
    await db.flush()

    asyncio.create_task(_run_scan_background(scan.id))

    return scan


async def _run_scan_background(scan_id: uuid.UUID) -> None:
    from app.services.auditor import AuditEngine

    async with async_session() as db:
        try:
            engine = AuditEngine(db=db, scan_id=scan_id)
            await engine.run()
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Background scan %s failed", scan_id)


@router.get("", response_model=ScanList)
async def list_scans(
    account_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(ScanSession).order_by(ScanSession.created_at.desc())
    if account_id:
        query = query.where(ScanSession.account_id == account_id)
    result = await db.execute(query)
    scans = list(result.scalars().all())
    return {"scans": scans, "total": len(scans)}


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ScanSession:
    result = await db.execute(select(ScanSession).where(ScanSession.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.get("/{scan_id}/progress", response_model=ScanProgress)
async def get_scan_progress(scan_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(ScanSession).where(ScanSession.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    log_result = await db.execute(
        select(AuditLogEntry)
        .where(AuditLogEntry.scan_id == scan_id)
        .order_by(AuditLogEntry.timestamp.desc())
        .limit(50)
    )
    recent_logs = list(log_result.scalars().all())

    phases_completed = scan.phases_completed or {}
    total_phases = 6
    completed_count = sum(1 for v in phases_completed.values() if v.get("status") == "completed")
    progress_pct = int((completed_count / total_phases) * 100) if total_phases else 0

    current_phase = "idle"
    for phase_name, phase_data in phases_completed.items():
        if phase_data.get("status") == "running":
            current_phase = phase_name
            break

    return {
        "scan_id": scan.id,
        "status": scan.status,
        "overall_progress_pct": progress_pct,
        "current_phase": current_phase,
        "phases": [
            {
                "name": name,
                "status": data.get("status", "pending"),
                "started_at": data.get("started_at"),
                "completed_at": data.get("completed_at"),
                "duration_ms": data.get("duration_ms"),
                "items_completed": data.get("items_completed", 0),
                "items_total": data.get("items_total"),
            }
            for name, data in phases_completed.items()
        ],
        "running_totals": {
            "resources_found": scan.resources_found,
            "eligible_resources": scan.eligible_resources,
            "estimated_savings": str(scan.estimated_savings) if scan.estimated_savings else None,
            "total_monthly_cost": str(scan.total_monthly_cost) if scan.total_monthly_cost else None,
        },
        "live_log_entries": [AuditLogEntryResponse.model_validate(entry) for entry in reversed(recent_logs)],
    }


@router.get("/{scan_id}/resources", response_model=ResourceList)
async def get_scan_resources(
    scan_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    service: str | None = Query(None),
    ha_classification: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(ScanSession).where(ScanSession.id == scan_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Scan not found")

    query = select(DiscoveredResource).where(DiscoveredResource.scan_id == scan_id)
    count_query = select(func.count()).select_from(DiscoveredResource).where(DiscoveredResource.scan_id == scan_id)

    if service:
        query = query.where(DiscoveredResource.service == service)
        count_query = count_query.where(DiscoveredResource.service == service)
    if ha_classification:
        query = query.where(DiscoveredResource.ha_classification == ha_classification)
        count_query = count_query.where(DiscoveredResource.ha_classification == ha_classification)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(DiscoveredResource.estimated_savings.desc().nulls_last())
    query = query.offset((page - 1) * page_size).limit(page_size)
    resources_result = await db.execute(query)
    resources = list(resources_result.scalars().all())

    return {
        "resources": [ResourceResponse.model_validate(r) for r in resources],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{scan_id}/log", response_model=list[AuditLogEntryResponse])
async def get_scan_log(
    scan_id: uuid.UUID,
    phase: str | None = Query(None),
    service: str | None = Query(None),
    log_status: str | None = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list:
    result = await db.execute(select(ScanSession).where(ScanSession.id == scan_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Scan not found")

    query = select(AuditLogEntry).where(AuditLogEntry.scan_id == scan_id)
    if phase:
        query = query.where(AuditLogEntry.phase == phase)
    if service:
        query = query.where(AuditLogEntry.service == service)
    if log_status:
        query = query.where(AuditLogEntry.status == log_status)

    query = query.order_by(AuditLogEntry.timestamp.asc()).offset(offset).limit(limit)
    entries_result = await db.execute(query)
    return list(entries_result.scalars().all())


@router.websocket("/{scan_id}/ws")
async def scan_progress_ws(websocket: WebSocket, scan_id: uuid.UUID) -> None:
    await websocket.accept()

    if scan_id not in _progress_subscribers:
        _progress_subscribers[scan_id] = []
    _progress_subscribers[scan_id].append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _progress_subscribers[scan_id].remove(websocket)
        if not _progress_subscribers[scan_id]:
            del _progress_subscribers[scan_id]


async def broadcast_scan_progress(scan_id: uuid.UUID, data: dict) -> None:
    subscribers = _progress_subscribers.get(scan_id, [])
    disconnected = []
    for ws in subscribers:
        try:
            await ws.send_json(data)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        subscribers.remove(ws)
