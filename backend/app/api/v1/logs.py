from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_any
from app.models.user import User
from app.schemas.log import LogOut
from app.services.log_service import LogService

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("", response_model=list[LogOut])
async def list_logs(
    level: str | None = None, offset: int = 0, limit: int = Query(default=200, le=1000),
    session: AsyncSession = Depends(get_db), user: User = Depends(require_any),
):
    service = LogService(session)
    return await service.list_logs(level, offset, limit)
