import csv
import io
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import ProxyStatus, ProxyType
from app.models.proxy import Proxy, ProxyCheckHistory
from app.repositories.proxy_repository import ProxyRepository
from app.schemas.proxy import ProxyCreate, ProxyImportResult, ProxyTestResult, ProxyUpdate


def compute_score(success: int, fail: int, latency_ms: float | None) -> float:
    total = success + fail
    if total == 0:
        return 0.0
    success_rate = success / total
    latency_penalty = 0.0
    if latency_ms is not None:
        # normalize: 0ms -> 0 penalty, 5000ms+ -> heavy penalty
        latency_penalty = min(latency_ms / 5000, 1.0) * 0.3
    score = max(0.0, (success_rate * 0.7 + (1 - latency_penalty) * 0.3)) * 100
    return round(score, 2)


class ProxyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProxyRepository(session)

    async def list_proxies(self, status: str | None, offset: int, limit: int) -> list[Proxy]:
        return await self.repo.list_all(status=status, offset=offset, limit=limit)

    async def get_proxy(self, proxy_id: uuid.UUID) -> Proxy:
        proxy = await self.repo.get(proxy_id)
        if not proxy:
            raise NotFoundError("Proxy not found")
        return proxy

    async def create_proxy(self, data: ProxyCreate) -> Proxy:
        if await self.repo.get_by_host_port(data.host, data.port):
            raise ConflictError("Proxy with this host/port already exists")
        proxy = Proxy(**data.model_dump(exclude={"type"}), type=data.type.value)
        return await self.repo.create(proxy)

    async def update_proxy(self, proxy_id: uuid.UUID, data: ProxyUpdate) -> Proxy:
        proxy = await self.get_proxy(proxy_id)
        payload = data.model_dump(exclude_unset=True)
        if "type" in payload and payload["type"] is not None:
            payload["type"] = payload["type"].value if hasattr(payload["type"], "value") else payload["type"]
        if "status" in payload and payload["status"] is not None:
            payload["status"] = payload["status"].value if hasattr(payload["status"], "value") else payload["status"]
        return await self.repo.update(proxy, payload)

    async def delete_proxy(self, proxy_id: uuid.UUID) -> None:
        proxy = await self.get_proxy(proxy_id)
        await self.repo.delete(proxy)

    async def test_proxy(self, proxy_id: uuid.UUID) -> ProxyTestResult:
        proxy = await self.get_proxy(proxy_id)
        success, latency_ms, message = await self._check_connectivity(proxy)

        if success:
            proxy.success_count += 1
        else:
            proxy.fail_count += 1

        proxy.latency_ms = latency_ms
        proxy.last_check = datetime.now(timezone.utc)
        proxy.score = compute_score(proxy.success_count, proxy.fail_count, latency_ms)
        proxy.status = self._derive_status(proxy, success)

        self.session.add(ProxyCheckHistory(
            proxy_id=proxy.id, success=success, latency_ms=latency_ms, message=message,
        ))
        await self.session.commit()
        await self.session.refresh(proxy)

        return ProxyTestResult(
            id=proxy.id, success=success, latency_ms=latency_ms, message=message,
            status=proxy.status, score=proxy.score,
        )

    @staticmethod
    def _derive_status(proxy: Proxy, last_success: bool) -> str:
        if not last_success and proxy.fail_count >= 5 and proxy.success_count == 0:
            return ProxyStatus.BLOCKED.value
        return ProxyStatus.ACTIVE.value if last_success else ProxyStatus.INACTIVE.value

    @staticmethod
    async def _check_connectivity(proxy: Proxy) -> tuple[bool, float | None, str | None]:
        scheme = "http" if proxy.type in (ProxyType.HTTP.value, ProxyType.HTTPS.value) else proxy.type
        auth = f"{proxy.username}:{proxy.password}@" if proxy.username else ""
        proxy_url = f"{scheme}://{auth}{proxy.host}:{proxy.port}"

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                proxies=proxy_url, timeout=settings.PROXY_TEST_TIMEOUT_SECONDS
            ) as client:
                response = await client.get(settings.PROXY_TEST_URL)
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                if response.status_code == 200:
                    return True, latency_ms, "OK"
                return False, latency_ms, f"HTTP {response.status_code}"
        except httpx.TimeoutException:
            return False, None, "Timeout"
        except Exception as exc:  # noqa: BLE001
            return False, None, str(exc)[:255]

    async def import_from_text(self, content: str, fmt: str = "txt") -> ProxyImportResult:
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        imported, skipped, errors = 0, 0, []

        for idx, line in enumerate(lines, start=1):
            try:
                if fmt == "csv":
                    reader = csv.reader(io.StringIO(line))
                    row = next(reader)
                    host, port = row[0], int(row[1])
                    username = row[2] if len(row) > 2 else None
                    password = row[3] if len(row) > 3 else None
                else:
                    # formats: host:port or host:port:user:pass
                    parts = line.split(":")
                    host, port = parts[0], int(parts[1])
                    username = parts[2] if len(parts) > 2 else None
                    password = parts[3] if len(parts) > 3 else None

                if await self.repo.get_by_host_port(host, port):
                    skipped += 1
                    continue

                proxy = Proxy(
                    host=host, port=port, username=username, password=password,
                    type=ProxyType.HTTP.value, status=ProxyStatus.TESTING.value,
                )
                self.session.add(proxy)
                imported += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Line {idx}: {exc}")

        await self.session.commit()
        return ProxyImportResult(imported=imported, skipped=skipped, errors=errors)
