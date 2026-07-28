"""
Gateway de Proxy Rotativo do ProxyHub.

Expoe um UNICO endpoint de proxy (HTTP/HTTPS) que, a cada nova conexao,
escolhe (rotaciona) um dos proxies ativos cadastrados no ProxyHub e
encaminha o trafego atraves dele.

Uso pratico: configure seu bot/script/navegador para usar como proxy:
    http://<usuario_gateway>:<senha_gateway>@<ip_da_vps>:8080

Cada nova conexao (cada requisicao HTTPS via CONNECT, ou cada requisicao
HTTP) sera roteada por um proxy diferente dentre os cadastrados e ativos,
sorteado com peso pelo score. Assim seu IP real nunca aparece e o mesmo
proxy nao fica sendo usado o tempo todo.

Uso:
    python -m app.workers.proxy_gateway
"""
import asyncio
import base64
import logging
import os
import random

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.enums import ProxyStatus
from app.models.proxy import Proxy, ProxyCheckHistory
from app.repositories.proxy_repository import ProxyRepository
from app.services.proxy_service import compute_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("proxyhub.gateway")

GATEWAY_HOST = "0.0.0.0"
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8080"))
GATEWAY_USERNAME = os.getenv("GATEWAY_USERNAME", "")
GATEWAY_PASSWORD = os.getenv("GATEWAY_PASSWORD", "")
CONNECT_TIMEOUT_SECONDS = 15
MAX_GATEWAY_RETRIES = int(os.getenv("GATEWAY_MAX_RETRIES", "3"))


async def pick_rotating_proxy(exclude_ids: set | None = None):
    """
    Sorteia um proxy ativo, ponderado pelo score (rotacao real a cada chamada).
    exclude_ids: ids de proxies ja tentados nesta requisicao (para retry automatico).
    """
    exclude_ids = exclude_ids or set()
    async with AsyncSessionLocal() as session:
        repo = ProxyRepository(session)
        proxies = await repo.list_all(status=ProxyStatus.ACTIVE.value, offset=0, limit=200)
        proxies = [p for p in proxies if p.id not in exclude_ids] or proxies
        if not proxies:
            return None
        if len(proxies) == 1:
            return proxies[0]
        weights = [max(p.score, 1.0) for p in proxies]
        return random.choices(proxies, weights=weights, k=1)[0]


async def record_proxy_outcome(proxy_id, success: bool, reason: str | None = None) -> None:
    """
    Feedback loop em tempo real: toda vez que o gateway usa um proxy (sucesso
    ou falha), atualiza score/status/contadores imediatamente no banco --
    em vez de esperar o proximo ciclo do scheduler (ate 5 min). Assim proxies
    instaveis perdem peso na rotacao rapidamente.
    """
    try:
        async with AsyncSessionLocal() as session:
            proxy = await session.get(Proxy, proxy_id)
            if not proxy:
                return

            if success:
                proxy.success_count += 1
            else:
                proxy.fail_count += 1

            proxy.score = compute_score(proxy.success_count, proxy.fail_count, proxy.latency_ms)

            # nao rebaixa para blocked aqui (isso e papel do healthcheck oficial,
            # que faz teste real); so ajusta o score para reduzir peso na rotacao
            if not success and proxy.fail_count >= 5 and proxy.success_count == 0:
                proxy.status = ProxyStatus.BLOCKED.value
            elif success and proxy.status != ProxyStatus.ACTIVE.value:
                proxy.status = ProxyStatus.ACTIVE.value

            session.add(ProxyCheckHistory(
                proxy_id=proxy.id, success=success, latency_ms=proxy.latency_ms,
                message=(reason or "OK")[:255],
            ))
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao registrar feedback do proxy %s: %s", proxy_id, exc)


