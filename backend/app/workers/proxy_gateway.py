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
from app.core.redis_client import redis_client
from app.models.enums import LogLevel, ProxyStatus
from app.models.log import Log
from app.models.proxy import Proxy, ProxyCheckHistory
from app.repositories.proxy_repository import ProxyRepository
from app.services.proxy_service import compute_score, derive_status_from_recent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("proxyhub.gateway")

GATEWAY_HOST = "0.0.0.0"
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8080"))
GATEWAY_USERNAME = os.getenv("GATEWAY_USERNAME", "")
GATEWAY_PASSWORD = os.getenv("GATEWAY_PASSWORD", "")
CONNECT_TIMEOUT_SECONDS = 15
MAX_GATEWAY_RETRIES = int(os.getenv("GATEWAY_MAX_RETRIES", "3"))
LOG_SUCCESS = os.getenv("GATEWAY_LOG_SUCCESS", "true").lower() in ("1", "true", "yes")


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


async def record_proxy_outcome(proxy_id, success: bool, reason: str | None = None, target: str | None = None) -> None:
    """
    Feedback loop em tempo real: toda vez que o gateway usa um proxy (sucesso
    ou falha), atualiza score/status/contadores imediatamente no banco --
    em vez de esperar o proximo ciclo do scheduler (ate 5 min). Assim proxies
    instaveis perdem peso na rotacao rapidamente.

    Tambem grava um registro na tabela de Logs (visivel na aba Logs da interface):
    falhas sempre sao logadas; sucessos sao logados conforme GATEWAY_LOG_SUCCESS
    (default: true). Desative via .env se o volume de requisicoes for muito alto
    e voce so quiser ver falhas/retries na interface.
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

            repo = ProxyRepository(session)
            recent = await repo.get_recent_outcomes(proxy.id, limit=4)  # anteriores a este resultado
            proxy.status = derive_status_from_recent([success, *recent])

            session.add(ProxyCheckHistory(
                proxy_id=proxy.id, success=success, latency_ms=proxy.latency_ms,
                message=(reason or "OK")[:255],
            ))

            if not success or LOG_SUCCESS:
                target_info = f" -> {target}" if target else ""
                message = (
                    f"Gateway: proxy {proxy.host}:{proxy.port} OK{target_info}"
                    if success
                    else f"Gateway: proxy {proxy.host}:{proxy.port} FALHOU{target_info} -- {reason}"
                )
                session.add(Log(
                    level=(LogLevel.INFO if success else LogLevel.WARNING).value,
                    message=message[:1000],
                    source="gateway",
                    proxy_id=proxy.id,
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


async def relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> int:
    """Encaminha bytes de reader para writer ate a conexao fechar. Retorna total de bytes."""
    total = 0
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
            total += len(data)
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass
    return total


async def record_bandwidth(bytes_in: int, bytes_out: int) -> None:
    """Acumula bytes trafegados pelo gateway no Redis (compartilhado com o Dashboard)."""
    try:
        pipe = redis_client.pipeline()
        pipe.incrby("gateway:bytes_in", bytes_in)
        pipe.incrby("gateway:bytes_out", bytes_out)
        pipe.incr("gateway:requests_total")
        await pipe.execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao registrar banda no Redis: %s", exc)


async def socks5_connect_upstream(target_host: str, target_port: int, proxy):
    """
    Abre um tunel para target_host:target_port atraves de um proxy SOCKS5
    upstream (RFC 1928 / RFC 1929 para autenticacao usuario/senha).
    Retorna (sucesso, upstream_reader, upstream_writer, motivo_falha).
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(proxy.host, proxy.port), timeout=CONNECT_TIMEOUT_SECONDS
        )
    except Exception as exc:  # noqa: BLE001
        return False, None, None, f"falha ao conectar no proxy SOCKS5: {exc}"

    try:
        # --- Saudacao / negociacao de metodo de autenticacao ---
        if proxy.username:
            greeting = bytes([0x05, 0x02, 0x00, 0x02])  # suporta "sem auth" e "user/pass"
        else:
            greeting = bytes([0x05, 0x01, 0x00])
        writer.write(greeting)
        await writer.drain()

        resp = await asyncio.wait_for(reader.readexactly(2), timeout=CONNECT_TIMEOUT_SECONDS)
        if resp[0] != 0x05:
            writer.close()
            return False, None, None, f"proxy nao fala SOCKS5 (resposta: {resp!r})"

        method = resp[1]
        if method == 0x02:  # usuario/senha exigido
            user_bytes = (proxy.username or "").encode()
            pass_bytes = (proxy.password or "").encode()
            auth_req = bytes([0x01, len(user_bytes)]) + user_bytes + bytes([len(pass_bytes)]) + pass_bytes
            writer.write(auth_req)
            await writer.drain()
            auth_resp = await asyncio.wait_for(reader.readexactly(2), timeout=CONNECT_TIMEOUT_SECONDS)
            if auth_resp[1] != 0x00:
                writer.close()
                return False, None, None, "autenticacao SOCKS5 (usuario/senha) rejeitada pelo proxy"
        elif method == 0xFF:
            writer.close()
            return False, None, None, "proxy SOCKS5 nao aceitou nenhum metodo de autenticacao oferecido"

        # --- Pedido de CONNECT ---
        host_bytes = target_host.encode()
        request = bytes([0x05, 0x01, 0x00, 0x03, len(host_bytes)]) + host_bytes + target_port.to_bytes(2, "big")
        writer.write(request)
        await writer.drain()

        reply_head = await asyncio.wait_for(reader.readexactly(4), timeout=CONNECT_TIMEOUT_SECONDS)
        if reply_head[0] != 0x05:
            writer.close()
            return False, None, None, "resposta invalida do proxy SOCKS5 ao CONNECT"
        if reply_head[1] != 0x00:
            reasons = {
                0x01: "erro geral no proxy", 0x02: "conexao nao permitida por regra do proxy",
                0x03: "rede inalcancavel", 0x04: "host inalcancavel", 0x05: "conexao recusada pelo alvo",
                0x06: "TTL expirado", 0x07: "comando nao suportado", 0x08: "tipo de endereco nao suportado",
            }
            writer.close()
            return False, None, None, f"SOCKS5 CONNECT falhou: {reasons.get(reply_head[1], 'erro desconhecido')}"

        # consome o restante da resposta (endereco/porta ligados, tamanho variavel conforme ATYP)
        atyp = reply_head[3]
        if atyp == 0x01:
            await reader.readexactly(4 + 2)
        elif atyp == 0x03:
            length = await reader.readexactly(1)
            await reader.readexactly(length[0] + 2)
        elif atyp == 0x04:
            await reader.readexactly(16 + 2)

        return True, reader, writer, None
    except Exception as exc:  # noqa: BLE001
        writer.close()
        return False, None, None, f"falha no handshake SOCKS5: {exc}"


