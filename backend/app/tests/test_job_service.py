import uuid
from dataclasses import dataclass, field

import pytest

from app.core.exceptions import ValidationError
from app.models.enums import JobStatus
from app.services.job_service import JobService


@dataclass
class FakeJob:
    id: uuid.UUID
    status: str
    retries: int = 0
    max_retries: int = 3


class FakeRepo:
    def __init__(self, job: FakeJob):
        self.job = job

    async def update(self, obj, data: dict):
        for key, value in data.items():
            setattr(obj, key, value)
        return obj

    async def get(self, id_):
        return self.job if self.job.id == id_ else None


class FakeSession:
    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


def make_service(job: FakeJob) -> JobService:
    service = JobService.__new__(JobService)
    service.session = FakeSession()
    service.repo = FakeRepo(job)
    return service


@pytest.mark.asyncio
async def test_pause_running_job_succeeds():
    job = FakeJob(id=uuid.uuid4(), status=JobStatus.RUNNING.value)
    service = make_service(job)
    result = await service.pause_job(job.id)
    assert result.status == JobStatus.PAUSED.value


@pytest.mark.asyncio
async def test_cannot_pause_queued_job():
    job = FakeJob(id=uuid.uuid4(), status=JobStatus.QUEUED.value)
    service = make_service(job)
    with pytest.raises(ValidationError):
        await service.pause_job(job.id)


@pytest.mark.asyncio
async def test_resume_paused_job_succeeds():
    job = FakeJob(id=uuid.uuid4(), status=JobStatus.PAUSED.value)
    service = make_service(job)
    result = await service.resume_job(job.id)
    assert result.status == JobStatus.RUNNING.value


@pytest.mark.asyncio
async def test_cancel_from_finished_fails():
    job = FakeJob(id=uuid.uuid4(), status=JobStatus.FINISHED.value)
    service = make_service(job)
    with pytest.raises(ValidationError):
        await service.cancel_job(job.id)


@pytest.mark.asyncio
async def test_retry_respects_max_retries():
    job = FakeJob(id=uuid.uuid4(), status=JobStatus.FAILED.value, retries=3, max_retries=3)
    service = make_service(job)
    with pytest.raises(ValidationError):
        await service.retry_job(job.id)
