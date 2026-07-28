import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ProxyStatus, ProxyType


class ProxyBase(BaseModel):
    host: str
    port: int = Field(gt=0, lt=65536)
    username: str | None = None
    password: str | None = None
    country: str | None = None
    provider: str | None = None
    asn: str | None = None
    type: ProxyType = ProxyType.HTTP


class ProxyCreate(ProxyBase):
    pass


class ProxyUpdate(BaseModel):
    host: str | None = None
    port: int | None = Field(default=None, gt=0, lt=65536)
    username: str | None = None
    password: str | None = None
    country: str | None = None
    provider: str | None = None
    asn: str | None = None
    type: ProxyType | None = None
    status: ProxyStatus | None = None


class ProxyOut(ProxyBase):
    id: uuid.UUID
    status: str
    score: float
    latency_ms: float | None
    success_count: int
    fail_count: int
    last_check: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProxyTestResult(BaseModel):
    id: uuid.UUID
    success: bool
    latency_ms: float | None
    message: str | None
    status: str
    score: float


class ProxyImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []
