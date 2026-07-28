from sqlalchemy import select, func

from app.models.proxy import Proxy
from app.models.enums import ProxyStatus
from app.repositories.base import BaseRepository


class ProxyRepository(BaseRepository[Proxy]):
    model = Proxy

    async def get_by_host_port(self, host: str, port: int) -> Proxy | None:
        result = await self.session.execute(
            select(Proxy).where(Proxy.host == host, Proxy.port == port)
        )
        return result.scalar_one_or_none()

    async def list_all(self, status: str | None = None, offset: int = 0, limit: int = 100) -> list[Proxy]:
        query = select(Proxy)
        if status:
            query = query.where(Proxy.status == status)
        query = query.order_by(Proxy.score.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def counts_by_status(self) -> dict[str, int]:
        result = await self.session.execute(
            select(Proxy.status, func.count()).group_by(Proxy.status)
        )
        counts = {status.value: 0 for status in ProxyStatus}
        for status, count in result.all():
            counts[status] = count
        return counts

    async def list_active_for_healthcheck(self) -> list[Proxy]:
        result = await self.session.execute(
            select(Proxy).where(Proxy.status != ProxyStatus.BLOCKED.value)
        )
        return list(result.scalars().all())
