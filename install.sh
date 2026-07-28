#!/bin/bash
# ==============================================================================
# ProxyHub - Script de instalacao automatizada
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/nexus26-crypto/proxyhub/main/install.sh | bash
# ou, apos clonar o repo manualmente:
#   cd proxyhub && chmod +x install.sh && ./install.sh
#
# O que este script faz:
#   1. Instala Docker + Docker Compose (plugin oficial) se nao estiverem presentes
#   2. Clona o repositorio (se ainda nao estiver rodando de dentro dele)
#   3. Gera um .env com senhas fortes aleatorias (SECRET_KEY, senha do admin,
#      senha do gateway) -- nao usa mais os valores padrao inseguros
#   4. Builda e sobe todos os containers
#   5. Imprime a URL final do Gateway e as credenciais de login
# ==============================================================================
set -e

REPO_URL="${PROXYHUB_REPO_URL:-https://github.com/nexus26-crypto/proxyhub.git}"
INSTALL_DIR="${PROXYHUB_DIR:-/opt/proxyhub}"

color() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
info()  { color "36" "==> $1"; }
ok()    { color "32" "OK  $1"; }
warn()  { color "33" "!!  $1"; }
err()   { color "31" "ERRO $1"; }

random_secret() {
    openssl rand -hex 32 2>/dev/null || head -c 48 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 48
}

random_password() {
    # senha mais amigavel (sem caracteres que quebram URL/shell): 24 chars alfanumericos
    openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 24
}

# ------------------------------------------------------------------------------
# 1. Docker + Compose
# ------------------------------------------------------------------------------
if ! command -v docker &>/dev/null; then
    info "Docker nao encontrado. Instalando via script oficial (inclui plugin compose)..."
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    ok "Docker instalado."
else
    ok "Docker ja instalado ($(docker --version))."
fi

if ! docker compose version &>/dev/null; then
    if command -v docker-compose &>/dev/null; then
        ok "Usando docker-compose standalone ($(docker-compose --version))."
        COMPOSE="docker-compose"
    else
        info "Plugin 'docker compose' nao encontrado. Instalando binario standalone..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        COMPOSE="docker-compose"
        ok "docker-compose standalone instalado ($(docker-compose --version))."
    fi
else
    ok "Plugin 'docker compose' disponivel ($(docker compose version))."
    COMPOSE="docker compose"
fi

systemctl enable docker --now &>/dev/null || true

# ------------------------------------------------------------------------------
# 2. Codigo-fonte
# ------------------------------------------------------------------------------
if [ -f "./docker-compose.yml" ] && [ -f "./backend/app/main.py" ]; then
    info "Rodando de dentro de um checkout existente do ProxyHub. Pulando clone."
    INSTALL_DIR="$(pwd)"
else
    if [ -d "$INSTALL_DIR/.git" ]; then
        info "Repositorio ja existe em $INSTALL_DIR. Atualizando (git pull)..."
        cd "$INSTALL_DIR"
        git pull
    else
        info "Clonando repositorio em $INSTALL_DIR..."
        git clone "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
fi
cd "$INSTALL_DIR"

# ------------------------------------------------------------------------------
# 3. .env com senhas fortes geradas automaticamente + IP publico configurado
# ------------------------------------------------------------------------------
info "Detectando IP publico do servidor..."
SERVER_IP="$(curl -s -4 https://api.ipify.org || echo "")"
if [ -z "$SERVER_IP" ]; then
    warn "Nao foi possivel detectar o IP publico automaticamente."
    read -rp "Digite o IP publico (ou dominio) deste servidor: " SERVER_IP
fi
ok "IP detectado: ${SERVER_IP}"

if [ -f ".env" ]; then
    warn ".env ja existe -- nao sera sobrescrito. Delete o arquivo antes de rodar o script se quiser gerar tudo do zero."
else
    info "Gerando .env com senhas aleatorias seguras e IP configurado..."
    cp .env.example .env

    SECRET_KEY_VAL="$(random_secret)"
    ADMIN_PASSWORD_VAL="$(random_password)"
    GATEWAY_PASSWORD_VAL="$(random_password)"
    POSTGRES_PASSWORD_VAL="$(random_password)"

    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY_VAL}|" .env
    sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ADMIN_PASSWORD_VAL}|" .env
    sed -i "s|^GATEWAY_PASSWORD=.*|GATEWAY_PASSWORD=${GATEWAY_PASSWORD_VAL}|" .env
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD_VAL}|" .env

    # CRITICO: sem isso o frontend nao consegue falar com o backend quando
    # acessado por IP publico (erro de CORS / URL da API apontando para localhost)
    sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=[\"http://${SERVER_IP}:5173\",\"http://localhost:5173\"]|" .env
    sed -i "s|^VITE_API_URL=.*|VITE_API_URL=http://${SERVER_IP}:8000/api/v1|" .env
    sed -i "s|^VITE_WS_URL=.*|VITE_WS_URL=ws://${SERVER_IP}:8000/api/v1/ws|" .env

    ok ".env criado com senhas geradas automaticamente e IP ${SERVER_IP} configurado."
fi

# ------------------------------------------------------------------------------
# 4. Build e subida dos containers
# ------------------------------------------------------------------------------
info "Buildando imagens (pode demorar alguns minutos na primeira vez)..."
$COMPOSE build

info "Subindo containers..."
$COMPOSE up -d

info "Aguardando o backend aplicar migrations e criar o usuario admin..."
sleep 8
for i in $(seq 1 20); do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        break
    fi
    sleep 3
done

# ------------------------------------------------------------------------------
# 5. Resumo final
# ------------------------------------------------------------------------------
ADMIN_USER="$(grep '^ADMIN_USERNAME=' .env | cut -d= -f2)"
ADMIN_PASS="$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2)"
GATEWAY_USER="$(grep '^GATEWAY_USERNAME=' .env | cut -d= -f2)"
GATEWAY_PASS="$(grep '^GATEWAY_PASSWORD=' .env | cut -d= -f2)"
GATEWAY_PORT="$(grep '^GATEWAY_PORT=' .env | cut -d= -f2)"

echo ""
color "32" "=============================================================="
color "32" "  ProxyHub instalado com sucesso!"
color "32" "=============================================================="
echo ""
echo "Frontend:      http://${SERVER_IP}:5173"
echo "API / Swagger: http://${SERVER_IP}:8000/docs"
echo ""
echo "Login:"
echo "  usuario: ${ADMIN_USER}"
echo "  senha:   ${ADMIN_PASS}"
echo ""
echo "Gateway de Proxy Rotativo (aponte seu bot para isto):"
echo "  http://${GATEWAY_USER}:${GATEWAY_PASS}@${SERVER_IP}:${GATEWAY_PORT}"
echo ""
warn "As senhas geradas estao salvas em: ${INSTALL_DIR}/.env -- guarde em local seguro."
color "32" "=============================================================="
