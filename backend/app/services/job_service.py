import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import JobStatus
from app.models.job import Job
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobCreate

_VALID_TRANSITIONS = {
    JobStatus.QUEUED.value: {JobStatus.RUNNING.value, JobStatus.CANCELLED.value},
    JobStatus.RUNNING.value: {JobStatus.PAUSED.value, JobStatus.FINISHED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value},
    JobStatus.PAUSED.value: {JobStatus.RUNNING.value, JobStatus.CANCELLED.value},
    JobStatus.FAILED.value: {JobStatus.QUEUED.value},
}


class JobService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = JobRepository(session)

    async def list_jobs(self, status: str | None, offset: int, limit: int) -> list[Job]:
        return await self.repo.list_all(status=status, offset=offset, limit=limit)

    async def get_job(self, job_id: uuid.UUID) -> Job:
        job = await self.repo.get(job_id)
        if not job:
            raise NotFoundError("Job not found")
        return job

    async def create_job(self, data: JobCreate) -> Job:
        job = Job(
            name=data.name,
            priority=data.priority.value,
            payload=data.payload,
            max_retries=data.max_retries,
            status=JobStatus.QUEUED.value,
        )
        return await self.repo.create(job)

    async def _transition(self, job: Job, new_status: str, **extra) -> Job:
        allowed = _VALID_TRANSITIONS.get(job.status, set())
        if new_status not in allowed:
            raise ValidationError(f"Cannot transition job from '{job.status}' to '{new_status}'")
        payload = {"status": new_status, **extra}
        return await self.repo.update(job, payload)

    async def pause_job(self, job_id: uuid.UUID) -> Job:
        job = await self.get_job(job_id)
        return await self._transition(job, JobStatus.PAUSED.value)

    async def resume_job(self, job_id: uuid.UUID) -> Job:
        job = await self.get_job(job_id)
        return await self._transition(job, JobStatus.RUNNING.value)

    async def cancel_job(self, job_id: uuid.UUID) -> Job:
        job = await self.get_job(job_id)
        return await self._transition(job, JobStatus.CANCELLED.value, finished_at=datetime.now(timezone.utc))

    async def start_job(self, job_id: uuid.UUID, worker_id: uuid.UUID | None = None, proxy_id: uuid.UUID | None = None) -> Job:
        job = await self.get_job(job_id)
        return await self._transition(
            job, JobStatus.RUNNING.value,
            worker_id=worker_id, proxy_id=proxy_id, started_at=datetime.now(timezone.utc),
        )

    async def finish_job(self, job_id: uuid.UUID, success: bool, error_message: str | None = None) -> Job:
        job = await self.get_job(job_id)
        status = JobStatus.FINISHED.value if success else JobStatus.FAILED.value
        return await self._transition(
            job, status, finished_at=datetime.now(timezone.utc), error_message=error_message,
        )

    async def retry_job(self, job_id: uuid.UUID) -> Job:
        job = await self.get_job(job_id)
        if job.retries >= job.max_retries:
            raise ValidationError("Max retries exceeded")
        job = await self._transition(job, JobStatus.QUEUED.value, error_message=None)
        job.retries += 1
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def delete_job(self, job_id: uuid.UUID) -> None:
        job = await self.get_job(job_id)
        await self.repo.delete(job)
