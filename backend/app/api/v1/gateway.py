from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import require_any
from app.models.user import User

router = APIRouter(prefix="/gateway", tags=["Gateway"])


class GatewayInfo(BaseModel):
    port: int
    username: str
    password: str
    configured: bool


@router.get("/info", response_model=GatewayInfo)
async def get_gateway_info(user: User = Depends(require_any)):
    return GatewayInfo(
        port=settings.GATEWAY_PORT,
        username=settings.GATEWAY_USERNAME,
        password=settings.GATEWAY_PASSWORD,
        configured=bool(settings.GATEWAY_USERNAME and settings.GATEWAY_PASSWORD),
    )
