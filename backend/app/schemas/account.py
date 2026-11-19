import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.account import AccountStatus


class AccountCreate(BaseModel):
    account_id: str = Field(..., min_length=12, max_length=12, pattern=r"^\d{12}$")
    iam_role_arn: str = Field(..., pattern=r"^arn:aws:iam::\d{12}:role/.+$")
    external_id: str = Field(..., min_length=8, max_length=128)
    account_name: str | None = None


class AccountResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    account_id: str
    account_name: str | None
    iam_role_arn: str
    external_id: str
    status: AccountStatus
    regions_enabled: list[str] | None
    created_at: datetime
    updated_at: datetime


class AccountList(BaseModel):
    accounts: list[AccountResponse]
    total: int
