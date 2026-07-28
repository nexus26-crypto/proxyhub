import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import JobStatus, JobPriority


class JobCreate(BaseModel):
    name: str
    priority: JobPriority = JobPriority.NORMAL
    payload: dict[str, Any] = {}  # esperado: {"url": "https://exemplo.com"} para o scraper_worker
    max_retries: int = 3


class JobUpdate(BaseModel):
    status: JobStatus | None = None
    priority: JobPriority | None = None
    worker_id: uuid.UUID | None = None
    proxy_id: uuid.UUID | None = None
    error_message: str | None = None


class JobOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    priority: str
    payload: dict[str, Any]
    worker_id: uuid.UUID | None
    proxy_id: uuid.UUID | None
    retries: int
    max_retries: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}
