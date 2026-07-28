import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_any
from app.models.user import User
from app.schemas.worker import WorkerCreate, WorkerOut, WorkerUpdate
from app.services.worker_service import WorkerService
from app.ws.manager import manager

router = APIRouter(prefix="/workers", tags=["Workers"])


@router.get("", response_model=list[WorkerOut])
async def list_workers(
    offset: int = 0, limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_db), user: User = Depends(require_any),
):
    service = WorkerService(session)
    return await service.list_workers(offset, limit)


@router.get("/{worker_id}", response_model=WorkerOut)
async def get_worker(worker_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = WorkerService(session)
    return await service.get_worker(worker_id)


@router.post("", response_model=WorkerOut, status_code=201)
async def create_worker(data: WorkerCreate, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    service = WorkerService(session)
    return await service.create_worker(data)


@router.patch("/{worker_id}", response_model=WorkerOut)
async def update_worker(
    worker_id: uuid.UUID, data: WorkerUpdate, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin),
):
    service = WorkerService(session)
    worker = await service.update_worker(worker_id, data)
    await manager.broadcast({"type": "worker_updated", "worker_id": str(worker.id), "status": worker.status})
    return worker


@router.delete("/{worker_id}", status_code=204)
async def delete_worker(worker_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    service = WorkerService(session)
    await service.delete_worker(worker_id)


@router.post("/{worker_id}/start", response_model=WorkerOut)
async def start_worker(worker_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    service = WorkerService(session)
    worker = await service.start_worker(worker_id)
    await manager.broadcast({"type": "worker_started", "worker_id": str(worker.id)})
    return worker


@router.post("/{worker_id}/stop", response_model=WorkerOut)
async def stop_worker(worker_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    service = WorkerService(session)
    worker = await service.stop_worker(worker_id)
    await manager.broadcast({"type": "worker_stopped", "worker_id": str(worker.id)})
    return worker


@router.post("/{worker_id}/restart", response_model=WorkerOut)
async def restart_worker(worker_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    service = WorkerService(session)
    worker = await service.restart_worker(worker_id)
    await manager.broadcast({"type": "worker_restarted", "worker_id": str(worker.id)})
    return worker
