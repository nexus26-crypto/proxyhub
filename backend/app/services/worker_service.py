import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.enums import WorkerStatus
from app.models.worker import Worker
from app.repositories.worker_repository import WorkerRepository
from app.schemas.worker import WorkerCreate, WorkerUpdate


class WorkerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = WorkerRepository(session)

    async def list_workers(self, offset: int, limit: int) -> list[Worker]:
        return await self.repo.list(offset=offset, limit=limit)

    async def get_worker(self, worker_id: uuid.UUID) -> Worker:
        worker = await self.repo.get(worker_id)
        if not worker:
            raise NotFoundError("Worker not found")
        return worker

    async def create_worker(self, data: WorkerCreate) -> Worker:
        worker = Worker(
            name=data.name,
            proxy_id=data.proxy_id,
            status=WorkerStatus.OFFLINE.value,
        )
        return await self.repo.create(worker)

    async def update_worker(self, worker_id: uuid.UUID, data: WorkerUpdate) -> Worker:
        worker = await self.get_worker(worker_id)
        payload = data.model_dump(exclude_unset=True)
        if "status" in payload and payload["status"] is not None:
            payload["status"] = payload["status"].value if hasattr(payload["status"], "value") else payload["status"]
        return await self.repo.update(worker, payload)

    async def delete_worker(self, worker_id: uuid.UUID) -> None:
        worker = await self.get_worker(worker_id)
        await self.repo.delete(worker)

    async def start_worker(self, worker_id: uuid.UUID) -> Worker:
        worker = await self.get_worker(worker_id)
        return await self.repo.update(worker, {
            "status": WorkerStatus.ONLINE.value,
            "started_at": datetime.now(timezone.utc),
            "last_heartbeat": datetime.now(timezone.utc),
        })

    async def stop_worker(self, worker_id: uuid.UUID) -> Worker:
        worker = await self.get_worker(worker_id)
        return await self.repo.update(worker, {"status": WorkerStatus.STOPPED.value})

    async def restart_worker(self, worker_id: uuid.UUID) -> Worker:
        worker = await self.get_worker(worker_id)
        return await self.repo.update(worker, {
            "status": WorkerStatus.ONLINE.value,
            "started_at": datetime.now(timezone.utc),
            "cpu_usage": 0.0,
            "ram_usage_mb": 0.0,
            "errors_count": 0,
        })

    async def heartbeat(self, worker_id: uuid.UUID, cpu: float, ram: float) -> Worker:
        worker = await self.get_worker(worker_id)
        return await self.repo.update(worker, {
            "cpu_usage": cpu,
            "ram_usage_mb": ram,
            "last_heartbeat": datetime.now(timezone.utc),
        })
