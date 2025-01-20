#!/bin/sh

set -e

cd /app

echo "Waiting for database to be ready..."
python scripts/wait_for_db.py

echo "Running database migrations..."
# alembic revision --autogenerate -m "Domain credibility made nullable"
alembic downgrade -1
alembic upgrade head

echo "Starting the application..."
uvicorn app.main:app --host 0.0.0.0 --port 8001