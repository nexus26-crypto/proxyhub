from sqlalchemy import select, func

from app.models.job import Job
from app.models.enums import JobStatus, JobPriority
from app.repositories.base import BaseRepository

_PRIORITY_ORDER = {
    JobPriority.CRITICAL.value: 0,
    JobPriority.HIGH.value: 1,
    JobPriority.NORMAL.value: 2,
    JobPriority.LOW.value: 3,
}


class JobRepository(BaseRepository[Job]):
    model = Job

    async def list_all(self, status: str | None = None, offset: int = 0, limit: int = 100) -> list[Job]:
        query = select(Job)
        if status:
            query = query.where(Job.status == status)
        query = query.order_by(Job.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        jobs = list(result.scalars().all())
        jobs.sort(key=lambda j: _PRIORITY_ORDER.get(j.priority, 2))
        return jobs

    async def counts_by_status(self) -> dict[str, int]:
        result = await self.session.execute(
            select(Job.status, func.count()).group_by(Job.status)
        )
        counts = {status.value: 0 for status in JobStatus}
        for status, count in result.all():
            counts[status] = count
        return counts

    async def next_queued(self) -> Job | None:
        query = select(Job).where(Job.status == JobStatus.QUEUED.value)
        result = await self.session.execute(query)
        jobs = list(result.scalars().all())
        if not jobs:
            return None
        jobs.sort(key=lambda j: _PRIORITY_ORDER.get(j.priority, 2))
        return jobs[0]
