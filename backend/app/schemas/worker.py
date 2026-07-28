import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import WorkerStatus


class WorkerCreate(BaseModel):
    name: str
    proxy_id: uuid.UUID | None = None


class WorkerUpdate(BaseModel):
    name: str | None = None
    status: WorkerStatus | None = None
    proxy_id: uuid.UUID | None = None
    cpu_usage: float | None = None
    ram_usage_mb: float | None = None
    requests_count: int | None = None
    errors_count: int | None = None


class WorkerOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    proxy_id: uuid.UUID | None
    cpu_usage: float
    ram_usage_mb: float
    requests_count: int
    errors_count: int
    started_at: datetime | None
    last_heartbeat: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
