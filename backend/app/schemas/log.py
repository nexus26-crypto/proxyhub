import uuid
from datetime import datetime

from pydantic import BaseModel


class LogOut(BaseModel):
    id: uuid.UUID
    level: str
    message: str
    source: str | None
    worker_id: uuid.UUID | None
    proxy_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
