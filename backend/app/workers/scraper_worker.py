"""
Worker real de scraping do ProxyHub.

Roda em loop continuo, consumindo a fila de Jobs:
  1. Busca o proximo job com status "queued" (respeitando prioridade)
  2. Escolhe o proxy ativo com melhor score disponivel
  3. Faz o download do HTML da URL informada no payload do job, roteado pelo proxy
  4. Salva o resultado em /app/scraped_data/{job_id}.html
  5. Marca o job como finished/failed, com retry automatico ate max_retries

Uso:
    python -m app.workers.scraper_worker
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.core.database import AsyncSessionLocal
from app.models.enums import JobStatus, LogLevel, ProxyStatus, ProxyType
from app.repositories.job_repository import JobRepository
from app.repositories.proxy_repository import ProxyRepository
from app.repositories.worker_repository import WorkerRepository
from app.services.job_service import JobService
from app.services.log_service import LogService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("proxyhub.scraper_worker")

OUTPUT_DIR = Path("/app/scraped_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 20


def build_proxy_url(proxy) -> str:
    scheme = "http" if proxy.type in (ProxyType.HTTP.value, ProxyType.HTTPS.value) else proxy.type
    auth = f"{proxy.username}:{proxy.password}@" if proxy.username else ""
    return f"{scheme}://{auth}{proxy.host}:{proxy.port}"


async def pick_best_proxy(proxy_repo: ProxyRepository):
    """Escolhe o proxy ativo com maior score."""
    proxies = await proxy_repo.list_all(status=ProxyStatus.ACTIVE.value, offset=0, limit=200)
    if not proxies:
        return None
    return max(proxies, key=lambda p: p.score)


async def scrape_url(url: str, proxy) -> tuple[bool, str | None, str | None]:
    """Baixa o HTML da URL roteando pelo proxy. Retorna (sucesso, conteudo, erro)."""
    proxy_url = build_proxy_url(proxy)
    try:
        async with httpx.AsyncClient(proxies=proxy_url, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return True, response.text, None
            return False, None, f"HTTP {response.status_code}"
    except httpx.TimeoutException:
        return False, None, "Timeout ao acessar a URL via proxy"
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)[:500]


async def process_job(job) -> None:
    async with AsyncSessionLocal() as session:
        job_service = JobService(session)
        proxy_repo = ProxyRepository(session)
        log_service = LogService(session)

        url = (job.payload or {}).get("url")
        if not url:
            await job_service.start_job(job.id)
            await job_service.finish_job(job.id, success=False, error_message="payload.url ausente")
            await log_service.add_log(
                f"Job '{job.name}' sem URL no payload", level=LogLevel.ERROR, source="scraper_worker",
            )
            return

        proxy = await pick_best_proxy(proxy_repo)
        if not proxy:
            await job_service.start_job(job.id)
            await job_service.finish_job(job.id, success=False, error_message="Nenhum proxy ativo disponivel")
            await log_service.add_log(
                f"Job '{job.name}' falhou: nenhum proxy ativo", level=LogLevel.WARNING, source="scraper_worker",
            )
            return

        await job_service.start_job(job.id, worker_id=None, proxy_id=proxy.id)
        await log_service.add_log(
            f"Job '{job.name}' iniciado via proxy {proxy.host}:{proxy.port}",
            level=LogLevel.INFO, source="scraper_worker", proxy_id=proxy.id,
        )

        success, html, error = await scrape_url(url, proxy)

        if success:
            output_path = OUTPUT_DIR / f"{job.id}.html"
            output_path.write_text(html, encoding="utf-8", errors="ignore")
            await job_service.finish_job(job.id, success=True)
            await log_service.add_log(
                f"Job '{job.name}' concluido ({len(html)} bytes salvos em {output_path.name})",
                level=LogLevel.INFO, source="scraper_worker", proxy_id=proxy.id,
            )
        else:
            await job_service.finish_job(job.id, success=False, error_message=error)
            await log_service.add_log(
                f"Job '{job.name}' falhou: {error}",
                level=LogLevel.ERROR, source="scraper_worker", proxy_id=proxy.id,
            )


async def run_forever() -> None:
    logger.info("Scraper worker iniciado. Aguardando jobs na fila...")
    while True:
        try:
            async with AsyncSessionLocal() as session:
                job_repo = JobRepository(session)
                job = await job_repo.next_queued()

            if job:
                logger.info("Processando job %s (%s)", job.id, job.name)
                await process_job(job)
            else:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Erro inesperado no loop do worker: %s", exc)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_forever())
