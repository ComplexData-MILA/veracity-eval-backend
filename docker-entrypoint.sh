#!/bin/sh

echo "Waiting for database to be ready..."
python -m app.db.wait_for_db

echo "Running database migrations..."
alembic upgrade head

echo "Starting the application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8001