from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_any
from app.models.user import User
from app.schemas.dashboard import DashboardOut
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardOut)
async def get_dashboard(session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = DashboardService(session)
    return await service.get_metrics()