async def try_connect_upstream(target_host: str, target_port: int, proxy):
    """
    Tenta abrir o tunel ate target_host:target_port atraves do proxy upstream,
    escolhendo o protocolo correto (HTTP CONNECT ou SOCKS5) conforme proxy.type.
    SEM escrever nada ao cliente ainda -- seguro para retry.
    Retorna (sucesso, upstream_reader, upstream_writer, motivo_falha).
    """
    if proxy.type in ("socks5", "socks4"):
        if proxy.type == "socks4":
            return False, None, None, "SOCKS4 ainda nao e suportado pelo gateway (use SOCKS5 ou HTTP)"
        return await socks5_connect_upstream(target_host, target_port, proxy)

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
        await record_proxy_outcome(proxy.id, success, reason, target=f"{target_host}:{target_port}")

        if success:
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()
            logger.info(
                "Tunel HTTPS %s:%s via proxy %s:%s (tentativa %d/%d)",
                target_host, target_port, proxy.host, proxy.port, attempt, MAX_GATEWAY_RETRIES,
            )
            results = await asyncio.gather(
                relay(client_reader, upstream_writer),
                relay(upstream_reader, client_writer),
                return_exceptions=True,
            )
            bytes_in = results[0] if isinstance(results[0], int) else 0
            bytes_out = results[1] if isinstance(results[1], int) else 0
            await record_bandwidth(bytes_in, bytes_out)
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


def _parse_target_from_request(request_line: str, headers: dict[str, str]) -> tuple[str, int, bytes] | None:
    """
    Extrai host/porta do alvo a partir da request-line (forma absoluta,
    ex: 'GET http://host:port/path HTTP/1.1') ou do header Host, e devolve
    tambem a request-line reescrita em forma de origem (ex: 'GET /path HTTP/1.1'),
    necessaria para encaminhar atraves de um tunel SOCKS5.
    """
    try:
        method, url, version = request_line.split(" ", 2)
    except ValueError:
        return None

    if url.startswith("http://") or url.startswith("https://"):
        rest = url.split("://", 1)[1]
        host_port, _, path = rest.partition("/")
        path = "/" + path
        host, _, port_str = host_port.partition(":")
        port = int(port_str) if port_str else 80
    else:
        host_header = headers.get("host", "")
        host, _, port_str = host_header.partition(":")
        port = int(port_str) if port_str else 80
        path = url

    origin_form_line = f"{method} {path} {version}".encode()
    return host, port, origin_form_line


