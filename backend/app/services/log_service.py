import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LogLevel
from app.models.log import Log
from app.repositories.log_repository import LogRepository


class LogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LogRepository(session)

    async def list_logs(self, level: str | None, offset: int, limit: int) -> list[Log]:
        return await self.repo.list_all(level=level, offset=offset, limit=limit)

    async def add_log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        source: str | None = None,
        worker_id: uuid.UUID | None = None,
        proxy_id: uuid.UUID | None = None,
    ) -> Log:
        log = Log(
            level=level.value, message=message, source=source,
            worker_id=worker_id, proxy_id=proxy_id,
        )
        return await self.repo.create(log)
