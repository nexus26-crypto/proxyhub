import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.enums import LogLevel
from app.repositories.proxy_repository import ProxyRepository
from app.services.log_service import LogService
from app.services.proxy_service import ProxyService
from app.ws.manager import manager

logger = logging.getLogger("proxyhub.scheduler")

scheduler = AsyncIOScheduler()


async def run_proxy_healthcheck() -> None:
    """Verifica a saúde de todos os proxies ativos/em teste periodicamente."""
    async with AsyncSessionLocal() as session:
        repo = ProxyRepository(session)
        service = ProxyService(session)
        log_service = LogService(session)

        proxies = await repo.list_active_for_healthcheck()
        checked = 0
        for proxy in proxies:
            try:
                result = await service.test_proxy(proxy.id)
                checked += 1
                await manager.broadcast({
                    "type": "proxy_healthcheck",
                    "proxy_id": str(result.id),
                    "status": result.status,
                    "score": result.score,
                    "success": result.success,
                })
            except Exception as exc:  # noqa: BLE001
                logger.warning("Healthcheck failed for proxy %s: %s", proxy.id, exc)

        await log_service.add_log(
            f"Healthcheck concluido: {checked} proxies verificados",
            level=LogLevel.INFO, source="scheduler",
        )


def start_scheduler() -> None:
    scheduler.add_job(
        run_proxy_healthcheck,
        "interval",
        seconds=settings.PROXY_HEALTHCHECK_INTERVAL_SECONDS,
        id="proxy_healthcheck",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
