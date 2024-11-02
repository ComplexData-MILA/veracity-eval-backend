docker-compose -f docker-compose.db.yml up -d --remove-orphans
alembic upgrade head

