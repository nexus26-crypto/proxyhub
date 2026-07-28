import uuid

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_any
from app.models.user import User
from app.schemas.proxy import (
    ProxyCreate, ProxyImportResult, ProxyOut, ProxyTestResult, ProxyUpdate,
)
from app.services.proxy_service import ProxyService
from app.ws.manager import manager

router = APIRouter(prefix="/proxies", tags=["Proxies"])


@router.get("", response_model=list[ProxyOut])
async def list_proxies(
    status: str | None = None,
    offset: int = 0,
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_any),
):
    service = ProxyService(session)
    return await service.list_proxies(status, offset, limit)


@router.get("/{proxy_id}", response_model=ProxyOut)
async def get_proxy(proxy_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = ProxyService(session)
    return await service.get_proxy(proxy_id)


@router.post("", response_model=ProxyOut, status_code=201)
async def create_proxy(data: ProxyCreate, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    service = ProxyService(session)
    proxy = await service.create_proxy(data)
    await manager.broadcast({"type": "proxy_created", "proxy_id": str(proxy.id)})
    return proxy


@router.patch("/{proxy_id}", response_model=ProxyOut)
async def update_proxy(
    proxy_id: uuid.UUID, data: ProxyUpdate, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin),
):
    service = ProxyService(session)
    proxy = await service.update_proxy(proxy_id, data)
    await manager.broadcast({"type": "proxy_updated", "proxy_id": str(proxy.id)})
    return proxy


@router.delete("/{proxy_id}", status_code=204)
async def delete_proxy(proxy_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    service = ProxyService(session)
    await service.delete_proxy(proxy_id)
    await manager.broadcast({"type": "proxy_deleted", "proxy_id": str(proxy_id)})


@router.post("/{proxy_id}/test", response_model=ProxyTestResult)
async def test_proxy(proxy_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = ProxyService(session)
    result = await service.test_proxy(proxy_id)
    await manager.broadcast({"type": "proxy_tested", **result.model_dump()})
    return result


@router.post("/import", response_model=ProxyImportResult)
async def import_proxies(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    content = (await file.read()).decode("utf-8", errors="ignore")
    fmt = "csv" if file.filename and file.filename.lower().endswith(".csv") else "txt"
    service = ProxyService(session)
    result = await service.import_from_text(content, fmt=fmt)
    await manager.broadcast({"type": "proxy_import", "imported": result.imported})
    return result
