from sqlalchemy import select

from app.models.log import Log
from app.repositories.base import BaseRepository


class LogRepository(BaseRepository[Log]):
    model = Log

    async def list_all(
        self, level: str | None = None, offset: int = 0, limit: int = 200
    ) -> list[Log]:
        query = select(Log)
        if level:
            query = query.where(Log.level == level)
        query = query.order_by(Log.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