def check_gateway_auth(headers: dict[str, str]) -> bool:
    """Valida o header Proxy-Authorization enviado pelo cliente (seu bot)."""
    if not GATEWAY_USERNAME:  # sem auth configurada = aberto (nao recomendado em producao)
        return True
    auth_header = headers.get("proxy-authorization", "")
    if not auth_header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode()
        user, _, pwd = decoded.partition(":")
        return user == GATEWAY_USERNAME and pwd == GATEWAY_PASSWORD
    except Exception:  # noqa: BLE001
        return False


async def read_headers(reader: asyncio.StreamReader) -> tuple[str, dict[str, str], bytes]:
    """Le a request line + headers do cliente. Retorna (request_line, headers, raw_bytes)."""
    raw = b""
    while b"\r\n\r\n" not in raw:
        chunk = await reader.read(4096)
        if not chunk:
            break
        raw += chunk
    head, _, rest = raw.partition(b"\r\n\r\n")
    lines = head.decode(errors="ignore").split("\r\n")
    request_line = lines[0] if lines else ""
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return request_line, headers, raw


async def relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


async def try_connect_upstream(target_host: str, target_port: int, proxy):
    """
    Tenta abrir o tunel CONNECT no proxy upstream, SEM escrever nada ao cliente ainda.
    Retorna (sucesso, upstream_reader, upstream_writer, motivo_falha).
    Seguro para retry: nao ha efeito colateral no cliente nem no alvo se falhar aqui.
    """
    try:
        upstream_reader, upstream_writer = await asyncio.wait_for(
            asyncio.open_connection(proxy.host, proxy.port), timeout=CONNECT_TIMEOUT_SECONDS
        )
    except Exception as exc:  # noqa: BLE001
        return False, None, None, f"falha ao conectar no proxy: {exc}"

    connect_req = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\nHost: {target_host}:{target_port}\r\n"
    if proxy.username:
        cred = base64.b64encode(f"{proxy.username}:{proxy.password}".encode()).decode()
        connect_req += f"Proxy-Authorization: Basic {cred}\r\n"
    connect_req += "Proxy-Connection: Keep-Alive\r\n\r\n"

    try:
        upstream_writer.write(connect_req.encode())
        await upstream_writer.drain()
        response = await asyncio.wait_for(upstream_reader.readuntil(b"\r\n\r\n"), timeout=CONNECT_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001
        upstream_writer.close()
        return False, None, None, f"falha no handshake CONNECT: {exc}"

    if b"200" not in response.split(b"\r\n", 1)[0]:
        upstream_writer.close()
        return False, None, None, f"proxy recusou CONNECT: {response[:100]}"

    return True, upstream_reader, upstream_writer, None


async def handle_connect(client_reader, client_writer, target_host: str, target_port: int) -> None:
    """
    Estabelece tunel HTTPS com retry automatico: se um proxy falhar, tenta outro
    ate MAX_GATEWAY_RETRIES vezes antes de desistir e responder erro ao cliente.
    """
    tried_ids: set = set()
    last_reason = "nenhum proxy ativo disponivel"

    for attempt in range(1, MAX_GATEWAY_RETRIES + 1):
        proxy = await pick_rotating_proxy(exclude_ids=tried_ids)
        if not proxy:
            break
        tried_ids.add(proxy.id)

        success, upstream_reader, upstream_writer, reason = await try_connect_upstream(
            target_host, target_port, proxy
        )
        await record_proxy_outcome(proxy.id, success, reason)

        if success:
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()
            logger.info(
                "Tunel HTTPS %s:%s via proxy %s:%s (tentativa %d/%d)",
                target_host, target_port, proxy.host, proxy.port, attempt, MAX_GATEWAY_RETRIES,
            )
            await asyncio.gather(
                relay(client_reader, upstream_writer),
                relay(upstream_reader, client_writer),
                return_exceptions=True,
            )
            return

        last_reason = reason
        logger.warning(
            "Tentativa %d/%d falhou (proxy %s:%s): %s -- tentando outro proxy",
            attempt, MAX_GATEWAY_RETRIES, proxy.host, proxy.port, reason,
        )

    logger.error("Todas as %d tentativas falharam para %s:%s (%s)", MAX_GATEWAY_RETRIES, target_host, target_port, last_reason)
    client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
    await client_writer.drain()
    client_writer.close()


async def handle_plain_http(client_reader, client_writer, request_line, headers, raw_head) -> None:
    """
    Encaminha requisicao HTTP simples atraves do proxy upstream, com retry
    automatico apenas na fase de CONEXAO ao proxy (segura: nada foi enviado
    ainda ao alvo). Uma vez que a requisicao e enviada, nao ha retry -- evita
    duplicar efeitos colaterais em metodos nao-idempotentes (POST, etc).
    """
    tried_ids: set = set()

    for attempt in range(1, MAX_GATEWAY_RETRIES + 1):
        proxy = await pick_rotating_proxy(exclude_ids=tried_ids)
        if not proxy:
            break
        tried_ids.add(proxy.id)

        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.host, proxy.port), timeout=CONNECT_TIMEOUT_SECONDS
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Tentativa %d/%d: falha ao conectar no proxy %s:%s -> %s -- tentando outro",
                attempt, MAX_GATEWAY_RETRIES, proxy.host, proxy.port, exc,
            )
            await record_proxy_outcome(proxy.id, False, str(exc))
            continue

        await record_proxy_outcome(proxy.id, True)
        head = raw_head
        if proxy.username:
            cred = base64.b64encode(f"{proxy.username}:{proxy.password}".encode()).decode()
            head = head.replace(b"\r\n\r\n", f"\r\nProxy-Authorization: Basic {cred}\r\n\r\n".encode(), 1)

        upstream_writer.write(head)
        await upstream_writer.drain()

        logger.info("HTTP %s via proxy %s:%s (tentativa %d/%d)", request_line, proxy.host, proxy.port, attempt, MAX_GATEWAY_RETRIES)

        await asyncio.gather(
            relay(client_reader, upstream_writer),
            relay(upstream_reader, client_writer),
            return_exceptions=True,
        )
        return

    logger.error("Todas as %d tentativas de conexao ao proxy falharam para requisicao HTTP", MAX_GATEWAY_RETRIES)
    client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
    await client_writer.drain()
    client_writer.close()


