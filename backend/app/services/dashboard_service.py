import psutil
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import redis_client
from app.repositories.proxy_repository import ProxyRepository
from app.schemas.dashboard import DashboardOut, GatewayMetrics, ProxyMetrics, SystemMetrics


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.proxy_repo = ProxyRepository(session)

    async def get_metrics(self) -> DashboardOut:
        vm = psutil.virtual_memory()

        redis_ok = False
        try:
            redis_ok = await redis_client.ping()
        except Exception:  # noqa: BLE001
            redis_ok = False

        postgres_ok = False
        try:
            await self.session.execute(text("SELECT 1"))
            postgres_ok = True
        except Exception:  # noqa: BLE001
            postgres_ok = False

        system = SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=0.1),
            ram_percent=vm.percent,
            ram_used_mb=round(vm.used / (1024 * 1024), 2),
            ram_total_mb=round(vm.total / (1024 * 1024), 2),
            redis_ok=redis_ok,
            postgres_ok=postgres_ok,
        )

        proxy_counts = await self.proxy_repo.counts_by_status()
        proxies = ProxyMetrics(
            total=sum(proxy_counts.values()),
            active=proxy_counts.get("active", 0),
            inactive=proxy_counts.get("inactive", 0),
            blocked=proxy_counts.get("blocked", 0),
            testing=proxy_counts.get("testing", 0),
        )

        return DashboardOut(system=system, proxies=proxies, gateway=await self._gateway_metrics())

    async def _gateway_metrics(self) -> GatewayMetrics:
        try:
            requests_total, bytes_in, bytes_out = await redis_client.mget(
                "gateway:requests_total", "gateway:bytes_in", "gateway:bytes_out"
            )
        except Exception:  # noqa: BLE001
            requests_total, bytes_in, bytes_out = None, None, None

        requests_total = int(requests_total or 0)
        bytes_in = int(bytes_in or 0)
        bytes_out = int(bytes_out or 0)

        return GatewayMetrics(
            requests_total=requests_total,
            bytes_in_mb=round(bytes_in / (1024 * 1024), 2),
            bytes_out_mb=round(bytes_out / (1024 * 1024), 2),
            bytes_total_mb=round((bytes_in + bytes_out) / (1024 * 1024), 2),
        )
