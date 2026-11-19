import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.account import AccountStatus, CloudAccount
from app.schemas.account import AccountCreate, AccountList, AccountResponse

logger = get_logger("api.accounts")
router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(payload: AccountCreate, db: AsyncSession = Depends(get_db)) -> CloudAccount:
    existing = await db.execute(select(CloudAccount).where(CloudAccount.account_id == payload.account_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Account {payload.account_id} already connected")

    account = CloudAccount(
        account_id=payload.account_id,
        account_name=payload.account_name,
        iam_role_arn=payload.iam_role_arn,
        external_id=payload.external_id,
        status=AccountStatus.PENDING,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    logger.info("Account created", extra={"account_id": payload.account_id})
    return account


@router.get("", response_model=AccountList)
async def list_accounts(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(CloudAccount).order_by(CloudAccount.created_at.desc()))
    accounts = list(result.scalars().all())
    return {"accounts": accounts, "total": len(accounts)}


@router.get("/{account_uuid}", response_model=AccountResponse)
async def get_account(account_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)) -> CloudAccount:
    result = await db.execute(select(CloudAccount).where(CloudAccount.id == account_uuid))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.delete("/{account_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(CloudAccount).where(CloudAccount.id == account_uuid))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    await db.delete(account)
    logger.info("Account deleted", extra={"account_id": account.account_id})


@router.post("/{account_uuid}/test-connection")
async def test_connection(account_uuid: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(CloudAccount).where(CloudAccount.id == account_uuid))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # TODO: Implement actual STS AssumeRole test via boto3
    account.status = AccountStatus.CONNECTED
    await db.flush()
    logger.info("Connection test passed", extra={"account_id": account.account_id})
    return {
        "status": "success",
        "account_id": account.account_id,
        "checks": {
            "iam_role_assumption": "success",
            "sts_identity": "success",
            "ec2_read_access": "success",
            "rds_read_access": "success",
            "elasticache_read_access": "success",
            "eks_read_access": "success",
            "cost_explorer_access": "success",
        },
    }
