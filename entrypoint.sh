#!/bin/sh
set -e

echo "Rodando migrações..."

echo "Rodando migrações de identity"
python -m alembic -c src/identity/migrations/alembic.ini upgrade head

echo "Rodando migrações de project"
python -m alembic -c src/project/migrations/alembic.ini upgrade head

echo "Iniciando o servidor..."
uvicorn src.main:app --host 0.0.0.0 --port 8000
