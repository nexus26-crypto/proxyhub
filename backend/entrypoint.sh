#!/bin/sh
set -e

echo "Aguardando PostgreSQL..."
python - <<'PYEOF'
import time
import psycopg2
import os

host = os.getenv("POSTGRES_HOST", "postgres")
port = os.getenv("POSTGRES_PORT", "5432")
user = os.getenv("POSTGRES_USER", "proxyhub")
password = os.getenv("POSTGRES_PASSWORD", "proxyhub")
db = os.getenv("POSTGRES_DB", "proxyhub")

for i in range(30):
    try:
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=db)
        conn.close()
        print("PostgreSQL disponivel.")
        break
    except Exception as e:
        print(f"Tentativa {i+1}/30 - aguardando... ({e})")
        time.sleep(2)
else:
    raise SystemExit("PostgreSQL indisponivel apos varias tentativas.")
PYEOF

echo "Aplicando migracoes..."
alembic upgrade head

echo "Criando usuario admin (se necessario)..."
python scripts/seed_admin.py || true

echo "Iniciando servidor..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
