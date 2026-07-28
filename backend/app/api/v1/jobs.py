import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_any
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.job import JobCreate, JobOut
from app.services.job_service import JobService
from app.ws.manager import manager

router = APIRouter(prefix="/jobs", tags=["Jobs"])

SCRAPED_DATA_DIR = Path("/app/scraped_data")


@router.get("", response_model=list[JobOut])
async def list_jobs(
    status: str | None = None, offset: int = 0, limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_db), user: User = Depends(require_any),
):
    service = JobService(session)
    return await service.list_jobs(status, offset, limit)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = JobService(session)
    return await service.get_job(job_id)


@router.post("", response_model=JobOut, status_code=201)
async def create_job(data: JobCreate, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = JobService(session)
    job = await service.create_job(data)
    await manager.broadcast({"type": "job_created", "job_id": str(job.id)})
    return job


@router.post("/{job_id}/pause", response_model=JobOut)
async def pause_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = JobService(session)
    job = await service.pause_job(job_id)
    await manager.broadcast({"type": "job_paused", "job_id": str(job.id)})
    return job


@router.post("/{job_id}/resume", response_model=JobOut)
async def resume_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = JobService(session)
    job = await service.resume_job(job_id)
    await manager.broadcast({"type": "job_resumed", "job_id": str(job.id)})
    return job


@router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = JobService(session)
    job = await service.cancel_job(job_id)
    await manager.broadcast({"type": "job_cancelled", "job_id": str(job.id)})
    return job


@router.post("/{job_id}/retry", response_model=JobOut)
async def retry_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = JobService(session)
    job = await service.retry_job(job_id)
    await manager.broadcast({"type": "job_retried", "job_id": str(job.id)})
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    service = JobService(session)
    await service.delete_job(job_id)


@router.get("/{job_id}/result")
async def get_job_result(job_id: uuid.UUID, session: AsyncSession = Depends(get_db), user: User = Depends(require_any)):
    service = JobService(session)
    job = await service.get_job(job_id)  # 404 se nao existir
    file_path = SCRAPED_DATA_DIR / f"{job_id}.html"
    if not file_path.exists():
        raise NotFoundError("Resultado ainda nao disponivel para este job")
    return FileResponse(file_path, media_type="text/html", filename=f"{job.name}.html")
