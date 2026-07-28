from sqlalchemy import select, func

from app.models.worker import Worker
from app.models.enums import WorkerStatus
from app.repositories.base import BaseRepository


class WorkerRepository(BaseRepository[Worker]):
    model = Worker

    async def counts_by_status(self) -> dict[str, int]:
        result = await self.session.execute(
            select(Worker.status, func.count()).group_by(Worker.status)
        )
        counts = {status.value: 0 for status in WorkerStatus}
        for status, count in result.all():
            counts[status] = count
        return counts