async def strip_client_proxy_headers(raw_head: bytes) -> bytes:
    """
    Remove headers destinados APENAS a autenticar no nosso Gateway
    (Proxy-Authorization do cliente, Proxy-Connection) antes de repassar a
    requisicao para o proxy upstream real. Sem isso, o proxy upstream recebe
    a credencial do CLIENTE (que autentica no Gateway, nao nele) junto com a
    nossa propria credencial injetada, e pode rejeitar com o 407 dele mesmo.
    """
    head, _, rest = raw_head.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    filtered = [
        line for line in lines
        if not line.lower().startswith(b"proxy-authorization:")
        and not line.lower().startswith(b"proxy-connection:")
    ]
    return b"\r\n".join(filtered) + b"\r\n\r\n" + rest


async def handle_plain_http(client_reader, client_writer, request_line, headers, raw_head) -> None:
    """
    Encaminha requisicao HTTP simples atraves do proxy upstream (HTTP ou SOCKS5),
    com retry automatico apenas na fase de CONEXAO ao proxy (segura: nada foi
    enviado ainda ao alvo). Uma vez que a requisicao e enviada, nao ha retry --
    evita duplicar efeitos colaterais em metodos nao-idempotentes (POST, etc).
    """
    target = _parse_target_from_request(request_line, headers)
    if not target:
        client_writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        await client_writer.drain()
        client_writer.close()
        return
    target_host, target_port, origin_form_line = target
    raw_head = await strip_client_proxy_headers(raw_head)

    tried_ids: set = set()

    for attempt in range(1, MAX_GATEWAY_RETRIES + 1):
        proxy = await pick_rotating_proxy(exclude_ids=tried_ids)
        if not proxy:
            break
        tried_ids.add(proxy.id)

        if proxy.type in ("socks5", "socks4"):
            if proxy.type == "socks4":
                logger.warning("Proxy %s:%s e SOCKS4 (nao suportado) -- pulando", proxy.host, proxy.port)
                await record_proxy_outcome(proxy.id, False, "SOCKS4 nao suportado")
                continue

            success, upstream_reader, upstream_writer, reason = await socks5_connect_upstream(
                target_host, target_port, proxy
            )
            await record_proxy_outcome(proxy.id, success, reason, target=f"{target_host}:{target_port}")
            if not success:
                logger.warning(
                    "Tentativa %d/%d: %s -- tentando outro", attempt, MAX_GATEWAY_RETRIES, reason,
                )
                continue

            # dentro do tunel SOCKS5 o pedido precisa estar em forma de origem
            headers_block = raw_head.split(b"\r\n", 1)[1] if b"\r\n" in raw_head else b"\r\n\r\n"
            new_request = origin_form_line + b"\r\n" + headers_block
            upstream_writer.write(new_request)
            await upstream_writer.drain()

            logger.info(
                "HTTP %s via proxy SOCKS5 %s:%s (tentativa %d/%d)",
                request_line, proxy.host, proxy.port, attempt, MAX_GATEWAY_RETRIES,
            )
        else:
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

            await record_proxy_outcome(proxy.id, True, target=f"{target_host}:{target_port}")
            head = raw_head
            if proxy.username:
                cred = base64.b64encode(f"{proxy.username}:{proxy.password}".encode()).decode()
                head = head.replace(b"\r\n\r\n", f"\r\nProxy-Authorization: Basic {cred}\r\n\r\n".encode(), 1)

            upstream_writer.write(head)
            await upstream_writer.drain()

            logger.info(
                "HTTP %s via proxy %s:%s (tentativa %d/%d)",
                request_line, proxy.host, proxy.port, attempt, MAX_GATEWAY_RETRIES,
            )

        results = await asyncio.gather(
            relay(client_reader, upstream_writer),
            relay(upstream_reader, client_writer),
            return_exceptions=True,
        )
        bytes_in = results[0] if isinstance(results[0], int) else 0
        bytes_out = results[1] if isinstance(results[1], int) else 0
        await record_bandwidth(bytes_in, bytes_out)
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
