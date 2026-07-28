# ProxyHub

Plataforma web para gerenciamento de proxies, monitoramento de workers e execução de jobs de scraping, com métricas em tempo real via WebSocket.

## Stack

**Backend:** Python 3.12 · FastAPI · SQLAlchemy (async) · Alembic · PostgreSQL · Redis · APScheduler · HTTPX · JWT (python-jose) · Pydantic v2

**Frontend:** React 18 · Vite · Tailwind CSS · TanStack Query · Recharts · Zustand · Axios

**Infra:** Docker · Docker Compose · Nginx

## Arquitetura

O backend segue Clean Architecture em camadas:

```
app/
├── api/v1/        # Routers HTTP (camada de apresentação)
├── core/          # Config, segurança (JWT), banco, Redis, exceções, deps
├── models/        # Entidades SQLAlchemy
├── schemas/       # Contratos Pydantic (entrada/saída)
├── repositories/  # Acesso a dados (camada de persistência)
├── services/      # Regras de negócio (camada de domínio)
├── ws/            # Gerenciador de WebSocket (broadcast em tempo real)
├── scheduler/     # Jobs periódicos (APScheduler) — healthcheck de proxies
└── tests/         # Testes unitários (pytest)
```

Fluxo de dependência: `router → service → repository → model`. Nenhuma camada depende de camadas superiores.

## Módulos implementados

1. **Dashboard** — métricas em tempo real de CPU, RAM, Redis, PostgreSQL, proxies, workers e jobs (`GET /api/v1/dashboard`)
2. **Proxies** — CRUD completo, importação via TXT/CSV, teste de conectividade real (httpx), cálculo de score (taxa de sucesso + latência), histórico de checagens
3. **Workers** — CRUD, start/stop/restart, heartbeat com uso de CPU/RAM
4. **Jobs** — criação, pausa, retomada, cancelamento, retry com limite de tentativas, prioridade (low/normal/high/critical), máquina de estados com transições validadas
5. **Logs estruturados** — níveis (debug/info/warning/error/critical), filtráveis por nível
6. **Scheduler** — healthcheck automático de proxies a cada N segundos (configurável)
7. **Autenticação JWT** — access + refresh token, dois papéis: `admin` (CRUD completo) e `operator` (leitura + operação de jobs)
8. **WebSocket** — broadcast de eventos (`proxy_tested`, `worker_updated`, `job_created`, etc.) que o frontend consome para invalidar cache e atualizar a UI em tempo real

## Como rodar (Docker Compose — recomendado)

### Pré-requisitos
- Docker e Docker Compose instalados

### Passos

```bash
# 1. Clonar/extrair o projeto e entrar na pasta raiz
cd proxyhub

# 2. Copiar o arquivo de variáveis de ambiente
cp .env.example .env
# edite .env se quiser trocar SECRET_KEY, senha do admin, etc.

# 3. Subir todos os serviços
docker compose up --build -d

# 4. Acompanhar logs do backend (aplica migrations e cria o admin automaticamente)
docker compose logs -f backend
```

Serviços disponíveis:
- **Frontend:** http://localhost:5173
- **Backend / Swagger (OpenAPI):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Healthcheck:** http://localhost:8000/health

### Login inicial

Um usuário administrador é criado automaticamente no primeiro start, usando as variáveis `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` do `.env` (padrão: `admin` / `admin123`).

Para parar tudo:
```bash
docker compose down
# para remover também os dados do Postgres:
docker compose down -v
```

## Como rodar localmente (sem Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Suba Postgres e Redis localmente (ou via docker), então:
cp ../.env.example ../.env   # ajuste POSTGRES_HOST=localhost, REDIS_HOST=localhost

alembic upgrade head
python scripts/seed_admin.py
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Acesse http://localhost:5173.

## Rodando os testes

```bash
cd backend
pytest app/tests/ -v
```

Cobre: cálculo de score de proxies e máquina de estados de jobs (transições válidas/inválidas, retry com limite de tentativas).

## Principais endpoints da API

| Método | Rota                          | Descrição                          |
|--------|-------------------------------|-------------------------------------|
| POST   | `/api/v1/auth/login`          | Login (retorna access + refresh)   |
| POST   | `/api/v1/auth/refresh`        | Renova o access token              |
| GET    | `/api/v1/dashboard`           | Métricas agregadas em tempo real   |
| GET    | `/api/v1/proxies`             | Lista proxies                      |
| POST   | `/api/v1/proxies`             | Cria proxy (admin)                 |
| POST   | `/api/v1/proxies/import`      | Importa proxies via TXT/CSV        |
| POST   | `/api/v1/proxies/{id}/test`   | Testa conectividade do proxy       |
| GET    | `/api/v1/workers`             | Lista workers                      |
| POST   | `/api/v1/workers/{id}/restart`| Reinicia worker                    |
| GET    | `/api/v1/jobs`                | Lista jobs                         |
| POST   | `/api/v1/jobs/{id}/pause`     | Pausa job                          |
| POST   | `/api/v1/jobs/{id}/retry`     | Retenta job falho                  |
| GET    | `/api/v1/logs`                | Lista logs estruturados            |
| WS     | `/api/v1/ws?token=...`        | Canal de eventos em tempo real     |

Documentação completa e interativa (OpenAPI) em `/docs`.

## Formato de importação de proxies

**TXT** (um proxy por linha):
```
1.2.3.4:8080
1.2.3.4:8080:usuario:senha
```

**CSV**:
```
host,porta,usuario,senha
1.2.3.4,8080,usuario,senha
```

## Expansão futura

- Fila real de jobs com Redis (RQ/Celery) executando workers de scraping de fato
- Métricas históricas (séries temporais) com TimescaleDB ou Prometheus
- Rotação automática de proxies por score dentro dos jobs
- Testes de integração com banco de dados de teste (testcontainers)
- RBAC mais granular (permissões por módulo)

## Licença

Projeto de referência/MVP — adapte livremente conforme sua necessidade.