async def handle_client(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    try:
        request_line, headers, raw_head = await read_headers(client_reader)
        if not request_line:
            client_writer.close()
            return

        if not check_gateway_auth(headers):
            client_writer.write(
                b'HTTP/1.1 407 Proxy Authentication Required\r\n'
                b'Proxy-Authenticate: Basic realm="ProxyHub Gateway"\r\n\r\n'
            )
            await client_writer.drain()
            client_writer.close()
            return

        proxy_check = await pick_rotating_proxy()
        if not proxy_check:
            logger.warning("Nenhum proxy ativo disponivel para rotear a requisicao")
            client_writer.write(b"HTTP/1.1 503 Service Unavailable\r\n\r\nNenhum proxy ativo disponivel")
            await client_writer.drain()
            client_writer.close()
            return

        method = request_line.split(" ", 1)[0].upper()

        if method == "CONNECT":
            target = request_line.split(" ")[1]
            target_host, _, target_port = target.partition(":")
            target_port = int(target_port) if target_port else 443
            await handle_connect(client_reader, client_writer, target_host, target_port)
        else:
            await handle_plain_http(client_reader, client_writer, request_line, headers, raw_head)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro tratando conexao do cliente: %s", exc)
        try:
            client_writer.close()
        except Exception:  # noqa: BLE001
            pass


async def main() -> None:
    if not GATEWAY_USERNAME:
        logger.warning(
            "GATEWAY_USERNAME/GATEWAY_PASSWORD nao configurados no .env -> gateway "
            "esta ABERTO sem autenticacao. Configure para uso em producao."
        )
    server = await asyncio.start_server(handle_client, GATEWAY_HOST, GATEWAY_PORT)
    logger.info("Proxy Gateway rotativo ouvindo em %s:%s", GATEWAY_HOST, GATEWAY_PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
